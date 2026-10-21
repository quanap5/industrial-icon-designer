# Implementation plan and status

Source of truth for requirements: [`SRS.md`](SRS.md) v2.1. The detailed phase files live in `plans/261021-0257-industrial-icon-designer-skill/`. This page is the milestone checklist with evidence.

## Milestones

| Milestone | Scope | Acceptance tests | Status |
|---|---|---|---|
| M1 Foundation | scaffold, schemas, dependency lock, `doctor`, inventory | AT-01, 02, 03, 21 | Done |
| M2 Reference and pilot | analysis, style spec, preview, approval gate | AT-04 to 09 | Done |
| M3 Production and source QA | batches, manifest, resume, invalidation, hostile input | AT-10, 11, 17, 18, 19 | Done |
| M4 Export and post-export QA | export, web profiles, determinism, conflicts | AT-12 to 16, 20 | Done |
| M5 Handoff and maintenance | application validation, extension, demo, README | AT-22 to 26 | Done, with application contexts `not-tested` |

Evidence: 183 tests pass (`pytest`, 11 min 50 s); every AT-01 to AT-26 has a `test_atNN_` function; `tests/test_srs_traceability.py` checks that every FR/SEC/NFR/DR requirement appears in SRS 9.3.

## Definition of Done (SRS 10.2: skill implementation ready)

| Item | Evidence |
|---|---|
| Installable in a clean project; environment documented | `README.md`, `docs/dependency-compatibility.md`; AT-26 builds from a copy without `docs/`, `plans/`, `logos/` |
| Upstream sources and toolchain verified and locked | `dependencies.lock.json`; `doctor.py`; AT-02 |
| Automated tests pass; visual pilot review recorded | 183 passed; `examples/pilot-review.json` and `approvals.json` (an **agent** review of synthetic fixtures) |
| Ten-icon example with masters, mapping, synchronized style documents, previews, reports | `examples/scada-demo/` (453 files) |
| Fixture export is 160 PNGs and 10 inline SVGs | AT-12 |
| Resume, invalidation, conflicts, deterministic export demonstrated | AT-17, AT-18, AT-20, AT-16 |
| README covers setup, usage, troubleshooting, uninstall, limitations | `README.md` |
| Application validation reports honest statuses incl. no access | AT-22 to AT-24 and `reports/application-validation.json` (all `not-tested`) |

## Independent review

An independent code review found 13 defects (2 critical, 4 high, 5 medium and low items) after the first full test run. All were fixed and each has a regression test in `tests/integration/test_review_fixes.py`; three requirements (FR-EXP-08, FR-APP-06, SEC-09) were added to the SRS. The report is `plans/reports/code-reviewer-261021-1220-industrial-icon-designer.md`.

## Open items

- OI-02: the measured export time is about 15 s for 170 files; a target (proposed 30 s) needs the owner's decision.
- OI-03: DevExpress 15.1.11 bitmap and DPI behavior needs a real application.
- OI-04: native Windows support is undecided.
- OI-07: the default required-context profile (Desktop toolbar, ribbon, menu, device list; Web navigation, actions, list) needs the owner's confirmation.
- `LICENSE` states that no license is granted yet; the owner has not chosen one.
- The demo pilot review is an agent review. A human approval of the pilot is still required before real icons are generated.
- A leftover directory from the first environment attempt remains at the project root and can be deleted by the owner (the tooling hook blocked removing it from this session).
