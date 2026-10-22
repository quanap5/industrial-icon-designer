---
phase: 4
title: "Export and exported-phase checks"
status: completed
priority: P1
effort: "5h"
dependencies: [1, 2]
---

# Phase 4: Export and exported-phase checks

## Goal

Filled and duotone icons export to Desktop PNG and Web SVG for Light and Dark, and the exported-phase validation checks the real files.

## Files to Create / Modify

- Modify: `skills/industrial-icon-designer/scripts/export_assets.py`
- Modify: `skills/industrial-icon-designer/scripts/validate_icons.py` (exported phase)
- Modify: `skills/industrial-icon-designer/scripts/common.py` (`recolor_svg`, only if needed)
- Modify: `skills/industrial-icon-designer/references/desktop-export.md`, `web-export.md`

## Tasks & Steps

1. Run `export_assets.py --dry-run` on a set that contains a filled and a duotone icon and record what it does with no code changes. The experiment showed `recolor_svg` keeps `fill-opacity`, so changes may be minimal.
2. Confirm the Web inline file still equals the master and keeps `currentColor` (existing check at `validate_icons.py` exported phase).
3. For `web-img` variants, verify that the replaced colour is used for both fill and stroke and that `fill-opacity` survives.
4. Add an exported check that the secondary layer's alpha in the PNG matches the configured opacity within a tolerance.
5. Record in `desktop-export.md` that `fill-opacity` in the DevExpress target is `not-tested` until `app_validation.py` records evidence; do not claim support.

## Verification

- `export_assets.py` then `validate_icons.py --phase exported` passes on a mixed outline, filled and duotone fixture set.
- A pixel test (as in the experiment: alpha 64 at 0.25 opacity) is automated.

## Risks and rollback

Risk: the application renders opacity differently from `resvg`. Mitigation: status stays `ASSETS_READY`, never `APPLICATION_VALIDATED`, until the user tests it. Rollback: revert exporter changes; outline output is untouched.
