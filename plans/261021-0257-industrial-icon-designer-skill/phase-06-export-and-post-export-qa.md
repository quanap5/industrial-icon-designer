---
phase: 6
title: "Export and post-export QA"
status: completed
priority: P1
effort: 10h
dependencies: [5]
---

# Phase 6: Export and post-export QA

## Overview

`export_assets.py` for Desktop RGBA PNGs and Web SVG profiles, dry-run, conflict handling, deterministic output, and post-export validation. Covers SRS M4.

## Requirements

- FR-EXP-01..07, FR-QA-03, FR-QA-05, FR-IF-05, NFR-01, NFR-03, DR-04, DR-05
- Tests: AT-12 to AT-16, AT-20

## Related files

- Create: `skills/industrial-icon-designer/scripts/export_assets.py`
- Modify: `scripts/validate_icons.py` (add `--phase exported`), `references/desktop-export.md`, `references/web-export.md`
- Create: `tests/integration/test_export_matrix.py`, `test_export_determinism.py`, `test_export_conflicts.py`

## Implementation steps

1. Resolve theme palettes from `style-spec.json`. Render each PNG directly at its intended size with the pinned renderer: transparent RGBA, per-icon `sizes_px`, themes and states (FR-EXP-01).
2. Web exports: inline monochrome SVG with `currentColor`; separate resolved-color variants for `img` use; document accessibility expectations (FR-EXP-02/03). Desktop SVG, React and ICO stay disabled (FR-EXP-04).
3. Conservative Desktop profile for the likely DevExpress 15.1.11 application; no SVG, recolor or DPI assumptions (FR-EXP-05).
4. Determinism: no timestamps in payloads; fixed PNG encoder settings; volatile data goes to logs (FR-EXP-06).
5. Safe write: stage, validate, commit per managed file; recovery journal for partial failure; `--dry-run` lists changes; detect manually changed exports or unknown files and report conflicts without overwriting or deleting (FR-EXP-07).
6. Post-export QA (`--phase exported`): dimensions, alpha, palette, content-to-icon mapping, completeness, clipping; a report separate from source QA (FR-QA-05). Export never calls an LLM.
7. Manifest `exports` entries with theme/state, dimensions, path/hash, source hash and config hash (NFR-03).

## Todo

- [x] PNG export with matrix control
- [x] Web inline and img profiles
- [x] Deterministic output
- [x] Dry-run, journal, conflict handling
- [x] Post-export validator and report
- [x] Manifest export entries

## Verification

- Uniform fixture config yields exactly 160 PNGs plus 10 inline Web SVGs (AT-12).
- Per-icon size override changes counts as expected (AT-13).
- Two consecutive exports give identical SHA-256 for every file (AT-16, NFR-01).
- A manually edited export produces a conflict report and is not overwritten (AT-20).

## Risks and rollback

A renderer version change alters bytes; invalidation tracks it (renderer row). Rollback: remove `exports/` (derived data) and regenerate from masters.
