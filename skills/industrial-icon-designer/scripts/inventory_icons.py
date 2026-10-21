#!/usr/bin/env python3
"""Build inventory.json from PNG/SVG references plus optional JSON/CSV metadata.

    python inventory_icons.py --input ./references --set ./icon-work/scada [--metadata meta.json] [--json]

References are never modified; their path, SHA-256 and raster facts are recorded. Unsafe or
oversized inputs are reported in `rejected`, never skipped silently. Exit codes: 0 ok,
2 input/configuration, 4 one or more inputs rejected (inventory is still written).
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from PIL import Image

import run_state
from common import (EXIT_INPUT, EXIT_OK, EXIT_VALIDATION, ToolError, emit, guardrail_hint, guardrails,
                    is_within, kebab_id, load_json, parse_svg, run_main, sha256_file, svg_findings,
                    svg_viewbox, validate_schema, write_json)

SCHEMA_VERSION = "1.0"
LIST_FIELDS = {"usage_locations": str, "sizes_px": int}
DEFAULTS = {"functional_group": "navigation-layout", "semantic_role": "object", "usage_locations": ["unknown"]}
METADATA_NAMES = {"metadata.json", "metadata.csv"}


# ------------------------------------------------------------------ discovery

def discover(inputs: list[Path]) -> tuple[list[tuple[Path, Path]], int]:
    """Return ([(file, root)], ignored_count) for PNG/SVG files under the inputs."""
    found, ignored = [], 0
    for item in inputs:
        if item.is_dir():
            root = item
            candidates = sorted(p for p in item.rglob("*") if p.is_file() or p.is_symlink())
        elif item.exists() or item.is_symlink():
            root, candidates = item.parent, [item]
        else:
            raise ToolError(EXIT_INPUT, "input not found", str(item))
        for p in candidates:
            if p.suffix.lower() in (".png", ".svg"):
                found.append((p, root))
            elif p.name.lower() not in METADATA_NAMES:
                ignored += 1
    return found, ignored


# ------------------------------------------------------------------- metadata

def _split(value: str, cast):
    return [cast(x.strip()) for x in value.replace(",", ";").split(";") if x.strip()]


def load_metadata(path: Path | None) -> tuple[dict[str, dict], list[str]]:
    """Return (rows by id, ids with conflicting duplicate rows)."""
    if path is None:
        return {}, []
    rows: list[dict] = []
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8") as fh:
            for raw in csv.DictReader(fh):
                row = {k: v for k, v in raw.items() if v not in (None, "")}
                for key, cast in LIST_FIELDS.items():
                    if key in row:
                        row[key] = _split(row[key], cast)
                rows.append(row)
    else:
        data = load_json(path)
        rows = data["icons"] if isinstance(data, dict) else data
    by_id: dict[str, dict] = {}
    conflicts: list[str] = []
    for row in rows:
        rid = kebab_id(str(row.get("id", "")))
        if not rid:
            continue
        if rid in by_id and by_id[rid].get("meaning") != row.get("meaning"):
            conflicts.append(rid)
        by_id.setdefault(rid, row)
    return by_id, sorted(set(conflicts))


# ---------------------------------------------------------------- inspection

def inspect_file(path: Path, root: Path, limits: dict, hint: str) -> dict:
    """Facts about one reference, or raise ToolError(EXIT_VALIDATION) describing the rejection."""
    if path.is_symlink() and not is_within(path, root):
        raise ToolError(EXIT_VALIDATION, "symlink resolves outside the input root", str(path))
    size = path.stat().st_size
    if size > limits["max_input_bytes"]:
        raise ToolError(EXIT_VALIDATION, f"file is {size} bytes, above max_input_bytes "
                        f"({limits['max_input_bytes']}); {hint}", str(path))
    info = {"path": str(path), "sha256": sha256_file(path), "kind": path.suffix.lower().lstrip(".")}
    if info["kind"] == "png":
        try:
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                width, height = im.size
                info["has_alpha"] = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
        except Exception as exc:
            raise ToolError(EXIT_VALIDATION, f"unreadable PNG: {exc}", str(path))
        if max(width, height) > limits["max_raster_px"]:
            raise ToolError(EXIT_VALIDATION, f"{width}x{height} exceeds max_raster_px "
                            f"({limits['max_raster_px']}); {hint}", str(path))
        info["width"], info["height"] = width, height
    else:
        root_el = parse_svg(path.read_bytes(), str(path), strict_markup=False)
        findings = svg_findings(root_el)
        if findings:
            raise ToolError(EXIT_VALIDATION, "unsafe SVG: " + "; ".join(findings), str(path))
        vb = svg_viewbox(root_el)
        if vb:
            info["width"], info["height"] = int(vb[2]), int(vb[3])
    return info


# -------------------------------------------------------------------- build

def build_icon(icon_id: str, refs: list[dict], meta: dict | None, conflict: bool, set_dir: Path) -> dict:
    refs = sorted(refs, key=lambda r: (r["kind"] != "svg", r["path"]))  # SVG first
    primary = refs[0]
    inferred: dict[str, dict] = {}
    notes = [meta.get("notes")] if meta and meta.get("notes") else []
    meta = meta or {}

    def pick(field, fallback, why):
        if field in meta and meta[field] not in (None, "", []):
            return meta[field]
        inferred[field] = {"confidence": "low", "note": why}
        return fallback

    meaning = pick("meaning", icon_id.replace("-", " ").capitalize(), "no metadata; derived from the file name")
    dim = primary.get("width")
    sizes = pick("sizes_px", [dim] if dim and 8 <= dim <= 1024 else [16, 24],
                 "no metadata; derived from the reference dimensions")
    usage = pick("usage_locations", list(DEFAULTS["usage_locations"]), "no metadata; usage unknown")
    group = pick("functional_group", DEFAULTS["functional_group"], "no metadata; placeholder group")
    role = pick("semantic_role", DEFAULTS["semantic_role"], "no metadata; placeholder role")

    if len(refs) > 1:
        notes.append("PNG and SVG references both present; SVG used for geometry, PNG retained")
    needs_review = bool(inferred) or bool(meta.get("ambiguous")) or conflict
    if conflict:
        notes.append("conflicting metadata rows for this id; resolve the meaning")
    if meta.get("ambiguous"):
        notes.append("marked ambiguous in metadata")
    if "meaning" in inferred:
        notes.append("meaning unresolved: review before approval")

    base = Path(set_dir).resolve()
    out_refs = []
    for r in refs:
        r = dict(r)
        r["path"] = Path(os.path.relpath(Path(r["path"]).resolve(), base)).as_posix()
        out_refs.append(r)
    entry = {"id": icon_id, "meaning": meaning, "source_path": out_refs[0]["path"], "usage_locations": usage,
             "sizes_px": sorted(set(int(s) for s in sizes)), "functional_group": group, "semantic_role": role,
             "status": "NEEDS_REVIEW" if needs_review else "INVENTORIED", "references": out_refs}
    if inferred:
        entry["inferred"] = inferred
    if notes:
        entry["notes"] = "; ".join(n for n in notes if n)
    if meta.get("fixture") or "synthetic" in (meta.get("notes") or ""):
        entry["fixture"] = True
    return entry


def run(inputs: list[Path], set_dir: Path, metadata: Path | None, set_id: str | None) -> dict:
    set_dir = Path(set_dir)
    limits = guardrails(set_dir)
    hint = guardrail_hint(set_dir)
    files, ignored = discover(inputs)
    if len(files) > limits["max_icons_per_run"]:
        raise ToolError(EXIT_INPUT, f"{len(files)} files exceed max_icons_per_run "
                        f"({limits['max_icons_per_run']}); {hint}")

    rejected, by_id = [], {}
    for path, root in files:
        icon_id = kebab_id(path.stem)
        try:
            info = inspect_file(path, root, limits, hint)
        except ToolError as exc:
            rejected.append({"path": str(path), "reason": exc.message})
            continue
        if not icon_id:
            rejected.append({"path": str(path), "reason": "file name yields an empty id"})
            continue
        slot = by_id.setdefault(icon_id, {})
        if info["kind"] in slot:
            rejected.append({"path": str(path), "reason": f"id '{icon_id}' collides (case-insensitive) with "
                             f"{slot[info['kind']]['path']}"})
            continue
        slot[info["kind"]] = info

    meta_rows, conflicts = load_metadata(metadata)
    icons = [build_icon(i, list(refs.values()), meta_rows.get(i), i in conflicts, set_dir)
             for i, refs in sorted(by_id.items())]
    unmatched = sorted(set(meta_rows) - set(by_id))
    sid = set_id or kebab_id(set_dir.resolve().name) or "icon-set"
    inventory = {"schema_version": SCHEMA_VERSION, "set_id": sid, "icons": icons,
                 "rejected": sorted(rejected, key=lambda r: r["path"]),
                 "unresolved": [i["id"] for i in icons if i["status"] == "NEEDS_REVIEW"],
                 "unmatched_metadata": unmatched, "ignored_files": ignored}
    validate_schema(inventory, "inventory", str(set_dir / "inventory.json"))
    write_json(set_dir / "inventory.json", inventory)
    # a re-inventory (for example when extending a set) must not forget finished work
    state = run_state.load(set_dir, sid) if (set_dir / "run-state.json").exists() else None
    done = {i for b in state["completed_batches"] for i in b["ids"]} if state else set()
    done |= {i["id"] for i in icons if (set_dir / "masters" / f"{i['id']}.svg").is_file()}
    run_state.advance(set_dir, sid, "INVENTORIED", pending_ids=[i["id"] for i in icons if i["id"] not in done])
    return inventory


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", nargs="+", required=True, help="PNG/SVG files or directories")
    ap.add_argument("--set", dest="set_dir", required=True)
    ap.add_argument("--metadata", help="JSON or CSV inventory metadata")
    ap.add_argument("--set-id")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    metadata = Path(args.metadata) if args.metadata else None
    if metadata is None and len(args.input) == 1 and Path(args.input[0]).is_dir():
        for name in ("metadata.json", "metadata.csv"):
            if (Path(args.input[0]) / name).exists():
                metadata = Path(args.input[0]) / name
                break
    inv = run([Path(p) for p in args.input], Path(args.set_dir), metadata, args.set_id)
    emit({"icons": len(inv["icons"]), "rejected": inv["rejected"], "unresolved": inv["unresolved"],
          "inventory": str(Path(args.set_dir) / "inventory.json")}, args.json,
         f"{len(inv['icons'])} icons, {len(inv['rejected'])} rejected, {len(inv['unresolved'])} need review")
    for r in inv["rejected"]:
        print(f"rejected: {r['path']}: {r['reason']}", file=__import__("sys").stderr)
    return EXIT_VALIDATION if inv["rejected"] else EXIT_OK


if __name__ == "__main__":
    run_main(main)
