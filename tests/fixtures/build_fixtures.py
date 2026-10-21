#!/usr/bin/env python3
"""Generate the synthetic fixture set (clearly synthetic; not user artwork).

Writes into tests/fixtures/:
  references/   deliberately inconsistent "legacy" PNG/SVG icons
  masters/      industrial redraws (24 grid, currentColor strokes) used as pilot/batch artwork
  metadata.json, metadata.csv, style-spec.json
Run with the project environment; it is deterministic.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "skills" / "industrial-icon-designer" / "scripts"))
from common import render_svg, write_json  # noqa: E402

# id -> (path data, extra shapes, meaning, group, role, usage)
ICONS = {
    "save": ("M5 3h11l3 3v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2zM8 3v5h7V3M8 21v-6h8v6",
             "Save current project", "file-edit", "action", ["toolbar", "ribbon", "menu"]),
    "open-folder": ("M3 18V6a1 1 0 0 1 1-1h5l2 2h7a1 1 0 0 1 1 1v2M3 18l3-8h16l-3 8z",
                    "Open project folder", "file-edit", "action", ["toolbar", "menu"]),
    "settings": ("M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"
                 "M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 0 0 0-7z",
                 "Open application settings", "users-settings", "navigation", ["toolbar", "web-navigation"]),
    "add": ("M12 5v14M5 12h14",
            "Add new item", "file-edit", "action", ["toolbar", "device-list", "web-actions"]),
    "alarm-list": ("M7 15v-4a5 5 0 0 1 10 0v4l1.5 2h-13zM10.5 20h3",
                   "Open active alarm list", "alarms-events", "navigation", ["ribbon", "web-navigation"]),
    "trend-chart": ("M3 3v18h18M7 15l4-4 3 3 6-7",
                    "Open historical trend view", "trends-reports", "navigation", ["ribbon", "web-navigation"]),
    "pump": ("M5 13a6 6 0 1 0 12 0a6 6 0 0 0-12 0zM11 7V4h9M5 21h12M8.5 15.5L11 10.5l2.5 5z",
             "Pump equipment", "devices-connectivity", "object", ["device-list"]),
    "valve": ("M3 7v10l9-5zM21 7v10l-9-5zM12 12V5M8 5h8",
              "Valve equipment", "devices-connectivity", "object", ["device-list"]),
    "device-connect": ("M9 3v5M15 3v5M7 8h10v4a5 5 0 0 1-10 0zM12 17v4",
                       "Connect to selected device", "devices-connectivity", "action", ["toolbar", "device-list"]),
    "network": ("M10 5a2 2 0 1 0 4 0a2 2 0 0 0-4 0zM3 19a2 2 0 1 0 4 0a2 2 0 0 0-4 0zM17 19a2 2 0 1 0 4 0a2 2 0 0 0-4 0z"
                "M12 7v5M12 12l-6 5.5M12 12l6 5.5",
                "Open network overview", "devices-connectivity", "navigation", ["menu", "web-navigation"]),
}

MASTER_TMPL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">\n'
    '  <path d="{d}"/>\n</svg>\n'
)

# legacy look: mixed stroke widths, colors and caps on a 32 grid (deliberately inconsistent)
LEGACY_STROKES = [1.0, 2.5, 2.0, 3.0, 1.5]
LEGACY_COLORS = ["#1f77b4", "#555555", "#ff7f0e", "#333333", "#17becf"]
SVG_REFS = {"save", "open-folder", "settings", "valve"}
PNG_REFS = {"add", "alarm-list", "trend-chart", "pump", "valve", "device-connect", "network"}


def legacy_svg(index: int, d: str) -> str:
    sw = LEGACY_STROKES[index % len(LEGACY_STROKES)]
    color = LEGACY_COLORS[index % len(LEGACY_COLORS)]
    cap = "butt" if index % 2 else "round"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="{cap}" stroke-linejoin="miter">'
            f'<g transform="translate(4 4) scale(1)"><path d="{d}"/></g></svg>\n')


def main() -> None:
    refs = HERE / "references"
    masters = HERE / "masters"
    refs.mkdir(exist_ok=True)
    masters.mkdir(exist_ok=True)
    meta = []
    for i, (icon_id, (d, meaning, group, role, usage)) in enumerate(ICONS.items()):
        (masters / f"{icon_id}.svg").write_text(MASTER_TMPL.format(d=d), encoding="utf-8")
        svg = legacy_svg(i, d)
        if icon_id in SVG_REFS:
            (refs / f"{icon_id}.svg").write_text(svg, encoding="utf-8")
        if icon_id in PNG_REFS:
            render_svg(svg.replace("<svg ", '<svg width="32" height="32" ', 1).encode(), refs / f"{icon_id}.png", 32)
        meta.append({"id": icon_id, "meaning": meaning, "usage_locations": usage,
                     "sizes_px": [16, 20, 24, 32], "functional_group": group, "semantic_role": role,
                     "notes": "synthetic fixture"})
    # ambiguous reference: no metadata entry, drawn as an unlabeled blob
    blob = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M6 20c0-8 6-14 14-12c4 1 6 5 5 9'
            'c-1 6-8 9-13 7c-3-1-6-2-6-4z" fill="#888"/></svg>')
    render_svg(blob.encode(), refs / "mystery-glyph.png", 32)

    write_json(HERE / "metadata.json", {"icons": meta})
    with open(HERE / "metadata.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "meaning", "usage_locations", "sizes_px", "functional_group", "semantic_role", "notes"])
        for m in meta:
            w.writerow([m["id"], m["meaning"], ";".join(m["usage_locations"]), ";".join(map(str, m["sizes_px"])),
                        m["functional_group"], m["semantic_role"], m["notes"]])
    write_json(HERE / "style-spec.json", {
        "schema_version": "1.0", "set_id": "scada-fixture", "style_version": "1.0.0", "grid": 24,
        "stroke_width": 1.5, "linecap": "round", "linejoin": "round", "padding": 2,
        "preview_sizes_px": [16, 20, 24, 32], "default_export_sizes_px": [16, 20, 24, 32],
        "themes": {"light": {"background": "#FFFFFF", "normal": "#334155", "disabled": "#94A3B8"},
                   "dark": {"background": "#1E293B", "normal": "#E2E8F0", "disabled": "#64748B"}},
        "states": ["normal", "disabled"], "small_variant_sizes_px": [16],
        "palette_status": "provisional_requires_review"})
    print(f"fixtures written: {len(ICONS)} masters, {len(list(refs.iterdir()))} references")


if __name__ == "__main__":
    main()
