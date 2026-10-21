# Phase 2: Compare UI on the index page

## Context

The index page is the pilot review surface behind FR-PIL-02. It must stay readable at actual size and honest about status.

## Requirements

- **Layout:** sticky control bar at the top; a group list on the left (a top strip on narrow screens); icon cards on the right.
- **Controls (CSS-only radios):**
  - Group: All plus one option per group, each with an icon count.
  - Theme: Light, Dark, Both.
  - State: Normal, Disabled, Both.
  - Size: 16, 20, 24, 32 px, All.
  - Compare mode: Side by side (default) and Before / After toggle (one image at a time, same position).
- **Card:** header with icon id, meaning, group, role and status badge. Two labeled columns, "Before (reference)" and "After (redrawn)", each on the theme surface, at actual size with a pixelated 4x zoom beside it, labeled "supplement". A missing reference shows "No reference", a missing master shows "No master yet".
- **Status:** badges carry text and an icon shape in addition to color. Contrast table stays near the top and keeps its `FAIL` wording.
- **UX and accessibility:**
  - Real `<fieldset>`/`<legend>` for each control group, visible focus ring, 44 px minimum targets for controls.
  - Page chrome follows `prefers-color-scheme` without altering icon surfaces, which always use the set's own theme tokens.
  - `prefers-reduced-motion` honored (no animation is needed anyway).
  - No horizontal page scroll at 360 px; cards stack Before above After.
  - Images use `loading="lazy"` and explicit width and height to avoid layout shift.
- **Optional step:** precompute a Pillow diff PNG (After vs Before at 24 px) shown as a third "Difference" view. Ship only if open question 2 says yes.

## Files

- Modify: `skills/industrial-icon-designer/scripts/preview_page.py`, `render_preview.py`
- Keep: all existing `src="renders/..."` paths so exports of previews stay stable.

## Steps

1. Write the control markup and the CSS selectors that show or hide cards and cells from the checked radios.
2. Write the card builder with the labeled Before and After columns.
3. Keep the strings the tests rely on (`light / disabled`, `dark / normal`, `supplement`, `16px`) as visible cell labels, or update the tests deliberately in phase 4.
4. Render the index for the scada-demo set and inspect it.

## Validation

- No `<script`, no `http(s)://`, no `@import` in the output.
- Hostile label and hostile master tests still pass.
- Manual: all control combinations in a browser (phase 4).

## Risk and rollback

`:has()` support: documented in the page footer as a requirement, with the full list still readable if unsupported (controls ignored, everything shown). Revert the commit to roll back.
