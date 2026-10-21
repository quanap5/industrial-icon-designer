# Phase 4: Tests, UX verification and docs

## Requirements

- Update AT-09 and related tests so they assert the new contract and still protect the offline, escaping and hostile-master guarantees.
- Add tests for: `--group` narrowing, unknown group error, run state not advancing on narrowed scope, "No reference" and "No master yet" placeholders, three context pages, and control ids derived safely from hostile group names.
- Browser pass on the scada-demo set at 1280, 768 and 360 px wide, keyboard-only, 200% zoom, light and dark page chrome. Use the repo's browser tooling and save screenshots under `plans/reports/`.
- Contrast check for page chrome text and for status badges.
- Docs: update `skills/industrial-icon-designer/SKILL.md` and `.claude/skills/industrial-icon-designer/SKILL.md` identically (they are kept in sync), plus the README preview section, `CHANGELOG.md` and, if open question 3 says yes, an SRS addendum.

## Files

- Modify: `tests/integration/test_pilot_preview_and_gate.py`, `tests/integration/test_review_fixes.py`, both `SKILL.md` copies, `README.md`, `CHANGELOG.md`
- Create: `tests/integration/test_preview_compare_ui.py`

## Steps

1. Run the existing preview tests, list the assertions that fail because of layout, and change each with a stated reason.
2. Add the new tests above.
3. Run the browser pass and record findings in a report; fix defects found.
4. Update docs, then run the full `pytest` suite.

## Validation

- Full `pytest` green, with the pre-change test count recorded for comparison.
- Report lists which of the six acceptance items were verified and how.

## Risk and rollback

Changing a test to fit new output can hide a regression. Each changed assertion must keep its original intent (offline, escaping, actual size, honest labels). Revert the commit to roll back.
