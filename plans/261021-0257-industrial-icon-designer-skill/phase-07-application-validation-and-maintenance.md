---
phase: 7
title: "Application validation and maintenance"
status: completed
priority: P1
effort: 6h
dependencies: [6]
---

# Phase 7: Application validation and maintenance

## Overview

Application-context validation records and status rules, and the maintenance workflow for extending a set. Covers SRS M5 part 1. Decides OI-07.

## Requirements

- FR-APP-01..05, FR-MNT-01, FR-MNT-02, FR-WFL-04, FR-EXP-05
- Tests: AT-22, AT-23, AT-24, AT-25

## Related files

- Create: `skills/industrial-icon-designer/scripts/app_validation.py` (record, evaluate, report), `scripts/duplicate_check.py`
- Modify: `SKILL.md`, `references/review-checklist.md`, `schemas/application-validation.schema.json` if the phase finds gaps
- Create: `tests/integration/test_app_validation.py`, `test_maintenance.py`

## Implementation steps

1. Define the required application-context profile (Desktop toolbar, Ribbon, menu, device-list; Web navigation, actions, list) and record it in `brief.json` (OI-07). A context removed from the profile needs an explicit reason.
2. `app_validation.py`: per-context records with status `passed|failed|not-tested`, reason, environment, tested IDs, exported hashes and evidence reference; a Desktop scaling checklist at 100/125/150/200% and Web browser/version fields.
3. State evaluation: no application access yields `ASSETS_READY` with `not-tested` entries; `APPLICATION_VALIDATED` only when all required contexts pass on current hashes; stale hashes reset a context to `not-tested`; simulations are never counted.
4. Provide manual checklist output for the user to fill in when screenshots are unavailable. Do not modify application code.
5. `duplicate_check.py`: before adding an icon, compare meaning and group in the manifest and report duplicates.
6. Maintenance flow: duplicate check, `icon-set-extend` guidance, source QA, regenerate affected outputs only, post-export checks, bump set version and changelog.

## Todo

- [x] Context profile and records
- [x] Status evaluator with hash staleness
- [x] Manual checklist output
- [x] Duplicate-meaning check
- [x] Extension flow with version and changelog update

## Verification

- With no application access the status is `ASSETS_READY` and every actual context is `not-tested` (AT-24).
- Adding `pump-stop` to the fixture set reruns only affected outputs and bumps the version (AT-25).
- Changing an export invalidates the matching application evidence.

## Risks and rollback

Actual application tests cannot run here; honest reporting is the delivered behavior. Rollback: revert modules; records are plain JSON.
