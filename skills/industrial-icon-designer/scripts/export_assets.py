#!/usr/bin/env python3
"""Export Desktop PNGs and Web SVGs from eligible masters. Derived artifacts only; never calls an LLM.

    export_assets.py --set DIR [--target all|desktop|web] [--web-img] [--dry-run] [--resolve overwrite] [--json]

Outputs (under DIR/exports/):
    desktop/<theme>/<state>/<size>/<icon-id>.png   transparent RGBA, rendered directly at <size>
    web/<icon-id>.svg                              inline profile, keeps currentColor
    web/img/<theme>/<state>/<icon-id>.svg          optional (--web-img): colors resolved for <img> use

Only icons whose manifest status is `eligible` are exported. Writes are staged, validated, then
committed file by file with a recovery journal; a crashed commit is completed on the next run.
Files changed by hand, or unknown files at a planned path, are reported as conflicts and are never
overwritten or deleted unless --resolve overwrite is given (the old file is then moved to
exports/.conflicts/, not destroyed). Exit codes: 0 ok, 3 renderer missing, 4 conflicts/drift/invalid
staged output, 5 render or write failure.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import shutil
from pathlib import Path

from PIL import Image

import approvals
import invalidate
import manifest as manifest_mod
import palette
import run_state
import style_spec
from common import (EXIT_INPUT, EXIT_OK, EXIT_RENDER, EXIT_VALIDATION, ToolError, atomic_write, canonical_hash, emit,
                    ensure_inside, find_resvg,
                    parse_svg, recolor_svg, render_many, resvg_version, run_main, sha256_bytes, sha256_file,
                    svg_findings, timed, write_json)

FORMAT_VERSION = 1
KINDS_BY_TARGET = {"desktop": {"desktop-png"}, "web": {"web-inline"}, "all": {"desktop-png", "web-inline"}}
JOURNAL = "exports/.journal.json"
STAGING = "exports/.staging"
CONFLICTS = "exports/.conflicts"


def _variant_or_master(set_dir: Path, icon_id: str, size: int | None, small: list[int]) -> Path:
    variant = set_dir / "variants" / "small" / f"{icon_id}.svg"
    if size is not None and size in small and variant.is_file():
        return variant
    return set_dir / "masters" / f"{icon_id}.svg"


def plan_outputs(set_dir: Path, manifest: dict, spec: dict, kinds: set[str], renderer: str) -> list[dict]:
    """Every output expected for the eligible icons in the selected scope."""
    small = spec["small_variant_sizes_px"]
    items = []
    for icon in manifest["icons"]:
        if icon["status"] != "eligible":
            continue
        iid = icon["id"]
        if "desktop-png" in kinds:
            for theme, tokens in sorted(spec["themes"].items()):
                for state in spec["states"]:
                    color, accent = palette.state_colors(tokens, state)
                    for size in sorted(icon["sizes_px"]):
                        src = _variant_or_master(set_dir, iid, size, small)
                        src_sha = sha256_file(src)
                        items.append({"id": iid, "kind": "desktop-png", "theme": theme, "state": state,
                                      "size_px": size, "color": color, "accent": accent, "source": src,
                                      "source_sha256": src_sha,
                                      "path": f"exports/desktop/{theme}/{state}/{size}/{iid}.png",
                                      "config_sha256": canonical_hash({"f": FORMAT_VERSION, "kind": "desktop-png",
                                                                       "theme": theme, "state": state, "size": size,
                                                                       "color": color, "src": src_sha,
                                                                       "renderer": renderer,
                                                                       **({"accent": accent} if accent else {})})})
        if "web-inline" in kinds:
            src = set_dir / "masters" / f"{iid}.svg"
            src_sha = sha256_file(src)
            items.append({"id": iid, "kind": "web-inline", "source": src, "source_sha256": src_sha,
                          "path": f"exports/web/{iid}.svg",
                          "config_sha256": canonical_hash({"f": FORMAT_VERSION, "kind": "web-inline", "src": src_sha})})
        if "web-img" in kinds:
            src = set_dir / "masters" / f"{iid}.svg"
            src_sha = sha256_file(src)
            for theme, tokens in sorted(spec["themes"].items()):
                for state in spec["states"]:
                    color, accent = palette.state_colors(tokens, state)
                    items.append({"id": iid, "kind": "web-img", "theme": theme, "state": state, "color": color,
                                  "accent": accent, "source": src, "source_sha256": src_sha,
                                  "path": f"exports/web/img/{theme}/{state}/{iid}.svg",
                                  "config_sha256": canonical_hash({"f": FORMAT_VERSION, "kind": "web-img",
                                                                   "theme": theme, "state": state, "color": color,
                                                                   "src": src_sha,
                                                                   **({"accent": accent} if accent else {})})})
    return items


def svg_payload(item: dict) -> bytes:
    text = item["source"].read_text(encoding="utf-8")
    if item["kind"] == "web-img":
        text = recolor_svg(text, item["color"], item.get("accent"))
    return text.encode("utf-8")


def classify(set_dir: Path, manifest: dict, items: list[dict], kinds: set[str]) -> dict:
    """Decide create/update/unchanged/remove/conflict for every planned and managed path."""
    managed = {e["path"]: (icon["id"], e) for icon in manifest["icons"]
               for e in icon["exports"] + icon.get("stale_exports", [])}
    managed.update({e["path"]: (None, e) for e in manifest.get("orphaned_exports", [])})  # icons that were removed
    planned = {i["path"]: i for i in items}
    result = {"create": [], "update": [], "unchanged": [], "remove": [], "conflicts": [], "unknown": []}
    for path, item in planned.items():
        final = set_dir / path
        entry = managed.get(path, (None, None))[1]
        if final.exists():
            current = sha256_file(final)
            if entry is None:
                result["conflicts"].append({"path": path, "reason": "unmanaged file at a planned path"})
            elif current != entry["sha256"]:
                result["conflicts"].append({"path": path, "reason": "export was changed by hand"})
            elif entry["config_sha256"] == item["config_sha256"]:
                result["unchanged"].append(path)
            else:
                result["update"].append(path)
        else:
            result["create"].append(path)
    for path, (icon_id, entry) in sorted(managed.items()):
        if path in planned or entry["kind"] not in kinds:
            continue
        final = set_dir / path
        if not final.exists():
            result["remove"].append(path)  # entry only; nothing on disk
        elif sha256_file(final) == entry["sha256"]:
            result["remove"].append(path)
        else:
            result["conflicts"].append({"path": path, "reason": "managed export no longer planned but changed by hand"})
    exports = set_dir / "exports"
    if exports.is_dir():
        known = set(planned) | set(managed)
        for f in sorted(exports.rglob("*")):
            rel = f.relative_to(set_dir).as_posix()
            if f.is_file() and rel not in known and not rel.startswith((STAGING, CONFLICTS)) and rel != JOURNAL:
                result["unknown"].append(rel)
    for key in result:
        result[key] = sorted(result[key], key=lambda x: x["path"] if isinstance(x, dict) else x)
    return result


def validate_staged(item: dict, staged: Path) -> None:
    if item["kind"] == "desktop-png":
        with Image.open(staged) as im:
            im.load()
            if im.size != (item["size_px"], item["size_px"]) or im.mode != "RGBA":
                raise ToolError(EXIT_VALIDATION, f"staged PNG is {im.size} {im.mode}, expected "
                                f"{item['size_px']}px RGBA", item["path"])
    else:
        root = parse_svg(staged.read_bytes(), item["path"])
        bad = svg_findings(root)
        if bad:
            raise ToolError(EXIT_VALIDATION, "staged SVG is unsafe: " + "; ".join(bad), item["path"])
        text = staged.read_text(encoding="utf-8")
        if item["kind"] == "web-img" and "currentColor" in text:
            raise ToolError(EXIT_VALIDATION, "web-img variant still contains currentColor", item["path"])
        if item["kind"] == "web-inline" and "currentColor" not in text:
            raise ToolError(EXIT_VALIDATION, "inline variant lost currentColor", item["path"])


def recover(set_dir: Path) -> dict | None:
    """Finish a commit that was interrupted; idempotent. Returns a summary or None if nothing to do."""
    journal_path = set_dir / JOURNAL
    if not journal_path.exists():
        return None
    journal = json.loads(journal_path.read_text())
    done = []
    for op in journal["operations"]:
        final = set_dir / op["path"]
        if op["op"] == "write":
            staged = set_dir / STAGING / op["path"]
            if staged.exists():
                final.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, final)
            elif not (final.exists() and sha256_file(final) == op["sha256"]):
                raise ToolError(EXIT_RENDER, f"recovery journal references a missing staged file: {op['path']}",
                                str(journal_path))
        elif op["op"] == "remove" and final.exists():
            final.unlink()
        done.append(op["path"])
    manifest_mod.set_exports(set_dir, journal["exports_by_id"], set(journal.get("keep_stale_kinds", [])))
    shutil.rmtree(set_dir / STAGING, ignore_errors=True)
    journal_path.unlink()
    return {"recovered_operations": len(done)}


@contextlib.contextmanager
def export_lock(set_dir: Path):
    """One export at a time per set: a second run would destroy the first run's staged files."""
    path = set_dir / ".export.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ToolError(EXIT_INPUT, "another export is running on this set; wait for it to finish", str(path))
        yield
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        os.close(fd)


def export(set_dir: Path, target: str = "all", web_img: bool = False, dry_run: bool = False,
           resolve: str | None = None, _fail_after: int | None = None) -> dict:
    set_dir = Path(set_dir)
    ensure_inside(set_dir, "masters", "variants", "exports", "reports")
    if dry_run:
        return _export(set_dir, target, web_img, True, resolve, _fail_after)
    with export_lock(set_dir):
        return _export(set_dir, target, web_img, False, resolve, _fail_after)


def _export(set_dir: Path, target: str, web_img: bool, dry_run: bool, resolve: str | None,
            _fail_after: int | None) -> dict:
    kinds = set(KINDS_BY_TARGET[target]) | ({"web-img"} if web_img and target in ("all", "web") else set())
    renderer = "n/a"
    if "desktop-png" in kinds:  # only raster output needs the renderer
        find_resvg()
        renderer = resvg_version()
    recovered = None if dry_run else recover(set_dir)
    drift = invalidate.detect(set_dir)["changes"]
    if drift:
        raise ToolError(EXIT_VALIDATION, "drift detected (" + ", ".join(c["change"] for c in drift) + "); run "
                        "invalidate.py detect --apply first so stale outputs are reset, then export again")
    gate = approvals.evaluate(set_dir, "pilot")
    if not gate["valid"]:
        raise ToolError(EXIT_VALIDATION, f"pilot approval gate closed: {gate['reason']}; approve the pilot again "
                        "(approvals.py record --type pilot) before exporting")
    manifest = manifest_mod.sync(set_dir, persist=not dry_run)
    unreviewed = sorted(i["id"] for i in manifest["icons"] if i["qa"].get("color_review") == "pending")
    if unreviewed:
        raise ToolError(EXIT_VALIDATION, "the palette changed and has not been reviewed (" + ", ".join(unreviewed[:5])
                        + ("..." if len(unreviewed) > 5 else "") + "); record approvals.py record --type palette "
                        "--ids all --reviewer user, then export again")
    spec = style_spec.load_spec(set_dir)
    items = plan_outputs(set_dir, manifest, spec, kinds, renderer)
    skipped = [{"id": i["id"], "status": i["status"], "reason": "not export-eligible (needs structural pass and "
                "current visual approval)"} for i in manifest["icons"] if i["status"] != "eligible"]
    cls = classify(set_dir, manifest, items, kinds)
    counts = {k: sum(1 for i in items if i["kind"] == k) for k in sorted(kinds)}
    summary = {"dry_run": dry_run, "planned": counts, "skipped": skipped,
               **{k: v for k, v in cls.items()}, "recovered": recovered}
    if dry_run:
        return summary
    if cls["conflicts"] and resolve != "overwrite":
        summary["status"] = "conflicts"
        raise ToolError(EXIT_VALIDATION, "conflicts found; nothing was changed. "
                        + "; ".join(f"{c['path']} ({c['reason']})" for c in cls["conflicts"][:5])
                        + ("; ..." if len(cls["conflicts"]) > 5 else "")
                        + ". Review them, or rerun with --resolve overwrite (originals are kept in exports/.conflicts)")

    by_path = {i["path"]: i for i in items}
    to_write = [by_path[p] for p in cls["create"] + cls["update"]]
    conflict_paths = {c["path"] for c in cls["conflicts"]}
    to_write += [by_path[p] for p in conflict_paths if p in by_path]
    staging = set_dir / STAGING
    shutil.rmtree(staging, ignore_errors=True)

    jobs = []
    for item in to_write:
        out = staging / item["path"]
        if item["kind"] == "desktop-png":
            jobs.append((recolor_svg(item["source"].read_text(encoding="utf-8"), item["color"],
                                     item.get("accent")).encode(), out, item["size_px"]))
        else:
            atomic_write(out, svg_payload(item))
    render_many(jobs)
    for item in to_write:
        validate_staged(item, staging / item["path"])
    staged_sha = {i["path"]: sha256_file(staging / i["path"]) for i in to_write}

    # new manifest entries for every planned path (unchanged ones keep their recorded hash)
    entries_by_id: dict[str, list[dict]] = {}
    kept = {e["path"]: e for icon in manifest["icons"] for e in icon["exports"] + icon.get("stale_exports", [])}
    for item in items:
        sha = staged_sha.get(item["path"]) or kept[item["path"]]["sha256"]
        entry = {"kind": item["kind"], "path": item["path"], "sha256": sha,
                 "source_sha256": item["source_sha256"], "config_sha256": item["config_sha256"]}
        for key in ("theme", "state", "size_px"):
            if key in item:
                entry[key] = item[key]
        entries_by_id.setdefault(item["id"], []).append(entry)
    for icon in manifest["icons"]:  # keep exports of kinds outside the selected scope
        outside = [e for e in icon["exports"] if e["kind"] not in kinds]
        entries_by_id.setdefault(icon["id"], []).extend(outside)

    operations = [{"op": "write", "path": p, "sha256": staged_sha[p]} for p in sorted(staged_sha)]
    operations += [{"op": "remove", "path": p} for p in cls["remove"]]
    keep_stale = sorted({"desktop-png", "web-inline", "web-img"} - kinds)
    atomic_write(set_dir / JOURNAL, (json.dumps({"operations": operations, "exports_by_id": entries_by_id,
                                                 "keep_stale_kinds": keep_stale},
                                                sort_keys=True, indent=1) + "\n").encode())

    committed = 0
    if resolve == "overwrite":
        for c in cls["conflicts"]:
            old = set_dir / c["path"]
            if old.exists():
                keep = set_dir / CONFLICTS / (c["path"] + "." + sha256_file(old)[:8])
                keep.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old), keep)
    for op in operations:
        if _fail_after is not None and committed >= _fail_after:
            raise RuntimeError("simulated crash during commit")
        final = set_dir / op["path"]
        if op["op"] == "write":
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging / op["path"], final)
        elif final.exists():
            final.unlink()
        committed += 1
    manifest_mod.set_exports(set_dir, entries_by_id, set(keep_stale))
    shutil.rmtree(staging, ignore_errors=True)
    (set_dir / JOURNAL).unlink()

    if not skipped and {"desktop-png", "web-inline"} <= kinds:  # a partial scope does not complete the export
        run_state.advance(set_dir, spec["set_id"], "EXPORTED")
    summary.update({"status": "exported", "written": len(to_write), "removed": len(cls["remove"])})
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="set_dir", required=True)
    ap.add_argument("--target", choices=["all", "desktop", "web"], default="all")
    ap.add_argument("--web-img", action="store_true", help="also write resolved-color SVGs for <img> use")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resolve", choices=["overwrite"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    clock = contextlib.nullcontext() if args.dry_run else timed(args.set_dir, "export")  # a dry run writes nothing
    with clock:
        result = export(Path(args.set_dir), args.target, args.web_img, args.dry_run, args.resolve)
    brief = {k: (len(v) if isinstance(v, list) else v) for k, v in result.items()}
    emit(result, args.json, " ".join(f"{k}={v}" for k, v in brief.items()))
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
