---
title: "Icon style modes (outline, filled, duotone) with consistency guardrails"
description: "Let industrial-icon-designer produce outline, filled and opacity-duotone icons in one set, customised through style-spec.json and protected by a guardrail layer."
status: in-progress
priority: P2
effort: 3d
branch: quanap5/feat/icon-style-modes
tags: [icon-design, validation, spec]
blockedBy: []
blocks: []
created: 2026-10-22
---

# Icon style modes with consistency guardrails

## Outcome

`style-spec.json` gains `style_mode` (`outline` | `filled` | `duotone`) and the parameters that customise it. A guardrail layer checks the spec and every icon against explicit consistency rules and reports a suggested value for each violation. Existing outline sets keep working and keep their approvals.

## Constraints

- The locked upstream skills (`dependencies.lock.json`) are never edited; differences are handled in `upstream_adapter.py`.
- Geometry is identical in every theme (DR-04). Only palette tokens change.
- Duotone uses `fill-opacity` on `currentColor`; no new palette token (DR-06 keeps true second colours out of scope).
- Output must render with the pinned `resvg` and keep Web inline `currentColor`.
- No fake data. Tests use constructed SVG fixtures labelled as fixtures.

## Non-goals

Gradient, 3D, skeuomorphic, hand-drawn, pixel, multi-colour flat, a real second colour, isometric.

## Acceptance criteria

1. A filled icon and an opacity-duotone icon pass `validate_icons.py --phase source` and `--phase exported`, with Desktop PNG and Web SVG output for Light and Dark.
2. Each guardrail rule has a failing and a passing test, and every failure message includes a suggested value.
3. An existing outline set (including its approvals) is unchanged by the new code: same geometry hash, same validation result.
4. `SKILL.md`, `industrial-style.md`, `questions.md`, the SRS and the README no longer contradict the code.

## Evidence (experiment, step 1 done)

See `plans/reports/experiment-261022-1643-filled-duotone-validator.md`. Filled and opacity-duotone icons pass both the local and the locked upstream validator with no errors; the earlier "false stroke error" risk did not materialise. Open verification is listed in the phases.

## Assumptions to confirm at plan approval

1. Filled is a state variant of an outline icon (`x` and `x-filled` form a pair), not a separate full set.
2. Duotone is one colour at two opacities.
3. Old specs without `style_mode` mean `outline` and keep their geometry hash.

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 1 | [Spec contract and hash compatibility](phase-01-spec-contract-and-hash-compatibility.md) | pending | none |
| 2 | [Guardrail engine](phase-02-guardrail-engine.md) | pending | 1 |
| 3 | [Variant pairing](phase-03-variant-pairing.md) | pending | 1 |
| 4 | [Export and exported-phase checks](phase-04-export-and-exported-checks.md) | pending | 1, 2 |
| 5 | [Preview and review rubric](phase-05-preview-and-review-rubric.md) | pending | 2, 3 |
| 6 | [Docs, tests and regression](phase-06-docs-tests-regression.md) | pending | 2, 3, 4, 5 |

Phases 2 and 3 touch different files and can run in parallel after phase 1.

## Unresolved questions

1. Should SRS changes go into `SRS.md` only, or also a new `SRS-v2.3.md` as the existing versions suggest?
2. Are the numeric guardrail defaults in phase 2 acceptable as starting values, to be calibrated in a pilot?
3. Does the DevExpress 15.1.11 target render `fill-opacity` in PNG? Only a real application check can answer this (phase 4 leaves it `not-tested` otherwise).

## Implementation notes (deviations from the phase text)

- The guardrail module is `consistency.py` and the spec key is `consistency_overrides`, because `guardrails` / `guardrails.json` already name the input-size limits in `common.py`.
- `min-gap` is not reimplemented: the locked upstream validator already reports it. `filled-knockout` needs no new check: a background-coloured knockout is a fixed colour and the existing source QA rejects it (covered by a test).
- `optical-weight-by-mode` became `variant-bounds-parity` (painted box of a filled variant against its base, measured on a render) plus dropping the upstream envelope warning for variants.
- Strictness is opt-in: a spec that declares `style_mode` gets errors, an older spec only warnings, so existing outline sets keep their validation result. `style_spec.py init --style-mode` writes the key.
- SRS: follows the repository habit of keeping each superseded version, so `docs/SRS-v2.3.md` is the previous text and `docs/SRS.md` is 2.4. This replaces the default "SRS.md only" from open question 1.
- Plugin version 0.4.0.
- Not verified: DevExpress 15.1.11 rendering of `fill-opacity` (`not-tested`).
