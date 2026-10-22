---
title: "Second colour token (accent) and a badge example that overlaps its icon"
description: "Add an optional accent palette token so one layer of an icon can have a different colour, then build an example whose badge has another colour and overlaps half of the main icon."
status: in-progress
priority: P2
effort: 1d
branch: quanap5/feat/accent-token
tags: [icon-design, palette, export]
blockedBy: []
blocks: []
created: 2026-10-22
---

# Accent token and a badge example that overlaps its icon

## Outcome

A master can paint one layer with `fill="var(--icon-accent, currentColor)"`. Each theme may declare an optional `accent` colour. Desktop PNG and web-img exports substitute it; Web inline keeps the `var()` so host CSS can set `--icon-accent`, and it falls back to `currentColor`. An example, `scada-badge-accent`, draws six icons with a violet badge over a slate main icon, half of the badge lying over the icon.

## Constraints

- DR-06 asks for an explicit token contract before a second colour: this plan is that contract. A theme without `accent` behaves as before, so every existing set keeps its hashes (accent belongs to the palette hash, never to the geometry hash).
- Disabled uses the single `disabled` token for every layer.
- The locked upstream validator is not edited; staged copies replace the marker with `currentColor` before it sees them.
- Red, yellow and green stay unassigned (DR-07); the example uses violet and slate and says the palette is provisional.

## Non-goals

More than one extra colour, gradients, per-state accent tokens, a brand palette.

## Acceptance criteria

1. Old sets: geometry and palette hashes and demo exports are byte-identical to before.
2. An accent master passes source QA and post-export QA; Desktop PNG shows the accent colour in the badge and the normal colour in the main icon, in both themes; the disabled state is one colour.
3. Rules report a suggested value: accent used without a token, accent contrast below 3:1, accent too close to the normal colour.
4. Verified in Chromium that Web inline takes `--icon-accent` and falls back to `currentColor` (done: 225,29,72 with the variable, 29,78,216 without).
5. The example reaches `ASSETS_READY` with agent-labelled reviews; tests and docs updated.

## Phases

| # | Phase | Status |
|---|---|---|
| 1 | Contract: schema, palette, recolor, spec summary | pending |
| 2 | Validators: marker allowed locally, sanitised for upstream, accent rules | pending |
| 3 | Export, preview and post-export checks use the accent | pending |
| 4 | Example `scada-badge-accent` with a measured 50 percent overlap | pending |
| 5 | Tests, SRS 2.5, docs, changelog | pending |
