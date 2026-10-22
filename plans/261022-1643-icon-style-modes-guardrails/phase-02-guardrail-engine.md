---
phase: 2
title: "Guardrail engine"
status: completed
priority: P1
effort: "8h"
dependencies: [1]
---

# Phase 2: Guardrail engine

## Goal

A single module evaluates the spec and each icon against named consistency rules, returns errors or warnings with a suggested value, and is called from `style_spec.py check` and `validate_icons.py --phase source`.

## Files to Create / Modify

- Create: `skills/industrial-icon-designer/scripts/guardrails.py`
- Modify: `skills/industrial-icon-designer/scripts/style_spec.py` (call spec-level rules)
- Modify: `skills/industrial-icon-designer/scripts/validate_icons.py` (call icon-level rules, extend `check_svg`)
- Modify: `skills/industrial-icon-designer/scripts/upstream_adapter.py` (see task 6)

## Rules

Each rule has an id, a severity, a check and a `suggest` function. Defaults below are starting values to calibrate in a pilot; `guardrails` in the spec may override a rule only with a written reason, and an override is listed in the report.

| Rule | Check | Severity |
|---|---|---|
| `stroke-min-at-smallest` | `stroke_width * smallest_size / grid >= 1.0` px (1.5 at grid 24 and 16 px) | error |
| `min-gap` | gaps between shapes at least 3 grid units for icons used at 16 px (existing guidance in `industrial-style.md`) | warning |
| `mode-matches-spec` | each master uses the spec mode: outline has `fill="none"` and a currentColor stroke; filled has a currentColor fill and `stroke="none"`; duotone has both | error |
| `filled-knockout` | holes in filled icons use `fill-rule="evenodd"` or separate subpaths, never a background-coloured shape | error |
| `duotone-opacity-range` | secondary opacity within a range (start 0.2 to 0.5) and not applied to the primary layer | error |
| `duotone-secondary-contrast` | effective secondary colour (blend of the token and the background) keeps a minimum contrast against the background in every theme | warning, then error after calibration |
| `optical-weight-by-mode` | optical size compared against the median of icons of the same mode, not the whole set | warning |
| `no-theme-geometry` | geometry does not depend on theme (already enforced; keep the test) | error |

## Tasks & Steps

1. Define the rule registry and a result shape `{rule, severity, message, suggested}`.
2. Implement spec-level rules (`stroke-min-at-smallest`, `duotone-opacity-range` for the configured value).
3. Implement icon-level rules from the parsed SVG tree.
4. Reuse `palette.contrast_report` for the secondary-contrast rule; extend it to report the blended secondary colour.
5. Surface results in `reports/pre-export-qa.json` under a `guardrails` key.
6. In `upstream_adapter`, drop only the upstream optical-size warning for filled/duotone icons when the same-mode comparison passes; never alter upstream files or hide errors.

## Verification

- `tests/` gains one failing and one passing fixture per rule; each failing case asserts a non-empty `suggested`.
- The experiment fixtures from the report pass; `tank-filled-edge` produces the optical warning only.

## Risks and rollback

Risk: thresholds are guesses. Mitigation: they are warnings first, errors only for rules with a derivable bound (`stroke-min-at-smallest`, `mode-matches-spec`). Rollback: remove the call sites; the module is additive.
