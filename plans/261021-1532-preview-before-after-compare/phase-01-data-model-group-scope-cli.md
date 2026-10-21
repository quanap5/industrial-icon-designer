# Phase 1: Data model, group scope and CLI

## Context

`build()` in `render_preview.py` mixes data collection, rendering jobs and HTML strings in one function. Groups come from `icon["functional_group"]` in `inventory.json`. Approved status comes from `approvals.evaluate(set_dir, "pilot")`.

## Requirements

- Collect per-icon data first (id, meaning, group, role, status badge, reference availability, master availability), then render, then build HTML.
- New flag `--group NAME[,NAME]` limits scope to those functional groups; unknown names exit with the existing input error code and list the valid groups.
- The `--json` result gains `groups` (name and icon count) and `rendered_images`, with no removed keys.
- Group names are escaped in every page and are never used as raw ids; derive a safe slug for anchors and control ids.

## Files

- Modify: `skills/industrial-icon-designer/scripts/render_preview.py`
- Create: `skills/industrial-icon-designer/scripts/preview_page.py` (empty builders wired in phase 2)

## Steps

1. Extract `collect_icons(set_dir, scope, groups)` returning a list of plain dicts.
2. Add `--group`, validate it against inventory groups, and apply it after `--scope`.
3. Keep render job creation in `render_preview.py`; pass a lookup of image paths to `preview_page`.
4. Keep `PILOT_READY` advancement only when scope is pilot, no master is missing and no `--group` narrowing is active, because a partial group view is not the whole pilot.

## Validation

- `pytest tests/integration/test_pilot_preview_and_gate.py tests/integration/test_review_fixes.py` still passes before any UI change.
- New test: `--group` with a valid and an invalid name.

## Risk and rollback

Narrowing by group must not advance run state. Revert the commit to roll back.
