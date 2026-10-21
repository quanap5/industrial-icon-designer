---
phase: 3
title: "Orchestrator skill and style spec"
status: completed
priority: P1
effort: 8h
dependencies: [2]
---

# Phase 3: Orchestrator skill and style spec

## Overview

Write the real `SKILL.md`, its phase-loaded references, and the style-spec tooling (generation of `icon-style.md` from `style-spec.json` plus consistency check). Covers SRS M2 part 1.

## Requirements

- FR-ANA-01..05, FR-SPC-01..03, FR-WFL-01, FR-WFL-06, DR-01..10
- Tests: AT-06, AT-07

## Related files

- Modify: `skills/industrial-icon-designer/SKILL.md`
- Create: `skills/industrial-icon-designer/references/{industrial-style,png-redraw-rules,dependency-routing,desktop-export,web-export,review-checklist}.md`
- Create: `skills/industrial-icon-designer/scripts/style_spec.py` (render summary from JSON, detect contradictions)
- Create: `tests/integration/test_style_spec.py`

## Implementation steps

1. `SKILL.md`: frontmatter from SRS 5.4, concise core flow for the eight stages, subcommands (`init analyze pilot generate extend audit export validate-app resume`), approval gates, ask-only-when-material policy, explicit "no hidden shell execution" statement. Load references by phase.
2. References: industrial rules (DR-01..10), PNG redraw rules (visual interpretation, labeling, no auto-trace, three redesign modes with `reinterpret` needing semantic approval), dependency routing (apply upstream guidance by reading resolved files, never executing them as shell programs), desktop and web export profiles, review checklist with the 1-5 rubric.
3. Stage 2 procedure: representative 8-12 sample selection rules and the documented exception below 8; SVG references go through `icon-set-audit` first; write `reports/reference-analysis.md` template.
4. Stage 3: `style_spec.py` regenerates the parameter summary in `icon-style.md` from `style-spec.json` and fails on contradictory values (FR-SPC-02); defaults grid 24, stroke compare 1.5 and 2, provisional palette labeled.
5. Dry-run the skill instructions against the fixture set by hand and record gaps in the references.

## Todo

- [x] SKILL.md complete and concise
- [x] Six reference files
- [x] `style_spec.py` with contradiction check
- [x] Reference-analysis template
- [x] Hand dry-run notes captured

## Verification

- `pytest tests/integration/test_style_spec.py`: a deliberately conflicting `icon-style.md` is detected (AT-07).
- A fixture SVG set produces a baseline audit note and a recorded redesign mode in `brief.json` (AT-06).
- Skill is discovered and its frontmatter parses.

## Risks and rollback

SKILL.md bloat: keep core short, push detail into references. Rollback: revert SKILL.md and references.
