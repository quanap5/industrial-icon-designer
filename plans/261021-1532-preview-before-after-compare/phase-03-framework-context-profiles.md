# Phase 3: Framework and context profiles

## Context

`build_contexts()` writes two pages showing only the redrawn icons, always with the first icons in the set. SRS FR-PIL-03 requires Desktop and Web simulations, FR-EXP-05 keeps the Desktop profile conservative for the likely DevExpress 15.1.11 target, and FR-APP-02 lists display scaling of 100/125/150/200%.

## Requirements

- Replace the two fixed builders with a small table of profiles, each naming its icon format, sizes and screens:

| Profile | Format shown | Screens |
|---|---|---|
| `desktop` (DevExpress-style) | PNG from the Desktop export rules | Toolbar 24, Menu 16, Ribbon-like 32/16, Device list 16 |
| `web-inline` | Inline SVG using `currentColor` | Navigation 24, Actions 20, List 16 |
| `web-img` | Resolved-color SVG as `<img>` | Same screens, showing how `--web-img` output looks |

- Every screen shows Before and After side by side in the same surface, in Light and Dark, with a Normal and a Disabled row, and a "No reference" placeholder when needed.
- Desktop adds a scaling control (100, 125, 150, 200%) that scales the surface with CSS only, labeled "CSS scaling, not a real DPI test". It does not change which bitmap is used, in line with the SRS note that DPI sizes come from a target profile.
- The group filter from phase 2 applies to context pages too (shared control markup).
- Simulation banner text is unchanged, so `SIMULATION` and `not the actual application` remain in every page.
- Choosing icons for each screen: pick by group when a group is selected, otherwise the first N in inventory order. The disabled example is the same icon in both columns.

## Files

- Modify: `skills/industrial-icon-designer/scripts/preview_page.py`, `render_preview.py`
- New output: `preview/contexts/web-img.html` (added next to `desktop.html` and `web.html`; existing filenames are kept)

## Steps

1. Define the profile table and a shared screen renderer that takes an "icon source" callable for Before and After.
2. Generate resolved-color SVG snippets for `web-img` from the same master using `recolor_svg`, not from export files, so the preview works before export.
3. Add the scaling control and the navigation links between pages.
4. Verify that reference PNGs scale with `image-rendering: pixelated`.

## Validation

- Existing context assertions (`Toolbar`, `Menu`, `Ribbon-like`, `Device list`, `Navigation`, `Actions`, `List`) still hold.
- The three pages contain no script and no remote URL.

## Risk and rollback

A web-img preview could be mistaken for application validation. Mitigation: the banner stays on every page and the run state is not advanced. Revert the commit to roll back.
