---
phase: 6
title: "Docs, tests and regression"
status: pending
priority: P1
effort: "6h"
dependencies: [2, 3, 4, 5]
---

# Phase 6: Docs, tests and regression

## Goal

Documentation matches the code, and the old outline workflow is proven unchanged.

## Files to Create / Modify

- Modify: `docs/SRS.md` (`DR-06`, `FR-EXP-02`, new requirements and acceptance tests); optionally add `docs/SRS-v2.3.md` (open question 1)
- Modify: `README.md`, `CHANGELOG.md`, `skills/industrial-icon-designer/references/questions.md` (add decision points `style_mode` and `duotone_level`; keep the AskUserQuestion format)
- Create or modify: tests under `tests/` for phases 1 to 5

## Tasks & Steps

1. Read each document before editing, and check each claim afterwards against the code.
2. Add a regression test that runs the existing outline example set end to end and compares geometry hash, validation result and exported file list with the pre-change values.
3. Add an end-to-end test on a mixed fixture set: validate source, export, validate exported.
4. Bump the plugin version and describe the change in the changelog.
5. Run the full test suite and report any failure as is.

## Verification

- `env-py311/bin/python -m pytest tests` passes, with output attached to the final report.
- Searching the docs for `fill="none"`, `monochrome` and `DR-06` shows no statement that contradicts the new behaviour.

## Risks and rollback

Risk: SRS versions diverge. Mitigation: settle open question 1 first. Rollback: documentation commits are independent of code commits.
