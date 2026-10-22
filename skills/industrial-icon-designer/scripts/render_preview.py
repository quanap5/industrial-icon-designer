#!/usr/bin/env python3
"""Offline preview: reference/new pairs, Light/Dark, normal/disabled, plus UI-context simulations.

    render_preview.py --set DIR [--scope pilot|all] [--group a,b] [--json]

Outputs under DIR/preview/: index.html, contexts/{desktop,web,web-img}.html, renders/**.png (+ renders/web-img/**.svg).
The index compares reference (Before) and redrawn (After) with group, theme, state and size controls.
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
import preview_page
import run_state
import style_spec
from common import (EXIT_INPUT, EXIT_OK, ToolError, atomic_write, emit, ensure_inside, escape_html, load_json, parse_svg,
                    recolor_svg, render_many, render_svg, run_main, svg_findings, timed, write_json)

ENLARGED_PX = 128
CONTEXT_PROFILES = ("desktop", "web", "web-img")


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


def inline_svg(svg_text: str) -> str:
    body = re.sub(r"<\?xml[^>]*\?>", "", svg_text)
    return re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", body).strip()


def scope_icons(set_dir: Path, scope: str, inv: dict) -> list[dict]:
    if scope == "pilot" and (set_dir / "brief.json").exists():
        ids = set(load_json(set_dir / "brief.json").get("sample_ids") or [])
        if ids:  # a filled variant is reviewed beside its base, so it follows the base into the scope
            return [i for i in inv["icons"] if i["id"] in ids or i.get("variant_of") in ids]
    return list(inv["icons"])


def select_groups(icons: list[dict], requested: list[str] | None) -> list[dict]:
    """Narrow to the requested functional groups; an unknown name lists the valid ones."""
    if not requested:
        return icons
    valid = sorted({i["functional_group"] for i in icons})
    unknown = [g for g in requested if g not in valid]
    if unknown:
        raise ToolError(EXIT_INPUT, f"unknown group(s) {', '.join(unknown)}; valid groups: {', '.join(valid) or 'none'}")
    return [i for i in icons if i["functional_group"] in requested]


class Sources:
    """Image lookups for the page builders; everything it returns exists under preview/ or is None."""

    def __init__(self, set_dir: Path, prev: Path, small: list[int], have_master: set[str]):
        self.set_dir, self.prev, self.small, self.have_master = set_dir, prev, small, have_master
        self.kinds: dict[tuple[str, int], str] = {}

    def _rel(self, *parts) -> str | None:
        rel = "/".join(str(x) for x in parts)
        return rel if (self.prev / rel).is_file() else None

    def ref(self, iid, size):
        return self._rel("renders", "reference", size, f"{iid}.png")

    def png(self, iid, theme, state, size):
        return self._rel("renders", theme, state, size, f"{iid}.png")

    def big(self, iid, theme, state):
        return self._rel("renders", theme, state, "enlarged", f"{iid}.png")

    def master(self, iid, size):
        got = load_master(self.set_dir, iid, size, self.small) if iid in self.have_master else None
        if got:
            self.kinds[(iid, size)] = got[1]
        return got

    def alt(self, iid, size):
        if (iid, size) not in self.kinds:
            self.master(iid, size)
        return f"redrawn {iid} ({self.kinds.get((iid, size), 'master')})"

    def inline(self, iid, size):
        got = self.master(iid, size)
        return inline_svg(got[0]) if got else ""

    def webimg(self, iid, theme, state, size):
        got = self.master(iid, size)
        if not got:
            return None
        color, accent = palette.state_colors(self._tokens[theme], state)
        rel = f"renders/web-img/{theme}/{state}/{size}/{iid}.svg"
        atomic_write(self.prev / rel, recolor_svg(got[0], color, accent).encode("utf-8"))
        return rel


def build(set_dir: Path, scope: str, groups: list[str] | None = None) -> dict:
    ensure_inside(set_dir, "masters", "variants", "preview", "reports")
    spec = style_spec.load_spec(set_dir)
    inv = load_json(set_dir / "inventory.json")
    icons = select_groups(scope_icons(set_dir, scope, inv), groups)
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

    group_names = sorted({i["functional_group"] for i in icons})
    group_counts = [(g, sum(1 for i in icons if i["functional_group"] == g)) for g in group_names]
    entries, missing, rendered, jobs = [], [], [], []
    for icon in icons:
        iid = icon["id"]
        have_master = (set_dir / "masters" / f"{iid}.svg").is_file()
        badge = ("approved" if iid in approved_ids else "draft") if have_master else "missing"
        entries.append({"id": iid, "meaning": icon["meaning"], "group": icon["functional_group"], "role": icon["semantic_role"],
                        "g": group_names.index(icon["functional_group"]), "badge": badge, "have_master": have_master,
                        "form": "filled" if icon.get("variant_of") else style_spec.style_mode(spec),
                        "variant_of": icon.get("variant_of", "")})
        for size in sizes:
            ref_png = prev / "renders" / "reference" / str(size) / f"{iid}.png"
            if not ref_png.exists():
                render_reference(set_dir, icon, size, ref_png)
        for theme, tokens in sorted(spec["themes"].items()):
            for state in spec["states"]:
                color, accent = palette.state_colors(tokens, state)
                for size in sizes:
                    src = load_master(set_dir, iid, size, small) if have_master else None
                    if src:
                        jobs.append((recolor_svg(src[0], color, accent).encode(), prev / "renders" / theme / state / str(size) / f"{iid}.png", size))
                        rendered.append((iid, theme, state, size))
                src = load_master(set_dir, iid, ENLARGED_PX, small) if have_master else None
                if src:
                    jobs.append((recolor_svg(src[0], color, accent).encode(), prev / "renders" / theme / state / "enlarged" / f"{iid}.png", ENLARGED_PX))
        if not have_master:
            missing.append(iid)

    render_many(jobs)
    sources = Sources(set_dir, prev, small, {e["id"] for e in entries if e["have_master"]})
    sources._tokens = spec["themes"]
    contrast_rows = "".join(
        f"<tr><td>{escape_html(n)}</td><td>{t['normal']['ratio']}:1 <span class=\"{'ok' if t['normal']['passes'] else 'bad'}\">"
        f"{'pass' if t['normal']['passes'] else 'FAIL'} (needs {t['normal']['required']}:1)</span></td>"
        f"<td>{t['disabled']['ratio']}:1 (reported only)</td></tr>" for n, t in report["themes"].items())
    contrast_html = f"<table><tr><th>Theme</th><th>Normal</th><th>Disabled</th></tr>{contrast_rows}</table>"
    palette_note = ("<div class=\"banner\">Palette is provisional and not the official brand palette; it needs review.</div>"
                    if spec["palette_status"] != "approved" else "")
    atomic_write(prev / "index.html", preview_page.index_page(spec, entries, group_counts, scope, contrast_html,
                                                              palette_note, sources).encode("utf-8"))
    ready = [e for e in entries if e["have_master"]]
    for profile in CONTEXT_PROFILES:
        name = "desktop" if profile == "desktop" else profile
        atomic_write(prev / "contexts" / f"{name}.html",
                     preview_page.context_page(profile, spec, ready, group_counts, sources).encode("utf-8"))
    return {"icons": len(icons), "rendered_images": len(rendered), "missing_masters": missing,
            "groups": [{"name": g, "icons": n} for g, n in group_counts],
            "contrast_passes": report["passes"], "index": str(prev / "index.html")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="set_dir", required=True)
    ap.add_argument("--scope", choices=["pilot", "all"], default="pilot")
    ap.add_argument("--group", help="comma-separated functional groups to include (default: all groups in scope)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    with timed(set_dir, "preview-render"):
        groups = [g.strip() for g in args.group.split(",") if g.strip()] if args.group else None
        result = build(set_dir, args.scope, groups)
    if args.scope == "pilot" and not groups and not result["missing_masters"]:
        spec = style_spec.load_spec(set_dir)
        run_state.advance(set_dir, spec["set_id"], "PILOT_READY")
    emit(result, args.json, f"preview written: {result['index']} ({result['icons']} icons, "
                            f"{len(result['missing_masters'])} without master)")
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
