---
phase: 4
title: "Pilot preview and approval gate"
status: completed
priority: P1
effort: 10h
dependencies: [3]
---

# Phase 4: Pilot preview and approval gate

## Overview

Implement `render_preview.py` (sizes, themes, states, UI-context simulations), small-variant handling, and the hash-bound approval gate. Run the pilot on the synthetic fixtures. Covers SRS M2 part 2.

## Requirements

- FR-PIL-01..05, FR-QA-02, FR-QA-03, FR-GEN-02, FR-GEN-03, SEC-02, NFR-04, DR-04, DR-05
- Tests: AT-04, AT-08, AT-09

## Related files

- Create: `skills/industrial-icon-designer/scripts/render_preview.py`, `scripts/approvals.py` (record and verify approvals against style and asset hashes)
- Create: `tests/integration/test_preview.py`, `tests/integration/test_approval_gate.py`
- Create: `icon-work/fixture-demo/` pilot output (masters/, previews)
- Modify: `skills/industrial-icon-designer/scripts/common.py`

## Implementation steps

1. `render_preview.py`: render each reference/new pair with the pinned `resvg` (argument arrays, no shell) at 16/20/24/32 px on Light and Dark, normal and disabled; enlarged view only as supplement; offline HTML with no CDN; escape all labels; never inline unvalidated SVG as executable content (SEC-02).
2. Context pages: Desktop simulations (toolbar, menu, Ribbon-like, device-list) and Web (navigation, actions), each visibly labeled "simulation".
3. Small variants: manifest mapping with explicit fallback to master; preview prefers the variant at its sizes.
4. Redraw the pilot 8-12 fixture icons following `icon-set-generator` guidance (real paths and shapes, no embedded raster, no auto-trace); record before/after pairs.
5. Contrast check: 3:1 for normal, disabled reported separately (FR-QA-03).
6. `approvals.py`: write approval records (type, reviewer user/agent, timestamp, scope, style hash, asset hashes); refuse generation when the hash is stale or no human approval exists unless the user explicitly authorized unattended mode, recorded as agent review.
7. Present the pilot to the user for approval; pause the pipeline until given.

## Todo

- [x] Preview renderer with four sizes, themes, states
- [x] Desktop and Web context simulations labeled
- [x] Small-variant support
- [x] Pilot redrawn and reviewed with rubric
- [x] Approval gate tested with stale hash
- [x] User approval of pilot recorded

## Verification

- Preview HTML opens offline and contains no external URLs (grep).
- Gate test: editing a pilot SVG after approval makes `generate` refuse (AT-08/AT-18 precursor).
- Rubric scores recorded; all >=4 and no semantic defect before approval.
- Outputs rendered only by the pinned renderer.

## Risks and rollback

Visual quality is judgment-based; the gate ensures the human decides. Rollback: delete `icon-work/fixture-demo/` and revert scripts.
