---
phase: 5
title: "Batch production and source QA"
status: completed
priority: P1
effort: 12h
dependencies: [4]
---

# Phase 5: Batch production and source QA

## Overview

Functional batch generation workflow, manifest, checkpoints, resume and invalidation, upstream adapters, and `validate_icons.py` source validation. Covers SRS M3.

## Requirements

- FR-GEN-01, FR-GEN-04, FR-QA-01, FR-QA-04, FR-WFL-01, FR-WFL-02, FR-WFL-05, FR-MNT-03, FR-DEP-04, SEC-01..06, NFR-02, NFR-03, NFR-05
- Tests: AT-10, AT-11, AT-17, AT-18, AT-19

## Related files

- Create: `skills/industrial-icon-designer/scripts/validate_icons.py`, `scripts/manifest.py`, `scripts/run_state.py`, `scripts/invalidate.py`, `scripts/upstream_adapter.py`
- Create: `tests/integration/test_validate_source.py`, `test_resume.py`, `test_invalidation.py`, `test_hostile_input.py`
- Modify: `SKILL.md`, `references/review-checklist.md`

## Implementation steps

1. `manifest.py`: create and update manifest records (SRS 5.5 fields); status per icon (pending, eligible, rejected); hashes for source and master.
2. `validate_icons.py --phase source`: structural validation of masters and variants. Reject scripts, event handlers, external references, `foreignObject`, DTD/entities and embedded raster; flag clipping and empty geometry; report the affected icon ID. Non-eligible icons never reach export (FR-QA-04).
3. Batch workflow in SKILL.md: batches of 5-10 within functional groups, reuse shared geometry, inspect next to related icons, checkpoint after each batch. `run_state.py` writes stage, hashes, pending IDs and resumable phase.
4. `invalidate.py`: implement the SRS 5.6 invalidation table; reject stale approval hashes; keep logs and prior evidence.
5. `upstream_adapter.py`: translate personal schemas to the formats found during phase 1 inspection, only where required, with a tested mapping and no invented arguments. The extension flow uses `icon-set-extend` guidance.
6. Exceptional states `BLOCKED`, `NEEDS_REVIEW`, `FAILED` preserve the last valid stage and a recovery action. A run never reports success while silently dropping failed icons.
7. Generate the remaining fixture icons in batches, with an interrupted-run simulation.

## Todo

- [x] Manifest and run-state modules
- [x] Source validator with hostile-input rejections
- [x] Invalidation implemented per SRS table
- [x] Adapter for upstream formats, tested
- [x] Batch generation of all ten fixture icons
- [x] Interrupt and resume demonstrated

## Verification

- `pytest tests/integration` for AT-10/11/17/18/19 passes.
- Resume regenerates zero approved icons (NFR-02).
- A palette-only change invalidates themed outputs but not geometry approvals (AT-18).
- Hostile SVG and path traversal are rejected with per-file messages.

## Risks and rollback

Adapter shape depends on phase 1 findings; if upstream is instructions-only, keep the adapter minimal. Rollback: revert scripts; manifest and run-state files are rebuildable.
