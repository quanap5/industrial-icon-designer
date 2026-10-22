#!/usr/bin/env python3
"""Build the style examples next to the SCADA demo by running the real pipeline on the synthetic fixtures.

    python examples/build_style_examples.py [--out examples] [--only filled,duotone] [--stop-after preview]

Each example redraws the same ten synthetic references in one drawing form:

    scada-filled           style_mode filled, every master a solid shape with cut-out details
    scada-duotone          style_mode duotone, one colour at two opacities (a blue provisional palette)
    scada-outline-bold     style_mode outline at stroke 2 with a graphite provisional palette
    scada-selected-states  the outline demo masters plus filled variants of four icons
    scada-badged           six outline icons, each with one solid badge (plus, minus or check) as a secondary object
    scada-badge-accent     the same six icons with a violet badge (a second palette token, `accent`) that sits on the
                           right edge of its icon, so half of the badge lies over the icon

Everything is synthetic. The reviews are AGENT reviews of constructed icons, recorded as such; they are not
human approval and not validation in a real application. Palettes are provisional, never a brand palette.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import build_demo

HERE = Path(__file__).resolve().parent
STYLES = HERE / "styles"
PLACEHOLDERS = list(build_demo.STYLE_PROSE)  # the four template paragraphs, in order


def prose(*texts: str) -> dict:
    return dict(zip(PLACEHOLDERS, texts))


COMMON_REVIEW = "agent review of synthetic icons; not human approval"
EXAMPLES = {
    "filled": {
        "set_id": "scada-filled",
        "title": "Filled SCADA set (synthetic)",
        "summary": "Every master is a solid shape with `fill=\"currentColor\"` and `stroke=\"none\"`; details are cut out "
                   "with `fill-rule=\"evenodd\"` or kept as separate gaps, never painted in a background colour.",
        "direction": "Redraw the ten icons as solid shapes on a 24 grid with 2 units of padding. Details are holes or "
                     "gaps so Light, Dark and disabled only change the palette token. Keep established SCADA "
                     "conventions (valve as two opposed triangles, pump as a circle with an outlet).",
        "style_args": ("--style-mode", "filled"),
        "masters": STYLES / "filled" / "masters",
        "review": STYLES / "filled" / "review.json",
        "prose": prose(
            "A filled form reads well as a selected or active state and in dense toolbars at 16 to 24 px. Solid "
            "shapes need cut-outs wider than 1.5 units to survive at 16 px. The slate palette is provisional and "
            "is not the official brand palette.",
            "Equipment glyphs (pump, valve) sit on the same padding box as the outline set. Thin features "
            "(network links, valve stem) are 1.5 units wide; teeth of the gear are 3 units wide.",
            "`trend-chart` uses an area under the line instead of an open polyline, because a stroke would "
            "need a second rendering mode. No other icon deviates.",
            "All ten icons in `masters/` are the pilot. `settings` and `save` are the reference for cut-outs, "
            "`valve` for thin parts. The pilot review is an agent review of synthetic icons."),
    },
    "duotone": {
        "set_id": "scada-duotone",
        "title": "Duotone SCADA set (synthetic)",
        "summary": "Each master is an outline plus one translucent fill (`fill=\"currentColor\"` at "
                   "`fill-opacity=\"0.3\"`): one colour at two opacities, no second palette token.",
        "direction": "Keep the outline geometry of the existing set and add a translucent fill to the main body of "
                     "each icon. The secondary layer is the same colour at 30 percent so that themes and states "
                     "still change one palette token only.",
        "style_args": ("--style-mode", "duotone"),
        "spec_patch": {
            "duotone_secondary_opacity": 0.3,
            "themes": {"light": {"background": "#FFFFFF", "normal": "#1D4ED8", "disabled": "#93A3C4"},
                       "dark": {"background": "#0F172A", "normal": "#93C5FD", "disabled": "#475569"}},
        },
        "masters": STYLES / "duotone" / "masters",
        "review": STYLES / "duotone" / "review.json",
        "prose": prose(
            "A translucent body gives dashboards a second level of emphasis without a second colour. The "
            "secondary layer must stay visible against both backgrounds, so its opacity is 0.3 and its contrast "
            "is checked per theme. The blue palette is provisional and is not the official brand palette.",
            "The fill covers the body of the icon (bell, plug body, front flap, pump casing, floppy body, "
            "gear hub, area under the trend line, valve triangles, node circles, a disc behind the plus).",
            "`add` has no closed shape, so a disc sits behind the plus. `trend-chart` fills the area under the "
            "line without a stroke on the fill. No other icon deviates.",
            "All ten icons in `masters/` are the pilot. `pump` and `valve` are the reference for filled "
            "equipment bodies. The pilot review is an agent review of synthetic icons."),
    },
    "outline-bold": {
        "set_id": "scada-outline-bold",
        "title": "Bold outline SCADA set (synthetic)",
        "summary": "The outline masters of the demo at stroke 2 instead of 1.5, with a graphite provisional palette: "
                   "the same geometry showing what a heavier stroke does to 16 px legibility.",
        "direction": "Keep the geometry of the demo set and raise the stroke to 2 for busy backgrounds. The "
                     "geometry is unchanged; only the stroke width and the palette differ.",
        "style_args": ("--style-mode", "outline"),
        "spec_patch": {
            "stroke_width": 2,
            "themes": {"light": {"background": "#FFFFFF", "normal": "#1F2937", "disabled": "#9CA3AF"},
                       "dark": {"background": "#111827", "normal": "#F3F4F6", "disabled": "#6B7280"}},
        },
        "masters": STYLES / "outline-bold" / "masters",
        "review": STYLES / "outline-bold" / "review.json",
        "prose": prose(
            "A stroke of 2 on a 24 grid renders 1.33 px at 16 px, which holds up on textured or busy "
            "backgrounds. The cost is crowded interiors (gear, pump, network). The graphite palette is "
            "provisional and is not the official brand palette.",
            "Geometry is identical to the demo set; only the root stroke width differs. Equipment glyphs keep "
            "the same padding box.",
            "`settings`, `pump` and `network` are the tightest at 16 px; an explicit small variant would help "
            "them. No icon deviates in this example.",
            "All ten icons in `masters/` are the pilot. The pilot review is an agent review of synthetic icons."),
    },
    "badged": {
        "set_id": "scada-badged",
        "title": "Outline icons with a solid badge (synthetic)",
        "summary": "Six icons drawn as a 0.72-scale outline main object plus one solid secondary object: a disc in the "
                   "bottom-right corner with a plus (add), minus (remove) or check (done) cut out by "
                   "`fill-rule=\"evenodd\"`. Three icons have an explicit 16 px variant that drops detail, because the "
                   "first pilot review refused them for clarity at 16 px.",
        "direction": "Draw the main object as an outline at 0.72 scale and add one solid badge in the bottom-right "
                     "corner. The badge symbol is cut out of the disc, so themes and states change one token. Each "
                     "icon is a new meaning (add, remove, done), not a redraw of an existing one.",
        "style_args": ("--style-mode", "outline"),
        "masters": STYLES / "badged" / "masters",
        "references": STYLES / "badged" / "references",
        "metadata": STYLES / "badged" / "metadata.json",
        "small": STYLES / "badged" / "small",
        "review": STYLES / "badged" / "review.json",
        "prose": prose(
            "Badge icons express an action or a state on an object at 16 to 24 px. The main object shrinks to make "
            "room, so the stroke stays 1.5 and gaps are tight; busy objects need a 16 px variant. The slate palette "
            "is provisional and is not the official brand palette.",
            "Every icon is a 0.72 scaled outline plus one solid disc of radius 4 centred at (17.5, 17.5) with a "
            "symbol cut out: plus adds, minus removes, check marks a done state.",
            "`pump-add`, `valve-remove` and `save-done` have an explicit 16 px variant without the interior detail "
            "(pump triangle and base, valve stem and handle, floppy label), because the full drawings merged at "
            "16 px in the first review. The badge keeps its place in the variants.",
            "All six icons in `masters/` are the pilot. The first pilot review refused three icons below 4 on "
            "16 px clarity; the review file records the scores after the 16 px variants. It is an agent review of "
            "synthetic icons."),
    },
    "badge-accent": {
        "set_id": "scada-badge-accent",
        "title": "Outline icons with a violet badge over the icon (synthetic)",
        "summary": "Six icons drawn as a 0.8-scale slate outline plus one solid badge in a second colour: the "
                   "`accent` palette token (violet), painted with `fill=\"var(--icon-accent, currentColor)\"`. "
                   "The badge is centred on the right edge of its icon, so half of its area lies over the icon. "
                   "All six icons have an explicit 16 px variant with a larger badge and a simpler main object.",
        "direction": "Draw the main object as a slate outline and add one solid badge in the accent colour, centred "
                     "on the right edge of the object so that half of the badge overlaps it. The badge symbol is cut "
                     "out of the disc. The accent is a second palette token with its own contrast check; the disabled "
                     "state paints every layer with the single disabled token.",
        "style_args": ("--style-mode", "outline"),
        "spec_patch": {
            "themes": {"light": {"background": "#FFFFFF", "normal": "#334155", "disabled": "#94A3B8",
                                 "accent": "#7C3AED"},
                       "dark": {"background": "#1E293B", "normal": "#E2E8F0", "disabled": "#64748B",
                                "accent": "#A78BFA"}},
        },
        "masters": STYLES / "badge-accent" / "masters",
        "references": STYLES / "badged" / "references",
        "metadata": STYLES / "badged" / "metadata.json",
        "small": STYLES / "badge-accent" / "small",
        "review": STYLES / "badge-accent" / "review.json",
        "prose": prose(
            "A badge in a second colour separates the action or state from the object without a second shape "
            "language. The accent has its own token per theme, is checked for 3:1 contrast and for distance from "
            "the normal colour (a pale violet on the dark theme was rejected as too close to the near-white "
            "normal colour). Violet is not an alarm colour. The palette is provisional and is not the official "
            "brand palette.",
            "Every icon is a 0.8 scaled slate outline plus one disc of radius 4 centred on the right edge of that "
            "icon's painted box, vertically centred, so half of the disc lies over the icon. The symbol "
            "(plus, minus or check) is cut out of the disc by `fill-rule=\"evenodd\"`. The disc is the only "
            "accent layer.",
            "All six icons have an explicit 16 px variant: a simpler main object (no pump triangle and base, "
            "no valve stem, no plug cord, no floppy label, no bell clapper) and a larger badge (radius 4.8) with "
            "thicker symbols, because the badge symbol blurred at 16 px in the full drawings.",
            "All six icons in `masters/` are the pilot. The review is an agent review of synthetic icons made "
            "after looking at the 16 px renders in both themes."),
    },
    "selected-states": {
        "set_id": "scada-selected-states",
        "title": "Outline set with filled selected states (synthetic)",
        "summary": "The outline demo masters, plus a filled variant (`<id>-filled`) for four icons that have a "
                   "selected state: `valve`, `pump`, `alarm-list` and `settings`. Each variant is its own master, "
                   "judged as filled and checked against the box of its outline base.",
        "direction": "Keep the outline set as the main family. Four icons also get a filled variant that "
                     "stands for the selected state; it occupies the same box as its base.",
        "style_args": ("--style-mode", "outline"),
        "masters": None,
        "variants": ("valve", "pump", "alarm-list", "settings"),
        "variant_masters": STYLES / "filled" / "masters",
        "review": HERE / "pilot-review.json",
        "prose": prose(
            "The outline family suits toolbars and sidebars; filled variants mark the selected state without a "
            "second colour. The slate palette is provisional and is not the official brand palette.",
            "Equipment glyphs sit on a 2 unit padding box. A filled variant keeps the box of its outline base "
            "within one unit, which `validate_icons.py` measures on a render.",
            "`settings` has an explicit 16 px variant without the four diagonal rays, because the full gear "
            "closes up at that size. Its filled variant is a separate master.",
            "All ten outline icons in `masters/` are the pilot; the four `*-filled` masters are approved as a "
            "batch beside them. Both reviews are agent reviews of synthetic icons."),
    },
}


def readme(example: dict) -> str:
    sid = example["set_id"]
    return f"""# {example['title']}

Generated by `examples/build_style_examples.py` from the synthetic fixtures. The icons are not real product
artwork. {example['summary']}

The review in `icon-work/{sid}/approvals.json` is an **agent** review recorded for an unattended run; it is
not human approval. The palette is provisional. Application validation is `not-tested` for every context.

| Path | Content |
|---|---|
| `references/` | The same inconsistent synthetic "legacy" PNG/SVG icons and `metadata.json` as the demo |
| `icon-work/{sid}/masters/` | The SVG masters (24 grid, `currentColor`) |
| `icon-work/{sid}/icon-style.md`, `style-spec.json` | Synchronized style documents, including `style_mode` |
| `icon-work/{sid}/preview/` | Open `index.html`; contexts are labeled simulations |
| `icon-work/{sid}/exports/` | Desktop PNGs and inline Web SVGs |
| `icon-work/{sid}/reports/` | Reference analysis, QA reports (with the consistency findings), application checklist |

Rebuild: `python examples/build_style_examples.py --only {example['key']}`
"""


def build(key: str, out: Path, stop_after: str | None) -> Path:
    ex = {**EXAMPLES[key], "key": key}
    return build_demo.build_set(
        out / f"scada-{key}", ex["review"], stop_after, set_id=ex["set_id"], direction=ex["direction"],
        prose_by_placeholder=ex["prose"], masters=ex["masters"], style_args=ex["style_args"],
        spec_patch=ex.get("spec_patch"), variants=ex.get("variants", ()), variant_masters=ex.get("variant_masters"),
        small_variants=({p.stem: p.read_text() for p in ex["small"].glob("*.svg")} if ex.get("small") else None),
        references=ex.get("references"), metadata=ex.get("metadata"), readme=readme(ex), review_note=COMMON_REVIEW)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE))
    ap.add_argument("--only", help="comma-separated: " + ", ".join(EXAMPLES))
    ap.add_argument("--stop-after", choices=["preview"])
    args = ap.parse_args()
    keys = args.only.split(",") if args.only else list(EXAMPLES)
    unknown = [k for k in keys if k not in EXAMPLES]
    if unknown:
        raise SystemExit(f"unknown example(s): {', '.join(unknown)}; choose from {', '.join(EXAMPLES)}")
    for key in keys:
        print(f"built: {build(key, Path(args.out), args.stop_after)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
