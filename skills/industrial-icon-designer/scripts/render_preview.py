#!/usr/bin/env python3
"""Offline preview: reference/new pairs, Light/Dark, normal/disabled, plus UI-context simulations.

    render_preview.py --set DIR [--scope pilot|all] [--json]

Outputs under DIR/preview/: index.html, contexts/desktop.html, contexts/web.html, renders/**.png.
Rendering uses only the pinned resvg renderer. Pages have no external resources, escape every
label, and only embed master SVGs that passed the hardened-parser checks. Contexts are
simulations and say so on the page; they are not the target application.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from PIL import Image

import approvals
import palette
import run_state
import style_spec
from common import (EXIT_INPUT, EXIT_OK, ToolError, atomic_write, emit, ensure_inside, escape_html, load_json, parse_svg,
                    recolor_svg, render_many, render_svg, run_main, svg_findings, timed, write_json)

ENLARGED_PX = 128
SIM_BANNER = "SIMULATION: standalone mock-up, not the actual application. It does not count as application validation."

CSS = """
*{box-sizing:border-box}body{font:14px/1.45 system-ui,sans-serif;margin:0;padding:24px;background:#f1f5f9;color:#0f172a}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}h3{font-size:14px;margin:0}
.banner{background:#fff7ed;border:1px solid #fdba74;padding:8px 12px;border-radius:6px;margin:12px 0}
.badge{font-size:11px;padding:1px 6px;border-radius:9px;margin-left:6px;border:1px solid #94a3b8}
.badge.approved{background:#dcfce7;border-color:#16a34a}.badge.draft{background:#fef9c3;border-color:#ca8a04}
.badge.missing{background:#fee2e2;border-color:#dc2626}
section.icon{background:#fff;border:1px solid #cbd5e1;border-radius:8px;padding:12px;margin:12px 0}
table{border-collapse:collapse}td,th{padding:6px 10px;border:1px solid #e2e8f0;text-align:center;font-size:12px}
.pair{display:inline-flex;gap:6px;align-items:center}.pair img{image-rendering:pixelated}
.meta{color:#475569;font-size:12px;margin:2px 0 8px}.ok{color:#15803d}.bad{color:#b91c1c}
.panel{border:1px solid #cbd5e1;border-radius:8px;padding:12px;margin:10px 0;display:inline-block;vertical-align:top;min-width:280px}
.panel.light{background:var(--lbg);color:var(--lfg)}.panel.dark{background:var(--dbg);color:var(--dfg)}
.row{display:flex;align-items:center;gap:8px;padding:3px 0}.strip{display:flex;gap:6px;padding:4px 0}
.btn{display:inline-flex;align-items:center;justify-content:center;padding:4px}.dis{color:var(--dis)}
.ribbon{display:flex;gap:18px}.group{border-right:1px solid rgba(128,128,128,.4);padding-right:14px}
.group .big{display:flex;flex-direction:column;align-items:center;gap:2px;font-size:11px}
.ico{display:inline-block;width:var(--s);height:var(--s)}.ico svg{width:100%;height:100%;display:block}
"""


def page(title: str, body: str, extra_css: str = "") -> str:
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><title>{escape_html(title)}</title>'
            f"<style>{CSS}{extra_css}</style></head><body>{body}</body></html>\n")


def theme_vars(spec: dict) -> str:
    t = spec["themes"]
    light, dark = t.get("light"), t.get("dark")
    parts = []
    if light:
        parts.append(f"--lbg:{light['background']};--lfg:{light['normal']};")
    if dark:
        parts.append(f"--dbg:{dark['background']};--dfg:{dark['normal']};")
    return ":root{" + "".join(parts) + "}"


def load_master(set_dir: Path, icon_id: str, size: int, small_sizes: list[int]) -> tuple[str, str] | None:
    """Return (svg_text, kind) for the source drawn at this size, or None if absent/unsafe."""
    variant = set_dir / "variants" / "small" / f"{icon_id}.svg"
    master = set_dir / "masters" / f"{icon_id}.svg"
    path, kind = (variant, "small-variant") if (size in small_sizes and variant.is_file()) else (master, "master")
    if not path.is_file():
        return None
    data = path.read_bytes()
    try:
        findings = svg_findings(parse_svg(data, str(path)))
    except ToolError:
        return None
    return (data.decode("utf-8"), kind) if not findings else None


def render_reference(set_dir: Path, icon: dict, size: int, out: Path) -> bool:
    ref = icon["references"][0]
    path = (set_dir / ref["path"]).resolve()
    if not path.is_file():
        return False
    if ref["kind"] == "svg":
        data = path.read_bytes()
        try:
            if svg_findings(parse_svg(data, str(path), strict_markup=False)):
                return False
        except ToolError:
            return False
        render_svg(data, out, size)
        return True
    with Image.open(path) as im:
        im = im.convert("RGBA")
        scale = min(size / im.width, size / im.height)
        resized = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, format="PNG", optimize=False)
    return True


def inline_svg(svg_text: str, size_var: str) -> str:
    body = re.sub(r"<\?xml[^>]*\?>", "", svg_text)
    body = re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", body)
    return f'<span class="ico" style="--s:{size_var}">{body.strip()}</span>'


def scope_icons(set_dir: Path, scope: str, inv: dict) -> list[dict]:
    if scope == "pilot" and (set_dir / "brief.json").exists():
        ids = set(load_json(set_dir / "brief.json").get("sample_ids") or [])
        if ids:
            return [i for i in inv["icons"] if i["id"] in ids]
    return list(inv["icons"])


def build(set_dir: Path, scope: str) -> dict:
    ensure_inside(set_dir, "masters", "variants", "preview", "reports")
    spec = style_spec.load_spec(set_dir)
    inv = load_json(set_dir / "inventory.json")
    icons = scope_icons(set_dir, scope, inv)
    if not icons:
        raise ToolError(EXIT_INPUT, "no icons in scope", str(set_dir / "inventory.json"))
    sizes = spec["preview_sizes_px"]
    small = spec["small_variant_sizes_px"]
    prev = set_dir / "preview"
    shutil.rmtree(prev / "renders", ignore_errors=True)

    try:
        gate = approvals.evaluate(set_dir, "pilot")
    except ToolError:
        gate = {"valid": False, "scope": []}
    approved_ids = set(gate.get("scope", [])) if gate["valid"] else set()

    report = palette.contrast_report(spec)
    write_json(set_dir / "reports" / "contrast.json", report)

    sections, missing, rendered, jobs = [], [], [], []
    for icon in icons:
        iid = icon["id"]
        have_master = (set_dir / "masters" / f"{iid}.svg").is_file()
        badge = ("approved" if iid in approved_ids else "draft") if have_master else "missing"
        label = {"approved": "approved", "draft": "draft (pending approval)", "missing": "no master yet"}[badge]
        rows = []
        for theme, tokens in sorted(spec["themes"].items()):
            for state in spec["states"]:
                color = tokens["normal" if state == "normal" else "disabled"]
                cells = []
                for size in sizes:
                    ref_png = prev / "renders" / "reference" / str(size) / f"{iid}.png"
                    if not ref_png.exists():
                        render_reference(set_dir, icon, size, ref_png)
                    ref_html = (f'<img alt="reference" width="{size}" height="{size}" '
                                f'src="renders/reference/{size}/{iid}.png">') if ref_png.exists() else "n/a"
                    new_html = "n/a"
                    src = load_master(set_dir, iid, size, small) if have_master else None
                    if src:
                        out = prev / "renders" / theme / state / str(size) / f"{iid}.png"
                        jobs.append((recolor_svg(src[0], color).encode(), out, size))
                        new_html = (f'<img alt="redrawn {escape_html(iid)} ({src[1]})" width="{size}" height="{size}" '
                                    f'src="renders/{theme}/{state}/{size}/{iid}.png">')
                        rendered.append((iid, theme, state, size))
                    cells.append(f'<td style="background:{tokens["background"]}"><span class="pair">{ref_html}{new_html}</span></td>')
                big = "n/a"
                src = load_master(set_dir, iid, ENLARGED_PX, small) if have_master else None
                if src:
                    out = prev / "renders" / theme / state / "enlarged" / f"{iid}.png"
                    jobs.append((recolor_svg(src[0], color).encode(), out, ENLARGED_PX))
                    big = f'<img alt="enlarged supplement" width="{ENLARGED_PX}" height="{ENLARGED_PX}" src="renders/{theme}/{state}/enlarged/{iid}.png">'
                cells.append(f'<td style="background:{tokens["background"]}">{big}</td>')
                rows.append(f"<tr><th>{escape_html(theme)} / {escape_html(state)}</th>{''.join(cells)}</tr>")
        head = "".join(f"<th>{s}px<br>ref | new</th>" for s in sizes) + "<th>enlarged<br>(supplement)</th>"
        sections.append(
            f'<section class="icon" id="{escape_html(iid)}"><h3>{escape_html(iid)}<span class="badge {badge}">{label}</span></h3>'
            f'<div class="meta">{escape_html(icon["meaning"])} | {escape_html(icon["functional_group"])} | '
            f'{escape_html(icon["semantic_role"])}</div><table><tr><th></th>{head}</tr>{"".join(rows)}</table></section>')
        if not have_master:
            missing.append(iid)

    render_many(jobs)
    contrast_rows = "".join(
        f"<tr><td>{escape_html(n)}</td><td>{t['normal']['ratio']}:1 <span class=\"{'ok' if t['normal']['passes'] else 'bad'}\">"
        f"{'pass' if t['normal']['passes'] else 'FAIL'} (needs {t['normal']['required']}:1)</span></td>"
        f"<td>{t['disabled']['ratio']}:1 (reported only)</td></tr>" for n, t in report["themes"].items())
    palette_note = ("<div class=\"banner\">Palette is provisional and not the official brand palette; it needs review.</div>"
                    if spec["palette_status"] != "approved" else "")
    body = (f"<h1>Icon preview: {escape_html(spec['set_id'])}</h1>"
            f'<div class="meta">Style {escape_html(spec["style_version"])} | grid {spec["grid"]} | stroke {spec["stroke_width"]} | '
            f'{len(icons)} icons in scope ({escape_html(scope)})</div>{palette_note}'
            f'<div class="banner">Views are shown at actual size; the enlarged column is a supplement only. '
            f'Contexts: <a href="contexts/desktop.html">Desktop simulation</a> | <a href="contexts/web.html">Web simulation</a></div>'
            f"<h2>Contrast (token level)</h2><table><tr><th>Theme</th><th>Normal</th><th>Disabled</th></tr>{contrast_rows}</table>"
            f"<h2>Icons</h2>{''.join(sections)}")
    atomic_write(prev / "index.html", page(f"Preview {spec['set_id']}", body).encode("utf-8"))
    build_contexts(set_dir, spec, [i for i in icons if i["id"] not in missing])
    return {"icons": len(icons), "rendered_images": len(rendered), "missing_masters": missing,
            "contrast_passes": report["passes"], "index": str(prev / "index.html")}


def build_contexts(set_dir: Path, spec: dict, icons: list[dict]) -> None:
    small = spec["small_variant_sizes_px"]
    ctx = set_dir / "preview" / "contexts"

    def svg_of(iid, size):
        got = load_master(set_dir, iid, size, small)
        return inline_svg(got[0], f"{size}px") if got else ""

    names = {i["id"]: i["meaning"] for i in icons}
    ids = [i["id"] for i in icons]
    disabled_id = ids[len(ids) // 2] if ids else None

    def panel(theme, inner):
        return f'<div class="panel {theme}" style="--dis:{spec["themes"][theme]["disabled"]}">{inner}</div>'

    def desktop_panels():
        out = []
        for theme in ("light", "dark"):
            if theme not in spec["themes"]:
                continue
            toolbar = "".join(f'<span class="btn {"dis" if i == disabled_id else ""}">{svg_of(i, 24)}</span>' for i in ids[:8])
            menu = "".join(f'<div class="row {"dis" if i == disabled_id else ""}">{svg_of(i, 16)}<span>{escape_html(names[i])}</span></div>'
                           for i in ids[:6])
            ribbon = (f'<div class="ribbon"><div class="group"><div class="strip">'
                      + "".join(f'<span class="big">{svg_of(i, 32)}<span>{escape_html(i)}</span></span>' for i in ids[:3])
                      + '</div></div><div class="group">'
                      + "".join(f'<div class="row">{svg_of(i, 16)}<span>{escape_html(i)}</span></div>' for i in ids[3:6])
                      + "</div></div>")
            devices = "".join(f'<div class="row {"dis" if i == disabled_id else ""}">{svg_of(i, 16)}<span>{escape_html(i)}</span>'
                              f'<span style="margin-left:auto;opacity:.6">{"offline" if i == disabled_id else "online"}</span></div>'
                              for i in ids[-5:])
            out.append(panel(theme, f"<h3>Toolbar (24px)</h3><div class='strip'>{toolbar}</div>"
                                    f"<h3>Menu (16px)</h3>{menu}<h3>Ribbon-like (32px / 16px)</h3>{ribbon}"
                                    f"<h3>Device list (16px)</h3>{devices}"))
        return "".join(out)

    def web_panels():
        out = []
        for theme in ("light", "dark"):
            if theme not in spec["themes"]:
                continue
            nav = "".join(f'<div class="row">{svg_of(i, 24)}<span>{escape_html(i)}</span></div>' for i in ids[:6])
            actions = "".join(f'<span class="btn {"dis" if i == disabled_id else ""}">{svg_of(i, 20)}</span>' for i in ids[:6])
            lst = "".join(f'<div class="row {"dis" if i == disabled_id else ""}">{svg_of(i, 16)}<span>{escape_html(names[i])}</span></div>'
                          for i in ids[-5:])
            out.append(panel(theme, f"<h3>Navigation (24px, inline SVG)</h3>{nav}<h3>Actions (20px)</h3>"
                                    f"<div class='strip'>{actions}</div><h3>List (16px)</h3>{lst}"))
        return "".join(out)

    css = theme_vars(spec)
    for name, builder in (("desktop", desktop_panels), ("web", web_panels)):
        body = (f"<h1>{name.capitalize()} context simulation</h1><div class=\"banner\">{escape_html(SIM_BANNER)}</div>"
                f'<p class="meta"><a href="../index.html">Back to preview</a></p>{builder()}')
        atomic_write(ctx / f"{name}.html", page(f"{name} simulation", body, css).encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="set_dir", required=True)
    ap.add_argument("--scope", choices=["pilot", "all"], default="pilot")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    with timed(set_dir, "preview-render"):
        result = build(set_dir, args.scope)
    if args.scope == "pilot" and not result["missing_masters"]:
        spec = style_spec.load_spec(set_dir)
        run_state.advance(set_dir, spec["set_id"], "PILOT_READY")
    emit(result, args.json, f"preview written: {result['index']} ({result['icons']} icons, "
                            f"{len(result['missing_masters'])} without master)")
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
