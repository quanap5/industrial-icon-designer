---
phase: 1
title: "Spec contract and hash compatibility"
status: pending
priority: P1
effort: "4h"
dependencies: []
---

# Phase 1: Spec contract and hash compatibility

## Goal

Add the customisation fields to `style-spec.json` without changing the geometry hash of any existing set.

## Files to Create / Modify

- Modify: `skills/industrial-icon-designer/schemas/style-spec.schema.json`
- Modify: `skills/industrial-icon-designer/scripts/style_spec.py` (`DEFAULT_SPEC`, `SCALARS`, `GEOMETRY_KEYS`, `geometry_hash`, `expected_rows`)
- Modify: `skills/industrial-icon-designer/SKILL.md` ("Master format" section)

## Tasks & Steps

1. Read the schema and check whether `additionalProperties` is false, and how `schema_version` is validated.
2. Add optional fields with defaults: `style_mode` (`outline`), `duotone_secondary_opacity` (used only for `duotone`), and a `guardrails` object for overrides (empty by default).
3. Make `geometry_hash` include `style_mode` and `duotone_secondary_opacity` only when they differ from the defaults, so an outline spec hashes exactly as before.
4. Treat a missing `style_mode` as `outline` when loading old specs; do not rewrite old files.
5. Show the new fields in the `icon-style.md` parameter table (`expected_rows`) only when not default, so `style_spec.py check` stays green for old sets.
6. Rewrite the SKILL.md "Master format" so it describes the three modes instead of hard-coding `fill="none"`.

## Verification

- A test loads a spec saved before this change and asserts its `geometry_hash` equals a pinned literal computed from the pre-change code.
- `style_spec.py check` passes on an old set and on a new filled-mode set.
- Changing `style_mode` changes the geometry hash; changing only the palette does not.

## Risks and rollback

Risk: `canonical_hash` ordering or key presence differs from what the old code produced. Mitigation: the pinned literal test. Rollback: revert the three files; no data migration exists.
