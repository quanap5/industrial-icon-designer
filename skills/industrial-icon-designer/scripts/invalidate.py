#!/usr/bin/env python3
"""Invalidation: apply the SRS change table and detect drift that needs it.

    invalidate.py detect --set DIR [--apply] [--json]
    invalidate.py apply  --set DIR --change reference|geometry|style|palette|renderer|usage [--ids a,b] [--reason T]

| change   | effect                                                                              |
| reference| review of the affected icons is voided                                              |
| geometry | visual + structural review, exports and application evidence of the icons reset      |
| style    | pilot approval goes stale; every icon's review, exports and evidence reset           |
| palette  | color review and themed exports/evidence reset; geometry approvals stay valid        |
| renderer | raster exports and the checks on them reset                                          |
| usage    | exports and evidence of the affected icons reset                                     |

Stale approval hashes are never accepted (see approvals.py). History is only appended to
reports/invalidation-log.jsonl; nothing recorded earlier is deleted or rewritten.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import app_validation
import manifest as manifest_mod
import run_state
import style_spec
from common import (EXIT_INPUT, EXIT_OK, ToolError, emit, load_json, log_event, resvg_version, run_main)

CHANGES = ["reference", "geometry", "style", "palette", "renderer", "usage"]
RERUN = {
    "reference": ["review", "render_preview", "export_assets"],
    "geometry": ["validate_icons --phase source", "approvals", "render_preview", "export_assets",
                 "validate_icons --phase exported", "validate-app"],
    "style": ["validate_icons --phase source", "render_preview", "approvals (pilot)", "export_assets",
              "validate_icons --phase exported", "validate-app"],
    "palette": ["palette review", "render_preview", "export_assets", "validate_icons --phase exported",
                "validate-app"],
    "renderer": ["render_preview", "export_assets", "validate_icons --phase exported"],
    "usage": ["export_assets", "validate_icons --phase exported", "validate-app"],
}
# earliest normal stage each change returns the run to (only when the run is already past it)
REWIND = {"style": "PILOT_READY", "palette": "SOURCE_QA_PASSED", "renderer": "SOURCE_QA_PASSED"}


def _select(manifest: dict, ids: list[str] | None, removed: set[str]) -> list[dict]:
    chosen = [i for i in manifest["icons"] if ids is None or i["id"] in ids]
    if ids is not None:
        unknown = sorted(set(ids) - {i["id"] for i in manifest["icons"]} - removed)
        if unknown:
            raise ToolError(EXIT_INPUT, f"no manifest entry for: {', '.join(unknown)}")
    return chosen


def apply(set_dir: Path, change: str, ids: list[str] | None, reason: str | None) -> dict:
    set_dir = Path(set_dir)
    manifest = manifest_mod.sync(set_dir)  # picks up hash-detected geometry changes first
    approvals_count = len(manifest_mod.load_approvals(set_dir))
    # icons that lost their master or inventory entry are no longer in the manifest; export_assets cleans their files
    removed = {Path(e["path"]).stem for e in manifest.get("orphaned_exports", [])}
    affected = _select(manifest, ids, removed)
    touched = [i["id"] for i in affected]
    note = reason or f"{change} change"

    inventory = {i["id"]: i for i in load_json(set_dir / "inventory.json")["icons"]}
    for icon in affected:
        qa = icon["qa"]
        src = inventory.get(icon["id"])
        if src and change in ("reference", "usage"):  # consume the changed baseline
            ref = src["references"][0]
            icon["sizes_px"], icon["source_path"], icon["source_sha256"] = src["sizes_px"], ref["path"], ref["sha256"]
        if change == "reference":
            qa["review_void_after"] = approvals_count
            qa["visual"], qa["reviewer_type"] = "pending", "none"
        elif change == "geometry":
            qa["structural"], qa["visual"], qa["reviewer_type"] = "pending", "pending", "none"
            qa["review_void_after"] = approvals_count
            manifest_mod.retire_exports(icon)
        elif change == "style":
            qa["structural"], qa["visual"], qa["reviewer_type"] = "pending", "pending", "none"
            qa["review_void_after"] = approvals_count
            manifest_mod.retire_exports(icon)
        elif change == "palette":
            qa["color_review"] = "pending"
            manifest_mod.retire_exports(icon)
        elif change == "renderer":
            manifest_mod.retire_exports(icon, {"desktop-png"})
        elif change == "usage":
            manifest_mod.retire_exports(icon)
        icon["status"] = manifest_mod.derive_status(qa)

    # consume the drift so it is not reported twice
    spec = style_spec.load_spec(set_dir)
    base = manifest_mod.current_baseline(spec)
    if change == "style":
        manifest["style_hashes"]["geometry"] = base["style_hashes"]["geometry"]
    if change in ("style", "palette"):
        manifest["style_hashes"]["palette"] = base["style_hashes"]["palette"]
        manifest["style_version"] = spec["style_version"]
    if change == "renderer":
        manifest["toolchain"] = base["toolchain"]
    manifest_mod.save(set_dir, manifest)

    app_ids = None if change in ("style", "palette", "renderer") else touched
    reset = app_validation.reset_contexts(set_dir, app_ids, note)
    if change in REWIND:
        state = run_state.load(set_dir)
        if run_state.stage_index(state["last_valid_stage"]) > run_state.stage_index(REWIND[change]):
            run_state.rewind(set_dir, REWIND[change], f"{change} change: {note}")
    log_event(set_dir, change, touched, note)
    return {"change": change, "icons": touched, "removed_icons": sorted(removed & set(ids or removed)),
            "application_contexts_reset": reset, "rerun": RERUN[change]}


def detect(set_dir: Path) -> dict:
    """Drift between the recorded baseline and the current files. Run before anything calls sync."""
    set_dir = Path(set_dir)
    manifest = manifest_mod.load(set_dir)
    if manifest is None:
        return {"changes": [], "note": "no manifest yet; nothing to compare"}
    spec = style_spec.load_spec(set_dir)
    inv = {i["id"]: i for i in load_json(set_dir / "inventory.json")["icons"]}
    found: dict[str, list[str] | None] = {}
    if manifest["style_hashes"]["geometry"] != style_spec.geometry_hash(spec):
        found["style"] = None
    if manifest["style_hashes"]["palette"] != style_spec.palette_hash(spec):
        found["palette"] = None
    try:
        renderer = resvg_version()
    except ToolError:
        renderer = "unavailable"
    if renderer != "unavailable" and manifest["toolchain"]["renderer_version"] != renderer:
        found["renderer"] = None  # an absent renderer is a dependency problem, not a changed renderer
    geometry, reference, usage = [], [], []
    for icon in manifest["icons"]:
        current = manifest_mod.combined_asset_hash(set_dir, icon["id"])
        if current != icon["qa"].get("asset_sha256"):
            geometry.append(icon["id"])
        src = inv.get(icon["id"])
        if src:
            if src["references"][0]["sha256"] != icon["source_sha256"]:
                reference.append(icon["id"])
            if sorted(src["sizes_px"]) != sorted(icon["sizes_px"]):
                usage.append(icon["id"])
    for name, ids in (("geometry", geometry), ("reference", reference), ("usage", usage)):
        if ids:
            found[name] = ids
    return {"changes": [{"change": k, "ids": v} for k, v in sorted(found.items())]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--set", dest="set_dir", required=True)
    d.add_argument("--apply", action="store_true")
    d.add_argument("--json", action="store_true")
    a = sub.add_parser("apply")
    a.add_argument("--set", dest="set_dir", required=True)
    a.add_argument("--change", choices=CHANGES, required=True)
    a.add_argument("--ids", default="")
    a.add_argument("--reason")
    a.add_argument("--json", action="store_true")
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    if args.cmd == "detect":
        result = detect(set_dir)
        if args.apply:
            result["applied"] = [apply(set_dir, c["change"], c["ids"], "detected drift") for c in result["changes"]]
        emit(result, args.json, f"{len(result['changes'])} change(s) detected: "
             + ", ".join(c["change"] for c in result["changes"]))
        return EXIT_OK
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] or None
    result = apply(set_dir, args.change, ids, args.reason)
    emit(result, args.json, f"{args.change}: reset {len(result['icons'])} icon(s)")
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
