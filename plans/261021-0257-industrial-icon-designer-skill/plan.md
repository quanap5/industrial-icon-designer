---
title: "Industrial Icon Designer skill (SRS v2.0)"
description: "Build the industrial-icon-designer Claude Code skill: orchestrator, local scripts, schemas, previews, Desktop PNG and Web SVG export, validated on a ten-icon synthetic fixture set."
status: completed
priority: P1
effort: 66h
tags: [claude-code-skill, python, svg, icon-design, scada]
blockedBy: []
blocks: []
created: 2026-10-21
---

# Industrial Icon Designer skill

## Overview

Implements `docs/SRS.md` v2.0 (supersedes `docs/SRS-v1.1.md`) as a greenfield, personal Claude Code skill. It redesigns PNG/SVG icon sets into one industrial/SCADA system, keeps SVG masters as the single source of truth, and exports themed Desktop PNGs and Web SVGs with repeatable scripts. The plan follows SRS milestones M1–M5, split into eight phases, and delivers the SRS "skill implementation ready" Definition of Done (section 10.2). Full SRS scope is kept: no cuts, no deferred item pulled in.

## Contract

- **Outcome:** an installable `skills/industrial-icon-designer/` package plus tests, a ten-icon synthetic example, README and compatibility record, with all 26 acceptance tests passing (AT-22/23 on simulations only).
- **Constraints:** Python 3.11+, WSL2/Linux, pinned `resvg` CLI as the only QA renderer (C-04), no network during ordinary runs, no commit/push/publish without request (C-03), no edits to `docs/`, `logos/` or `plans/` content outside this plan's scope.
- **Non-goals:** deferred items in SRS 1.2 (tracing, MCP, React, ICO, brand/launcher icons, native Windows), real user icon artwork, validation inside a real DevExpress/Web application.
- **Acceptance:** SRS 10.2 "Skill implementation ready"; `pytest` green; traceability check (SRS 9.3) passes; honest `not-tested` status for actual application contexts.

## Scope decisions (from SRS v2.0)

- Repository is this project root (`/mnt/d/XISOM/Industrial-Icon-Design`), scaffolded in place beside existing `docs/`, `logos/`, `plans/`; nothing existing is overwritten.
- Upstream `shadcn-labs` skills are inspected and locked, never assumed (FR-DEP-01..07, OI-05).
- Real reference icons are not available; all pipeline work uses labeled synthetic fixtures (FR-WFL-03).

## Phase map

| Phase | SRS milestone | Main acceptance tests |
|---|---|---|
| 1 Bootstrap and toolchain | M1 | AT-01, AT-02 |
| 2 Schemas and inventory | M1 | AT-03, AT-05, AT-21 |
| 3 Orchestrator skill and style spec | M2 | AT-06, AT-07 |
| 4 Pilot preview and approval gate | M2 | AT-04, AT-08, AT-09 |
| 5 Batch production and source QA | M3 | AT-10, AT-11, AT-17, AT-18, AT-19 |
| 6 Export and post-export QA | M4 | AT-12 to AT-16, AT-20 |
| 7 Application validation and maintenance | M5 | AT-22 to AT-25 |
| 8 Demo, handoff and Definition of Done | M5 | AT-26, full sweep |

Dependencies are sequential: each phase starts after the previous phase's verification passes, except that phase 3 SKILL.md drafting may start once phase 2 schemas are frozen.

## Risks

| Risk | Mitigation |
|---|---|
| Upstream skill interfaces differ from SRS assumptions (R-02, OI-05) | Phase 1 inspects and locks them first; adapters tested in phase 5 |
| Renderer divergence misleads QA (R-06) | `doctor.py` reports renderer; only pinned `resvg` is used |
| Model-made redraw quality cannot be unit tested | Pilot gate with visual rubric and explicit human approval (phase 4) |
| 16 px legibility | Small variants and 16/20/24/32 preview (phase 4) |
| Scope size (66h) | Phases end with verified, independently usable output; resume protocol from SRS 4.10 |

## Open questions

- Local git repository: not initialized; SRS C-03 forbids commit, push and publish without a request, and nothing needed one.
- Which exact upstream commit SHA of `shadcn-labs/skills` to lock (resolved in phase 1, OI-05).
- Required application-context profile for `APPLICATION_VALIDATED` (OI-07, decided in phase 7).

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | [Phase 1: Bootstrap and toolchain](./phase-01-start.md) | Completed |
| 2 | [Phase 2: Schemas and inventory](./phase-02-schemas-and-inventory.md) | Completed |
| 3 | [Phase 3: Orchestrator skill and style spec](./phase-03-orchestrator-skill-and-style-spec.md) | Completed |
| 4 | [Phase 4: Pilot preview and approval gate](./phase-04-pilot-preview-and-approval-gate.md) | Completed |
| 5 | [Phase 5: Batch production and source QA](./phase-05-batch-production-and-source-qa.md) | Completed |
| 6 | [Phase 6: Export and post-export QA](./phase-06-export-and-post-export-qa.md) | Completed |
| 7 | [Phase 7: Application validation and maintenance](./phase-07-application-validation-and-maintenance.md) | Completed |
| 8 | [Phase 8: Demo, handoff and Definition of Done](./phase-08-demo-handoff-and-definition-of-done.md) | Completed |

## Success Criteria

- [x] All eight phases verified and marked complete
- [x] SRS 10.2 "Skill implementation ready" checklist satisfied
- [x] `pytest` passes including AT-01..AT-26 fixtures
- [x] Traceability sweep: every `FR-*`, `SEC-*`, `NFR-*`, `DR-*` appears in the SRS 9.3 table or inspection list
- [x] Actual application contexts reported `not-tested`; no `APPLICATION_VALIDATED` claim

<!-- slug: industrial-icon-designer-skill -->
