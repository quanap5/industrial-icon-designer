---
title: "Preview page: clear before/after comparison"
description: "Rework the generated icon preview so reference vs redrawn icons compare side by side, filterable by functional group, across Light/Dark, Normal/Disabled and target UI profiles, without losing the offline and no-script guarantees."
status: completed
priority: P2
effort: 14h
tags: [preview, ux, accessibility, python, html]
blockedBy: []
blocks: []
created: 2026-10-21
mode: fast
---

# Preview page: clear before/after comparison

## Overview

`skills/industrial-icon-designer/scripts/render_preview.py` writes `preview/index.html`, `contexts/desktop.html` and `contexts/web.html`. Today the before/after pair is two tiny images squeezed into one table cell per size, with theme and state encoded as row labels such as `light / disabled`. Every icon is one long table, there is no way to look at one functional group, and the contexts show only the redrawn icons, so nothing is compared inside a real-looking surface.

## Contract

- **Outcome:** a reviewer can pick a group, a theme, a state and a size, and immediately see each reference icon beside its redrawn icon, labeled Before and After, at actual size and enlarged. The same comparison is available inside the Desktop and Web contexts.
- **Constraints:**
  - Pages stay fully offline: no `<script>`, no remote URL, no `@import`. AT-09 asserts this today.
  - Labels stay HTML-escaped and rejected masters never reach a page (existing tests).
  - Actual-size views remain primary; enlarged views stay labeled "supplement" (FR-PIL-02).
  - Contexts stay labeled simulations (FR-PIL-03, C-02). A simulation never counts as application validation.
  - Only the pinned `resvg` renders icons. Pillow is used for reference PNGs and may compute diffs.
  - Same CLI contract: `render_preview.py --set DIR [--scope pilot|all] [--json]`; new flags are additive.
- **Non-goals:** React/Vue/Angular component output, ICO and Desktop SVG (deferred by SRS FR-EXP-04), changing export or approval logic, any claim of validation in a real DevExpress or web app.
- **Acceptance:**
  1. Group filter, theme, state and size controls work with no JavaScript.
  2. Before/After are visually distinct, labeled in text, and not distinguished by color alone.
  3. Dark, Light, Normal and Disabled each render for every icon in scope, and an icon without a reference shows an explicit "No reference" placeholder.
  4. Each context profile shows Before and After side by side.
  5. Page passes keyboard-only use, 200% zoom and a 360 px wide viewport without horizontal page scroll.
  6. `pytest` stays green, with tests updated where the layout contract intentionally changes.

## Phases

| # | Phase | Status |
|---|---|---|
| 1 | [Data model, group scope and CLI](phase-01-data-model-group-scope-cli.md) | done |
| 2 | [Compare UI on index page](phase-02-compare-ui-index.md) | done |
| 3 | [Framework and context profiles](phase-03-framework-context-profiles.md) | done |
| 4 | [Tests, UX verification and docs](phase-04-tests-ux-verification-docs.md) | done |

Phases 2 and 3 both edit page-building code, so they run in order, not in parallel.

## Key decisions

| Decision | Choice | Trade-off |
|---|---|---|
| Interactivity | CSS-only: radio inputs plus `:has()` / sibling selectors | Keeps the no-script, offline guarantee and the AT-09 assertion. Needs a browser with `:has()` (all current evergreen browsers). No free-text search. |
| Module layout | Move HTML/CSS builders to a new `preview_page.py`; keep `render_preview.py` as CLI and render orchestration | The file would pass 500 lines otherwise. One extra module, no new dependency. |
| Layout | One card per icon: Before column and After column, theme and state as controls, not row labels | More vertical space per icon, offset by group filtering and lazy-loaded images. |
| Disabled | Rendered in the theme's `disabled` token with a visible "Disabled" label | Contrast stays "reported only" as the SRS defines it. |
| Frameworks | "Profiles" are target UI contexts (Desktop DevExpress-style, Web inline SVG, Web `<img>`), not JS frameworks | Matches SRS scope. See open question 1. |

## Risks

- **Large sets:** 200 icons x 4 sizes x 2 themes x 2 states x 2 columns is many PNGs. Mitigation: `--group` renders only chosen groups, `loading="lazy"`, and a render count in the `--json` output.
- **`:has()` selector depth:** deeply nested state selectors are fragile. Mitigation: put controls at the top of one container and test all control combinations in a browser pass (phase 4).
- **Test churn:** existing assertions read exact strings (`light / disabled`, `supplement`, `renders/reference/16/pump.png`). Mitigation: keep those strings where they remain true, and change a test only with the reason stated in the commit.

## Rollback

Revert the commits for these phases. `render_preview.py` output is regenerated on every run, so no stored data or schema changes.

## Open questions

1. "Cac framework khac nhau": is this the target UI contexts above (Desktop DevExpress-style, Web inline SVG, Web `<img>`), or do you also want a view per web framework such as React, Vue or Angular? The SRS defers React; adding it would need a scope change.
2. Should the pixel-diff overlay (phase 2, optional step) ship, or is side-by-side enough?
3. Should the SRS (FR-PIL-02, FR-PIL-03) get a short addendum for group filtering and the compare views?
