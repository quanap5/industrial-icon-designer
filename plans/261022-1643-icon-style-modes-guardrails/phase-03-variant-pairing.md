---
phase: 3
title: "Variant pairing"
status: pending
priority: P1
effort: "6h"
dependencies: [1]
---

# Phase 3: Variant pairing

## Goal

An outline icon and its filled counterpart are recognised as one icon in two forms, not as a duplicate and not as two unrelated inventory entries.

## Files to Create / Modify

- Modify: `skills/industrial-icon-designer/scripts/inventory_icons.py` (optional `variant_of`, `variant_kind`)
- Modify: `skills/industrial-icon-designer/scripts/duplicate_check.py`
- Modify: `skills/industrial-icon-designer/scripts/manifest.py` (pair is tracked and exported together)
- Modify: `skills/industrial-icon-designer/scripts/validate_icons.py` (a variant needs its base; geometry bounds match)
- Modify: `skills/industrial-icon-designer/schemas/` (inventory schema, if one exists)

## Tasks & Steps

1. Read `inventory_icons.py` and `manifest.py` first to find where icon ids and file names are derived.
2. Add `variant_of: <base-id>` with `variant_kind: filled`. The id convention is `<base-id>-filled`.
3. `duplicate_check`: an icon whose `variant_of` names the matching base is not a duplicate of it; the check still flags a second filled variant or a filled icon without a base.
4. Manifest: record the pair so status, approval and invalidation cover both; a change to the base marks the variant for review.
5. Validation: the variant must exist only with its base, share the base's bounding box within a tolerance, and use the filled mode.

## Verification

- `duplicate_check.py --id valve-filled --meaning "<same as valve>" --variant-of valve` exits 0; without `--variant-of` it still exits 4.
- A manifest sync with a pair produces both entries and one linked status.

## Risks and rollback

Risk: file naming affects export paths and any consumer expecting one file per concept. Mitigation: names stay kebab-case ids, nothing is renamed for existing sets. Rollback: the new fields are optional; remove them.
