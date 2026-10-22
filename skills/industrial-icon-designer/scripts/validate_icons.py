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

import consistency
import manifest as manifest_mod
import palette
import run_state
import style_spec
import upstream_adapter
from common import (EXIT_DEPENDENCY, EXIT_OK, EXIT_VALIDATION, ToolError, emit, ensure_inside, is_within, load_json, parse_svg,
                    recolor_svg, render_svg, run_main, svg_findings, svg_viewbox, timed, write_json, ACCENT_PAINT)

DRAWABLE = {"path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}
COLOR_VALUE = re.compile(r"^\s*(#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|[a-zA-Z]+)\s*$")
KEBAB_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
THEME_SAFE = {"none", "currentcolor", "inherit", "transparent", ACCENT_PAINT.lower()}
REPORT = "reports/pre-export-qa.json"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def check_svg(path: Path, grid: int, root_dir: Path | None = None, spec: dict | None = None,
              mode: str | None = None) -> tuple[list[str], list[str]]:
    """Local structural checks for one master or variant file. With a spec, the icon is also judged against
    its style mode (`mode` overrides the mode of the set, for example for a filled variant)."""
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
    if spec is not None and not errors:
        mode_errors, mode_warnings = consistency.split(consistency.icon_findings(root, spec, mode))
        errors += mode_errors
        warnings += mode_warnings
    return errors, warnings


def validate_source(set_dir: Path, project_root: Path, lock_path: Path | None, ids: list[str] | None) -> dict:
    set_dir = Path(set_dir)
    ensure_inside(set_dir, "masters", "variants", "reports")
    spec = style_spec.load_spec(set_dir)
    grid = spec["grid"]
    inv_by_id = {i["id"]: i for i in load_json(set_dir / "inventory.json")["icons"]}
    inv_ids = set(inv_by_id)
    spec_findings = consistency.spec_findings(spec)
    spec_errors, spec_warnings = consistency.split(spec_findings)
    masters = sorted((set_dir / "masters").glob("*.svg")) if (set_dir / "masters").is_dir() else []
    if ids:
        masters = [m for m in masters if m.stem in ids]
    results: dict[str, dict] = {}
    for m in masters:
        base_id, variant_problem = _variant_base(m.stem, inv_by_id)
        mode = "filled" if base_id else None
        errors, warnings = check_svg(m, grid, set_dir, spec, mode)
        if variant_problem:
            errors.append(variant_problem)
        errors += [f"style spec: {e}" for e in spec_errors]
        warnings += [f"style spec: {w}" for w in spec_warnings]
        if m.stem not in inv_ids:
            errors.append("master has no inventory entry (unknown id)")
        if base_id:
            pair_errors, pair_warnings = _variant_pair(set_dir, m, base_id, grid, spec)
            errors += pair_errors
            warnings += pair_warnings
        variant = set_dir / "variants" / "small" / m.name
        if variant.is_file():
            v_errors, v_warnings = check_svg(variant, grid, set_dir, spec, mode)
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
                    # a filled variant legitimately measures larger than the mostly-outline median; the
                    # pair rule (variant-bounds-parity) compares it with its own base instead
                    is_variant = _variant_base(r["icon"], inv_by_id)[0] is not None
                    results[r["icon"]]["errors"] += [f"consistency: {e}" for e in r["errors"]]
                    results[r["icon"]]["warnings"] += [f"consistency: {w}" for w in r["warnings"]
                                                       if not (is_variant and "envelope" in w)]
        except ToolError as exc:
            if exc.code != EXIT_DEPENDENCY:
                raise
            blocked = exc.message

    for r in results.values():
        r["status"] = "failed" if r["errors"] else "passed"
    report = {"phase": "source", "grid": grid, "style_version": spec["style_version"],
              "icons": dict(sorted(results.items())), "contrast": palette.contrast_report(spec),
              "style_mode": style_spec.style_mode(spec),
              "consistency": {"spec": spec_findings, "overrides": consistency.overrides(spec)},
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


def _variant_base(icon_id: str, inv_by_id: dict) -> tuple[str | None, str | None]:
    """The base id of a filled variant and, instead, the problem with a variant_of that cannot be trusted
    (not an id, itself, missing, or a variant of a variant)."""
    base = inv_by_id.get(icon_id, {}).get("variant_of")
    if base is None:
        return None, None
    if not isinstance(base, str) or not KEBAB_ID.match(base):
        return None, f"variant_of {base!r} is not an icon id"
    if base == icon_id:
        return None, "variant_of names the icon itself"
    if base not in inv_by_id:
        return None, f"variant_of {base} is not in the inventory"
    if inv_by_id[base].get("variant_of"):
        return None, f"variant_of {base} is itself a variant; a variant belongs to an outline icon"
    return base, None


def _secondary_layer_problem(item: dict, size: int) -> str | None:
    """Render the master with its fill-opacity removed. If the exported PNG shows no alpha difference from
    that opaque render, the renderer dropped the translucent layer."""
    import tempfile

    from PIL import Image, ImageChops

    text = item["source"].read_text(encoding="utf-8")
    if "fill-opacity" not in text:
        return None  # a filled variant or an outline-only master has no secondary layer to lose
    opaque = re.sub(r'\sfill-opacity="[^"]*"', "", text)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "opaque.png"
        render_svg(recolor_svg(opaque, item["color"], item.get("accent")).encode(), out, size)
        with Image.open(out) as flat, Image.open(item["_png"]) as actual:
            diff = ImageChops.difference(flat.convert("RGBA").getchannel("A"), actual.convert("RGBA").getchannel("A"))
            if diff.point(lambda a: 255 if a >= 16 else 0).getbbox() is None:
                return "the translucent secondary layer is missing (fill-opacity lost in rendering)"
    return None


def _variant_pair(set_dir: Path, variant: Path, base_id: str, grid: int, spec: dict) -> tuple[list[str], list[str]]:
    """A filled variant needs its base master, and must occupy the same box as it."""
    base = set_dir / "masters" / f"{base_id}.svg"
    if not base.is_file():
        return [f"variant of {base_id} but masters/{base_id}.svg does not exist"], []
    try:
        return consistency.split(consistency.variant_findings(base.read_bytes(), variant.read_bytes(), grid, spec))
    except ToolError as exc:
        if exc.code != EXIT_DEPENDENCY:
            raise
        return [], [f"variant bounds not checked: {exc.message}"]


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
            if style_spec.style_mode(spec) == "duotone":
                problem = _secondary_layer_problem({**item, "_png": path}, size)
                if problem:
                    errs.append(problem)
            want = tuple(int(item["color"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            # Edge pixels are partly transparent and their color is rounded when alpha is un-premultiplied,
            # so judge the alpha-weighted mean color of all content against the palette token.
            px = im.load()
            uses_accent = bool(item.get("accent")) and ACCENT_PAINT in item["source"].read_text(encoding="utf-8")
            if uses_accent:
                # two tokens: every fully opaque pixel must be one of them (edges are blends and are skipped)
                allowed = [want, tuple(int(item["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))]
                stray = sum(1 for y in range(h) for x in range(w) if px[x, y][3] == 255
                            and all(max(abs(px[x, y][c] - tok[c]) for c in range(3)) > 8 for tok in allowed))
                if stray:
                    errs.append(f"{stray} opaque pixel(s) match neither the {item['theme']}/{item['state']} token "
                                f"{item['color']} nor the accent {item['accent']}")
            else:
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
            jobs.append((recolor_svg(item["source"].read_text(encoding="utf-8"), item["color"],
                                     item.get("accent")).encode(), out,
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
