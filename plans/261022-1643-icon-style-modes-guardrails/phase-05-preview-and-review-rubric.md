---
phase: 5
title: "Preview and review rubric"
status: pending
priority: P2
effort: "4h"
dependencies: [2, 3]
---

# Phase 5: Preview and review rubric

## Goal

The Before/After preview and the review checklist let a reviewer judge mode consistency and outline-versus-filled pairs by eye, since the validators say optics still need human review.

## Files to Create / Modify

- Modify: `skills/industrial-icon-designer/scripts/render_preview.py`, `preview_page.py`
- Modify: `skills/industrial-icon-designer/references/review-checklist.md`, `industrial-style.md`

## Tasks & Steps

1. Read `preview_page.py` to see how groups, themes, states and sizes are laid out.
2. Add a mode filter and show a base icon next to its filled variant at 16, 20, 24 and 32 px.
3. Add checklist rows: weight parity between outline and filled, readable knock-outs at 16 px, secondary layer distinguishable from the primary one in both themes.
4. In `industrial-style.md` update DR-06: filled and opacity-duotone are allowed; a second colour still needs an explicit token contract. Add the guardrail rule ids as the reference for reviewers.

## Verification

- Generate the preview for the fixture set and open it; each requested control works.
- The checklist rows map one-to-one to guardrail rules or are marked as visual-only.

## Risks and rollback

Low. Preview is derived output. Rollback: revert the two scripts.
