#!/usr/bin/env python3
"""Structural QA for masters and variants, and (later phase) QA of the exported files.

    validate_icons.py --set DIR --phase source   [--ids a,b] [--project-root DIR] [--json]
    validate_icons.py --set DIR --phase exported [--json]

Source QA runs local checks (hardened XML, forbidden constructs, geometry present, theming-safe
colors, grid viewBox) and the locked upstream consistency validator. It writes
reports/pre-export-qa.json and updates the manifest; failing icons are never export-eligible.
Exit codes: 0 pass, 3 a dependency blocks the check, 4 validation failures.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import manifest as manifest_mod
import palette
import run_state
import style_spec
import upstream_adapter
from common import (EXIT_DEPENDENCY, EXIT_OK, EXIT_VALIDATION, ToolError, emit, ensure_inside, is_within, load_json, parse_svg,
                    recolor_svg, run_main, svg_findings, svg_viewbox, timed, write_json)

DRAWABLE = {"path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}
COLOR_VALUE = re.compile(r"^\s*(#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|[a-zA-Z]+)\s*$")
THEME_SAFE = {"none", "currentcolor", "inherit", "transparent"}
REPORT = "reports/pre-export-qa.json"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def check_svg(path: Path, grid: int, root_dir: Path | None = None) -> tuple[list[str], list[str]]:
    """Local structural checks for one master or variant file."""
    errors: list[str] = []
    warnings: list[str] = []
    if root_dir is not None and path.is_symlink() and not is_within(path, root_dir):
        return ["symlink resolves outside the set directory"], warnings
    try:
        root = parse_svg(path.read_bytes(), str(path))
    except ToolError as exc:
        return [exc.message], warnings
    errors += svg_findings(root)
    vb = svg_viewbox(root)
    if vb != (0.0, 0.0, float(grid), float(grid)):
        errors.append(f"viewBox must be '0 0 {grid} {grid}'")
    for attr in ("width", "height"):
        if attr in root.attrib:
            errors.append(f"root {attr} attribute set; the viewBox alone sizes the icon")
    if not any(_local(el.tag) in DRAWABLE for el in root.iter()):
        errors.append("empty geometry: no drawable shape")
    for el in root.iter():
        for attr in ("fill", "stroke"):
            value = el.attrib.get(attr)
            if value is not None and value.strip().lower() not in THEME_SAFE:
                errors.append(f"fixed {attr} color '{value}' breaks theming (geometry must not carry palette)")
        if "style" in el.attrib and re.search(r"(fill|stroke)\s*:", el.attrib["style"]):
            errors.append("inline style sets fill/stroke; use presentation attributes with currentColor")
    stroke_ok = root.attrib.get("stroke", "").lower() == "currentcolor" or any(
        el.attrib.get("stroke", "").lower() == "currentcolor" for el in root.iter())
    fill_ok = any(el.attrib.get("fill", "").lower() == "currentcolor" for el in root.iter())
    if not (stroke_ok or fill_ok):
        warnings.append("no currentColor stroke or fill; the icon cannot take theme colors")
    return errors, warnings


def validate_source(set_dir: Path, project_root: Path, lock_path: Path | None, ids: list[str] | None) -> dict:
    set_dir = Path(set_dir)
    ensure_inside(set_dir, "masters", "variants", "reports")
    spec = style_spec.load_spec(set_dir)
    grid = spec["grid"]
    inv_ids = {i["id"] for i in load_json(set_dir / "inventory.json")["icons"]}
    masters = sorted((set_dir / "masters").glob("*.svg")) if (set_dir / "masters").is_dir() else []
    if ids:
        masters = [m for m in masters if m.stem in ids]
    results: dict[str, dict] = {}
    for m in masters:
        errors, warnings = check_svg(m, grid, set_dir)
        if m.stem not in inv_ids:
            errors.append("master has no inventory entry (unknown id)")
        variant = set_dir / "variants" / "small" / m.name
        if variant.is_file():
            v_errors, v_warnings = check_svg(variant, grid, set_dir)
            errors += [f"small variant: {e}" for e in v_errors]
            warnings += [f"small variant: {w}" for w in v_warnings]
        results[m.stem] = {"errors": errors, "warnings": warnings}

    blocked = None
    if masters:
        try:
            lock = upstream_adapter.load_lock(project_root, lock_path)
            upstream = upstream_adapter.validate_masters(set_dir / "masters", project_root, lock, spec,
                                                         ids if ids else None)
            for r in upstream["results"]:
                if r["icon"] in results:
                    results[r["icon"]]["errors"] += [f"consistency: {e}" for e in r["errors"]]
                    results[r["icon"]]["warnings"] += [f"consistency: {w}" for w in r["warnings"]]
        except ToolError as exc:
            if exc.code != EXIT_DEPENDENCY:
                raise
            blocked = exc.message

    for r in results.values():
        r["status"] = "failed" if r["errors"] else "passed"
    report = {"phase": "source", "grid": grid, "style_version": spec["style_version"],
              "icons": dict(sorted(results.items())), "contrast": palette.contrast_report(spec),
              "blocked": blocked,
              "summary": {"checked": len(results), "passed": sum(r["status"] == "passed" for r in results.values()),
                          "failed": sum(r["status"] == "failed" for r in results.values())}}
    write_json(set_dir / REPORT, report)

    if blocked:
        # local findings are recorded, but nothing may become eligible while the consistency check is blocked
        manifest_mod.sync(set_dir)
        failed_only = {i: ("failed", REPORT) for i, r in results.items() if r["errors"]}
        if failed_only:
            manifest_mod.set_structural(set_dir, failed_only)
        return report
    manifest_mod.set_structural(set_dir, {i: (r["status"], REPORT) for i, r in results.items()})
    _record_state(set_dir, spec["set_id"], results)
    return report


def _record_state(set_dir: Path, set_id: str, results: dict) -> None:
    failed = sorted(i for i, r in results.items() if r["status"] == "failed")
    if failed:
        run_state.fail(set_dir, "NEEDS_REVIEW", ",".join(failed),
                       f"{len(failed)} master(s) failed source QA: {', '.join(failed)}",
                       f"fix {', '.join(failed)}, then rerun validate_icons.py --phase source", "generate")
        return
    state = run_state.load(set_dir, set_id)
    approved_or_later = run_state.stage_index(state["last_valid_stage"]) >= run_state.stage_index("PILOT_APPROVED")
    if approved_or_later and not state["pending_ids"]:
        run_state.advance(set_dir, set_id, "SOURCE_QA_PASSED")


def _png_problems(path: Path, item: dict, spec: dict) -> list[str]:
    from PIL import Image
    errs = []
    try:
        with Image.open(path) as im:
            im.load()
            size = item["size_px"]
            if im.size != (size, size):
                return [f"PNG is {im.size[0]}x{im.size[1]}, expected {size}x{size}"]
            if im.mode != "RGBA":
                return [f"PNG mode is {im.mode}, expected RGBA"]
            alpha = im.getchannel("A")
            lo, hi = alpha.getextrema()
            if hi == 0:
                return ["PNG is fully transparent (no content)"]
            if lo != 0:
                errs.append("PNG has no transparent pixels (opaque background baked in)")
            w, h = im.size
            edges = [alpha.crop((0, 0, w, 1)), alpha.crop((0, h - 1, w, h)),
                     alpha.crop((0, 0, 1, h)), alpha.crop((w - 1, 0, w, h))]
            # antialiased strokes may graze the outer pixel (padding is measured to the path, not the paint);
            # strong coverage there means the drawing is cut off by the canvas
            if any(e.getextrema()[1] >= 128 for e in edges):
                errs.append("content touches the canvas edge (clipping)")
            want = tuple(int(item["color"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            # Edge pixels are partly transparent and their color is rounded when alpha is un-premultiplied,
            # so judge the alpha-weighted mean color of all content against the palette token.
            px = im.load()
            weight = sum(px[x, y][3] for y in range(h) for x in range(w))
            mean = [sum(px[x, y][3] * px[x, y][c] for y in range(h) for x in range(w)) / weight for c in range(3)]
            if max(abs(mean[c] - want[c]) for c in range(3)) > 8:
                errs.append(f"content color ({', '.join(str(round(m)) for m in mean)}) differs from the "
                            f"{item['theme']}/{item['state']} token {item['color']}")
    except Exception as exc:  # unreadable PNG
        return [f"unreadable PNG: {exc}"]
    return errs


def validate_exported(set_dir: Path) -> dict:
    """Inspect the generated files themselves, separately from source QA."""
    import tempfile

    import export_assets
    from common import render_many, resvg_version, sha256_file

    set_dir = Path(set_dir)
    manifest = manifest_mod.load(set_dir)
    if manifest is None:
        raise ToolError(EXIT_VALIDATION, "manifest.json missing; nothing to inspect", str(set_dir / "manifest.json"))
    spec = style_spec.load_spec(set_dir)
    renderer = resvg_version()
    entries = {e["path"]: (i["id"], e) for i in manifest["icons"] for e in i["exports"]}
    kinds = {"desktop-png", "web-inline"} | ({"web-img"} if any(e["kind"] == "web-img" for _, e in entries.values())
                                            else set())
    planned = export_assets.plan_outputs(set_dir, manifest, spec, kinds, renderer)
    results: dict[str, dict] = {i["id"]: {"errors": [], "warnings": []} for i in manifest["icons"]}

    for icon in manifest["icons"]:
        if icon["status"] != "eligible" and icon["exports"]:
            results[icon["id"]]["errors"].append("exports exist for an icon that is not export-eligible")
    expected_paths = set()
    rerender, jobs = [], []
    tmp = Path(tempfile.mkdtemp(prefix="post-export-"))
    for item in planned:
        res = results[item["id"]]
        expected_paths.add(item["path"])
        entry = entries.get(item["path"], (None, None))[1]
        final = set_dir / item["path"]
        if entry is None or not final.is_file():
            res["errors"].append(f"missing export: {item['path']}")
            continue
        if sha256_file(final) != entry["sha256"]:
            res["errors"].append(f"{item['path']}: file differs from the manifest (changed after export)")
            continue
        if entry["config_sha256"] != item["config_sha256"]:
            res["errors"].append(f"{item['path']}: stale export (source, palette, size or renderer changed)")
            continue
        if item["kind"] == "desktop-png":
            res["errors"] += [f"{item['path']}: {m}" for m in _png_problems(final, item, spec)]
            out = tmp / item["path"]
            jobs.append((recolor_svg(item["source"].read_text(encoding="utf-8"), item["color"]).encode(), out,
                         item["size_px"]))
            rerender.append((item, out, final))
        else:
            try:
                root = parse_svg(final.read_bytes(), item["path"])
                bad = svg_findings(root)
            except ToolError as exc:
                bad = [exc.message]
            text = final.read_text(encoding="utf-8")
            if bad:
                res["errors"].append(f"{item['path']}: " + "; ".join(bad))
            if item["kind"] == "web-inline" and ("currentColor" not in text or text.encode() != export_assets.svg_payload(item)):
                res["errors"].append(f"{item['path']}: inline SVG must equal the master and keep currentColor")
            if item["kind"] == "web-img" and ("currentColor" in text or item["color"] not in text.upper()):
                res["errors"].append(f"{item['path']}: resolved-color SVG must use {item['color']} and no currentColor")
    render_many(jobs)
    for item, expected, final in rerender:  # mapping: the file is exactly the icon it claims to be
        if expected.exists() and sha256_file(expected) != sha256_file(final):
            results[item["id"]]["errors"].append(f"{item['path']}: pixels differ from a fresh render of its source "
                                                 "(wrong icon, size or palette)")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    unknown = []
    if (set_dir / "exports").is_dir():
        for f in sorted((set_dir / "exports").rglob("*")):
            rel = f.relative_to(set_dir).as_posix()
            if f.is_file() and rel not in entries and not rel.startswith(("exports/.staging", "exports/.conflicts")) \
                    and rel != "exports/.journal.json":
                unknown.append(rel)
    for r in results.values():
        r["status"] = "failed" if r["errors"] else "passed"
    eligible = {i["id"] for i in manifest["icons"] if i["status"] == "eligible"}
    report = {"phase": "exported", "renderer": renderer, "checked_files": len(planned),
              "icons": dict(sorted(results.items())), "unknown_files": unknown,
              "summary": {"checked": len(results), "passed": sum(r["status"] == "passed" for r in results.values()),
                          "failed": sum(r["status"] == "failed" for r in results.values())}}
    write_json(set_dir / "reports" / "post-export-qa.json", report)
    failed = sorted(i for i, r in results.items() if r["status"] == "failed")
    if failed:
        run_state.fail(set_dir, "NEEDS_REVIEW", ",".join(failed), f"post-export QA failed for {', '.join(failed)}",
                       f"fix {', '.join(failed)}, then rerun export_assets.py and validate_icons.py --phase exported",
                       "export")
    else:
        inv_ids = {i["id"] for i in load_json(set_dir / "inventory.json")["icons"]}
        run_state.advance(set_dir, spec["set_id"], "POST_EXPORT_QA_PASSED")
        if eligible == inv_ids:
            run_state.advance(set_dir, spec["set_id"], "ASSETS_READY")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="set_dir", required=True)
    ap.add_argument("--phase", choices=["source", "exported"], required=True)
    ap.add_argument("--ids")
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--lock")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    with timed(set_dir, f"qa-{args.phase}"):
        if args.phase == "exported":
            report = validate_exported(set_dir)
        else:
            ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else None
            report = validate_source(set_dir, Path(args.project_root).resolve(),
                                     Path(args.lock) if args.lock else None, ids)
    emit(report, args.json,
         f"{report['phase']} QA: {report['summary']['passed']} passed, {report['summary']['failed']} failed")
    for icon_id, r in report["icons"].items():
        for e in r["errors"]:
            print(f"error: {icon_id}: {e}", file=__import__("sys").stderr)
    if report.get("blocked"):
        print(f"blocked: {report['blocked']}", file=__import__("sys").stderr)
        return EXIT_DEPENDENCY
    return EXIT_VALIDATION if report["summary"]["failed"] else EXIT_OK


if __name__ == "__main__":
    run_main(main)
