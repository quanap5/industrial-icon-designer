#!/usr/bin/env python3
"""manifest.json: one record per drawn icon with hashes, QA state, variants and exports.

    manifest.py sync   --set DIR [--json]                      rebuild from inventory, masters, approvals
    manifest.py status --set DIR [--json]
    manifest.py reject --set DIR --ids a,b --reviewer user     mark visual review rejected (until the asset changes)
    manifest.py bump   --set DIR --part patch|minor|major --note TEXT [--ids a,b]

`sync` derives visual approval from approvals.json: an icon is approved only while its master (and
small variant) hash equals the hash recorded in a covering approval. A changed asset drops back to
pending and loses its exports, so stale review evidence is never accepted.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
from pathlib import Path

import style_spec
from common import (EXIT_INPUT, EXIT_OK, ToolError, atomic_write, emit, load_json, log_event, resvg_version,
                    run_main, sha256_file, validate_schema, write_json)

SCHEMA_VERSION = "1.0"
INITIAL_VERSION = "1.0.0"


def path_for(set_dir: Path) -> Path:
    return Path(set_dir) / "manifest.json"


def load(set_dir: Path) -> dict | None:
    p = path_for(set_dir)
    if not p.exists():
        return None
    data = load_json(p)
    validate_schema(data, "manifest", str(p))
    return data


def save(set_dir: Path, manifest: dict) -> None:
    validate_schema(manifest, "manifest", str(path_for(set_dir)))
    write_json(path_for(set_dir), manifest)


def combined_asset_hash(set_dir: Path, icon_id: str) -> str | None:
    """One hash over an icon's master and small variant; None if there is no master."""
    master = Path(set_dir) / "masters" / f"{icon_id}.svg"
    if not master.is_file():
        return None
    h = hashlib.sha256(sha256_file(master).encode())
    variant = Path(set_dir) / "variants" / "small" / f"{icon_id}.svg"
    if variant.is_file():
        h.update(sha256_file(variant).encode())
    return h.hexdigest()


def load_approvals(set_dir: Path) -> list[dict]:
    p = Path(set_dir) / "approvals.json"
    return load_json(p)["approvals"] if p.exists() else []


def visual_from_approvals(approvals: list[dict], icon_id: str, asset_hash: str) -> tuple[str, str, bool]:
    """(status, reviewer_type, was_stale) from the latest approval that covers this icon."""
    covering = [a for a in approvals if icon_id in a["asset_hashes"] and a["type"] in ("pilot", "batch")]
    if not covering:
        return "pending", "none", False
    latest = covering[-1]
    if latest["asset_hashes"][icon_id] == asset_hash:
        return "approved", latest["reviewer_type"], False
    return "pending", "none", True


def retire_exports(icon: dict, kinds: set[str] | None = None) -> None:
    """Invalidate exports but remember them: their recorded hashes still tell export_assets which files
    on disk are ours (safe to refresh) and which were changed by hand (conflicts)."""
    moved = [e for e in icon["exports"] if kinds is None or e["kind"] in kinds]
    icon["exports"] = [e for e in icon["exports"] if e not in moved]
    stale = {e["path"]: e for e in icon.get("stale_exports", [])}
    stale.update({e["path"]: e for e in moved})
    if stale:
        icon["stale_exports"] = sorted(stale.values(), key=lambda e: e["path"])


def derive_status(qa: dict) -> str:
    if qa["structural"] == "failed" or qa["visual"] == "rejected":
        return "rejected"
    if qa["structural"] == "passed" and qa["visual"] == "approved":
        return "eligible"
    return "pending"


def build_variants(set_dir: Path, spec: dict, icon_id: str) -> list[dict]:
    out = []
    variant = Path(set_dir) / "variants" / "small" / f"{icon_id}.svg"
    for size in spec["small_variant_sizes_px"]:
        if variant.is_file():
            out.append({"size_px": size, "path": f"variants/small/{icon_id}.svg", "sha256": sha256_file(variant)})
        else:
            out.append({"size_px": size, "fallback_to_master": True})
    return out


def sync(set_dir: Path, persist: bool = True) -> dict:
    """Rebuild the manifest. With persist=False nothing is written or logged (used by dry runs)."""
    set_dir = Path(set_dir)
    spec = style_spec.load_spec(set_dir)
    inv = load_json(set_dir / "inventory.json")
    brief_path = set_dir / "brief.json"
    mode = load_json(brief_path).get("redesign_mode", "redraw") if brief_path.exists() else "redraw"
    previous = load(set_dir)
    prev_icons = {i["id"]: i for i in previous["icons"]} if previous else {}
    approvals = load_approvals(set_dir)

    palette_votes = [a for a in approvals if a["type"] == "palette"]
    palette_approved = bool(palette_votes) and palette_votes[-1].get("palette_hash") == style_spec.palette_hash(spec)
    icons, changed = [], []
    for ic in inv["icons"]:
        asset = combined_asset_hash(set_dir, ic["id"])
        if asset is None:
            continue
        master = set_dir / "masters" / f"{ic['id']}.svg"
        prev = prev_icons.get(ic["id"])
        ref = ic["references"][0]
        geometry_changed = bool(prev) and prev["qa"].get("asset_sha256") != asset
        qa = {"structural": "pending", "visual": "pending", "reviewer_type": "none", "asset_sha256": asset,
              "reports": []}
        if prev and not geometry_changed:
            qa["structural"] = prev["qa"]["structural"]
            qa["reports"] = prev["qa"].get("reports", [])
            if prev["qa"]["visual"] == "rejected":
                qa["visual"], qa["reviewer_type"] = "rejected", prev["qa"]["reviewer_type"]
        void_after = prev["qa"].get("review_void_after", 0) if prev else 0
        if void_after:
            qa["review_void_after"] = void_after
        if ic["status"] == "NEEDS_REVIEW":  # an unresolved meaning is never approved, whoever asks
            qa["visual"], qa["reviewer_type"] = "pending", "none"
        elif qa["visual"] != "rejected":
            qa["visual"], qa["reviewer_type"], _ = visual_from_approvals(approvals[void_after:], ic["id"], asset)
        if prev and prev["qa"].get("color_review") == "pending" and not palette_approved:
            qa["color_review"] = "pending"
        if geometry_changed:
            changed.append(ic["id"])
        entry = {"id": ic["id"], "meaning": ic["meaning"], "semantic_role": ic["semantic_role"],
                 "functional_group": ic["functional_group"], "usage_locations": ic["usage_locations"],
                 # sizes and reference hash are a baseline kept until invalidate.py consumes a detected change
                 "sizes_px": prev["sizes_px"] if prev else ic["sizes_px"],
                 "source_path": prev["source_path"] if prev else ref["path"],
                 "source_sha256": prev["source_sha256"] if prev else ref["sha256"],
                 "master_path": f"masters/{ic['id']}.svg", "master_sha256": sha256_file(master), "route": mode,
                 "style_version": spec["style_version"], "variants": build_variants(set_dir, spec, ic["id"]),
                 "qa": qa, "exports": [] if (geometry_changed or not prev) else prev["exports"]}
        if prev and prev.get("stale_exports"):
            entry["stale_exports"] = prev["stale_exports"]
        if geometry_changed:  # the old files stay known (by hash) but no longer count as current exports
            stale = {e["path"]: e for e in entry.get("stale_exports", []) + prev["exports"]}
            entry["stale_exports"] = sorted(stale.values(), key=lambda e: e["path"])
        if ic.get("notes"):
            entry["notes"] = ic["notes"]
        if ic.get("variant_of"):
            entry["variant_of"], entry["variant_kind"] = ic["variant_of"], ic.get("variant_kind", "filled")
        entry["status"] = derive_status(qa)
        icons.append(entry)

    # The baseline (style hashes, renderer) is kept until invalidate.py consumes a detected drift, so a
    # style or renderer change cannot be silently absorbed by an unrelated sync.
    baseline = ({"style_hashes": previous["style_hashes"], "toolchain": previous["toolchain"]}
                if previous and "style_hashes" in previous else current_baseline(spec))
    manifest = {"schema_version": SCHEMA_VERSION, "set_id": spec["set_id"],
                "asset_set_version": previous["asset_set_version"] if previous else INITIAL_VERSION,
                "style_version": spec["style_version"], **baseline,
                "icons": sorted(icons, key=lambda i: i["id"])}
    # An icon that lost its master or inventory entry leaves its exported files behind; remember them (with
    # their hashes) so export_assets can remove the untouched ones and flag the hand-edited ones.
    kept_ids = {i["id"] for i in icons}
    orphans = {e["path"]: e for e in (previous or {}).get("orphaned_exports", [])}
    for pid, p in prev_icons.items():
        if pid not in kept_ids:
            orphans.update({e["path"]: e for e in p["exports"] + p.get("stale_exports", [])})
    if orphans:
        manifest["orphaned_exports"] = sorted(orphans.values(), key=lambda e: e["path"])
    if persist:
        if changed:
            log_event(set_dir, "geometry", changed, "asset hash changed since the previous manifest; "
                      "structural and visual QA reset, exports cleared")
        save(set_dir, manifest)
    return manifest


def current_baseline(spec: dict) -> dict:
    return {"style_hashes": {"geometry": style_spec.geometry_hash(spec), "palette": style_spec.palette_hash(spec)},
            "toolchain": {"renderer": "resvg", "renderer_version": _renderer_version()}}


def _renderer_version() -> str:
    try:
        return resvg_version()
    except ToolError:
        return "unavailable"


def set_structural(set_dir: Path, results: dict[str, tuple[str, str]]) -> dict:
    """results: id -> (passed|failed, report path). Called by validate_icons after source QA."""
    manifest = sync(set_dir)
    for icon in manifest["icons"]:
        if icon["id"] in results:
            status, report = results[icon["id"]]
            icon["qa"]["structural"] = status
            icon["qa"]["reports"] = sorted(set(icon["qa"].get("reports", [])) | {report})
            icon["status"] = derive_status(icon["qa"])
    save(set_dir, manifest)
    return manifest


def set_exports(set_dir: Path, exports_by_id: dict[str, list[dict]], keep_stale_kinds: set[str] | None = None) -> dict:
    """Replace the current exports of the given icons. Stale entries are dropped once refreshed, except for
    kinds outside the refreshed scope, which stay stale until they are exported again."""
    manifest = load(set_dir)
    if manifest is None:
        raise ToolError(EXIT_INPUT, "manifest.json missing; run manifest.py sync", str(path_for(set_dir)))
    keep = set(keep_stale_kinds or ())
    left = [e for e in manifest.get("orphaned_exports", []) if e["kind"] in keep]
    if left:
        manifest["orphaned_exports"] = left
    else:
        manifest.pop("orphaned_exports", None)
    for icon in manifest["icons"]:
        if icon["id"] in exports_by_id:
            icon["exports"] = sorted(exports_by_id[icon["id"]], key=lambda e: e["path"])
            now = {e["path"] for e in icon["exports"]}
            stale = [e for e in icon.get("stale_exports", []) if e["kind"] in keep and e["path"] not in now]
            if stale:
                icon["stale_exports"] = stale
            else:
                icon.pop("stale_exports", None)
    save(set_dir, manifest)
    return manifest


def reject(set_dir: Path, ids: list[str], reviewer: str) -> dict:
    manifest = sync(set_dir)
    known = {i["id"] for i in manifest["icons"]}
    unknown = sorted(set(ids) - known)
    if unknown:
        raise ToolError(EXIT_INPUT, f"no master/manifest entry for: {', '.join(unknown)}")
    for icon in manifest["icons"]:
        if icon["id"] in ids:
            icon["qa"]["visual"], icon["qa"]["reviewer_type"] = "rejected", reviewer
            icon["status"] = derive_status(icon["qa"])
            retire_exports(icon)
    save(set_dir, manifest)
    return manifest


def bump(set_dir: Path, part: str, note: str, ids: list[str]) -> str:
    manifest = sync(set_dir)
    major, minor, patch = (int(x) for x in manifest["asset_set_version"].split("."))
    major, minor, patch = {"major": (major + 1, 0, 0), "minor": (major, minor + 1, 0),
                           "patch": (major, minor, patch + 1)}[part]
    version = f"{major}.{minor}.{patch}"
    manifest["asset_set_version"] = version
    save(set_dir, manifest)
    log = Path(set_dir) / "CHANGELOG.md"
    head = log.read_text(encoding="utf-8") if log.exists() else f"# Changelog: {manifest['set_id']}\n"
    today = datetime.date.today().isoformat()
    entry = f"\n## {version} ({today})\n\n- {note}\n" + (f"- Icons: {', '.join(sorted(ids))}\n" if ids else "")
    atomic_write(log, (head.rstrip("\n") + "\n" + entry).encode("utf-8"))
    return version


def summarize(manifest: dict) -> dict:
    counts: dict[str, int] = {}
    for icon in manifest["icons"]:
        counts[icon["status"]] = counts.get(icon["status"], 0) + 1
    return {"set_id": manifest["set_id"], "version": manifest["asset_set_version"], "icons": len(manifest["icons"]),
            "status": counts, "eligible": sorted(i["id"] for i in manifest["icons"] if i["status"] == "eligible")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("sync", "status", "reject", "bump"):
        p = sub.add_parser(name)
        p.add_argument("--set", dest="set_dir", required=True)
        p.add_argument("--json", action="store_true")
        if name in ("reject", "bump"):
            p.add_argument("--ids", default="")
        if name == "reject":
            p.add_argument("--reviewer", choices=["user", "agent"], required=True)
        if name == "bump":
            p.add_argument("--part", choices=["patch", "minor", "major"], required=True)
            p.add_argument("--note", required=True)
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    ids = [i.strip() for i in getattr(args, "ids", "").split(",") if i.strip()]
    if args.cmd == "sync":
        result = summarize(sync(set_dir))
    elif args.cmd == "status":
        m = load(set_dir)
        if m is None:
            raise ToolError(EXIT_INPUT, "manifest.json missing; run manifest.py sync", str(path_for(set_dir)))
        result = summarize(m)
    elif args.cmd == "reject":
        result = summarize(reject(set_dir, ids, args.reviewer))
    else:
        result = {"version": bump(set_dir, args.part, args.note, ids)}
    emit(result, args.json, " ".join(f"{k}={v}" for k, v in result.items()))
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
