---
phase: 2
title: "Schemas and inventory"
status: completed
priority: P1
effort: 6h
dependencies: [1]
---

# Phase 2: Schemas and inventory

## Overview

Define versioned JSON schemas and implement `inventory_icons.py` with the ten-icon synthetic fixture set. Covers SRS M1 part 2.

## Requirements

- FR-INV-01..06, SEC-01, SEC-04, SEC-05, SEC-06, NFR-05, NFR-08
- Tests: AT-03, AT-05, AT-21 (and the inventory part of AT-19)

## Related files

- Create: `skills/industrial-icon-designer/schemas/{brief,inventory,style-spec,manifest,run-state,approvals,application-validation}.schema.json`
- Create: `skills/industrial-icon-designer/scripts/inventory_icons.py`, a shared `scripts/common.py` (paths, hashing, safe XML, errors)
- Create: `tests/fixtures/` (10 synthetic PNG/SVG icons: save, open-folder, settings, add, alarm-list, trend-chart, pump, valve, device-connect, network; one ambiguous image; invalid files), `tests/integration/test_inventory.py`

## Implementation steps

1. Write the seven schemas (JSON Schema 2020-12, `schema_version` field) from SRS 5.1 and 5.5; field-specific error messages.
2. Build fixtures as synthetic and label them `fixture: true`; include a PNG+SVG pair, a case-colliding filename, a symlink escaping the root, an oversize file, and an SVG with a script element.
3. `common.py`: SHA-256, safe XML parsing via `defusedxml`, path-traversal and symlink checks, guardrails (10 MiB, 4096x4096, 200 icons) with configuration path in errors.
4. `inventory_icons.py`: read PNG/SVG/directory plus JSON/CSV metadata; inspect dimensions, alpha, hashes, duplicates, collisions; assign stable kebab-case IDs with case-insensitive uniqueness and source mapping; mark inferred fields with confidence; unresolved meaning becomes `NEEDS_REVIEW`; prefer SVG when a PNG+SVG pair exists and report conflicts; never modify references.
5. Emit `inventory.json` validated against its schema plus a concise unresolved-items list; `--json` mode and exit codes per FR-IF-03/04.
6. Tests for each fixture class including Unicode and space paths.

## Todo

- [x] Seven schemas validated by a meta-schema test
- [x] Ten labeled synthetic fixtures plus hostile cases
- [x] `common.py` safety helpers
- [x] `inventory_icons.py` complete
- [x] Tests green on spaces/Unicode paths

## Verification

- `pytest tests/integration/test_inventory.py` passes (AT-03/05/21).
- Reference files unchanged before and after (hash comparison).
- Hostile fixtures rejected with per-file errors, no write outside root.

## Risks and rollback

Schema churn later: freeze schemas at end of this phase; changes need a version bump. Rollback: revert schema and script files only.
