# Industrial style rules

Use these when specifying the style (stage 3), reviewing the pilot and judging every batch.

## Design rules

- DR-01 Prefer clear, compact geometry and deliberate negative space over decoration.
- DR-02 Keep stroke width, caps, joins and recurring parts identical across the set.
- DR-03 Balance perceived size. Identical bounding boxes do not mean identical optical weight: circles need a little more room than squares, dense icons need lighter detail.
- DR-04 Geometry is identical in every theme. Only palette tokens change.
- DR-05 Disabled uses its own token, not opacity alone.
- DR-06 MVP icons are monochrome. Filled areas are fine when consistent across the set. Secondary color or duotone needs a later explicit token contract.
- DR-07 Do not use red, yellow or green to suggest equipment state unless the user approved semantic rules for them.
- DR-08 A provisional palette is labeled provisional everywhere it appears. It is never "the brand palette".
- DR-09 A small variant may drop detail but must keep the meaning.
- DR-10 This workflow does not certify compliance with any industrial safety standard.

## Starting parameters

Grid 24, stroke 1.5 (compare 1.5 against 2 in the pilot), round caps and joins, padding 2, 24-grid coordinates inside 2..22. These are starting points, configurable in `style-spec.json`, not standards. Anything that must read at 16 px should avoid features thinner than the stroke and gaps below about 3 grid units.

## Palette handling

Provisional starting tokens: Light background `#FFFFFF`, normal `#334155`, disabled `#94A3B8`; Dark background `#1E293B`, normal `#E2E8F0`, disabled `#64748B`. Normal icons target a 3:1 contrast ratio against their declared background; disabled contrast is reported separately and may be lower. Changing the palette invalidates color reviews and themed outputs but never requires redrawing geometry.

## Shared geometry

Reuse arrowheads, gears, badges, flanges and pipe joints. Define each recurring part once (in `icon-style.md`) and draw every instance from the same construction. A set whose arrowheads differ by one unit looks wrong at every size.

## Rubric

Score 1-5 each: meaning, 16 px clarity, optical balance, family consistency, contrast. Pilot acceptance needs every score at least 4 and no semantic defect. This is a review aid; it does not replace looking at actual-size renders. Always label the reviewer: `agent` or `user`.
