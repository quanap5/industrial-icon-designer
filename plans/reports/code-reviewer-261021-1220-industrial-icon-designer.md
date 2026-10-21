# Code Review: industrial-icon-designer skill package

Date: 2026-10-21. Reviewer: code-reviewer (read-only). Spec: docs/SRS.md v2.0.

## Scope
- Files: skills/industrial-icon-designer/scripts/*.py (18 files, ~3.6k LOC), schemas, SKILL.md, tests/, examples/build_demo.py
- Method: full read of the gate, invalidation, export, approval and app-validation code paths, then experiments on copies of the fixture pipeline in the session scratchpad (`/tmp/claude-1000/.../scratchpad/h/harness.py`, `e1.py` to `e6.py`). Nothing was written in the project tree except this report. I did not run the full suite.
- Every finding marked "verified" was reproduced end to end with the real scripts and resvg.

## Overall assessment
The happy path and the documented AT scenarios hold up. The gates fail at their edges. Two of them break the main promises: an export or preview can carry executable script, and `APPLICATION_VALIDATED` can be claimed with nothing tested. Several invalidation paths record a reset that no gate ever reads.

## Critical

### C1. Script injection through XML comments and processing instructions (SEC-01, SEC-02)
- `common.py:211-229` (`svg_findings`) only inspects elements and attributes. defusedxml drops comments and PIs, so they are never seen. `validate_icons.py:36-67` (`check_svg`) has the same blind spot.
- `render_preview.py:107-110` (`inline_svg`) pastes the raw master text into the HTML page. Its regex removes only `<?xml ...?>`.
- `export_assets.py:94-98` writes the raw master bytes as `exports/web/<id>.svg`, the inline profile meant to be pasted into host HTML. `validate_staged` (151-160) and post-export QA (`validate_icons.py:223-232`) run the same blind check.
- Scenario (verified): a master containing `<!--><script>alert(1)</script>-->`, or `<?x ><img src=x onerror=alert(1)>?>`, is valid XML (a comment, or a PI). It gives `svg_findings == []` and `check_svg == ([], [])`, so it passes source QA, becomes eligible and is exported byte for byte. An HTML parser closes `<!-->` at once (abrupt empty comment) and ends `<?...` at the first `>`, so the script runs in `preview/contexts/*.html` and in any app that inlines the web export.
- Fix: reject any master or variant whose raw bytes contain `<!--`, or `<?` other than the XML declaration. Better: re-serialize the parsed tree (no comments or PIs) and use those bytes for the inline preview and the web-inline export. Add tests for both payloads.
- Confidence: high.

### C2. `APPLICATION_VALIDATED` is claimed when zero contexts are required (FR-APP-04)
- `app_validation.py:107-126` lets every context be removed, each with a reason. `required()` (49-50) then returns `[]`. `cmd_evaluate` (212-219) finds no failed and no untested rows, so it sets `overall = APPLICATION_VALIDATED` and advances run-state.
- Scenario (verified, e1.py): `profile --remove <ctx> --reason "no app"` for all 7 contexts, then `evaluate`. Output: `{"overall": "APPLICATION_VALIDATED", "required_contexts": 0}`, and run-state reaches `APPLICATION_VALIDATED`.
- Fix: in `cmd_evaluate`, claim `APPLICATION_VALIDATED` only when `rows` is non-empty and every row passed. Consider refusing to remove the last context of a platform, or the last context overall.
- Confidence: high.

## High

### H1. `app_validation evaluate` ignores drift and validates stale state
- `effective()` / `current_hashes()` (`app_validation.py:67-78`, `182-193`) compare only against manifest export records from `manifest_mod.load`. They never call `invalidate.detect` or `sync`.
- Scenario (verified, e2.py): every context recorded `passed`, so the overall is `APPLICATION_VALIDATED`. Then I edited `masters/save.svg` and changed the light `normal` token in `style-spec.json`. `evaluate` still says `APPLICATION_VALIDATED`, while `invalidate.py detect` reports `geometry: [save]` and `palette`. The set is claimed validated although its source of truth no longer matches what was tested.
- Fix: in `cmd_evaluate`, run `invalidate.detect(set_dir)` first. If it finds any change, report `ASSETS_READY` (or `NEEDS_REVIEW`) with a "drift pending" reason, and never claim validation.
- Confidence: high.

### H2. `NEEDS_REVIEW` icons can be approved and exported, including by unattended agent review (FR-INV-05, AT-05)
- `approvals.record` (`approvals.py:88-110`) never reads the inventory status. `manifest.derive_status` (`manifest.py:85-90`) and `visual_from_approvals` ignore it too.
- Scenario (verified, e3.py): `mystery-glyph` is inventoried as `NEEDS_REVIEW`. With a master drawn, this succeeds: `approvals.py record --type batch --reviewer agent --unattended-authorized --ids mystery-glyph`. The manifest then shows `eligible` and `export_assets.py` writes `exports/web/mystery-glyph.svg`. `batch.py` blocks such icons only from batch planning. The pilot sample (`analysis.select_sample`) can also include them.
- Fix: refuse any approval whose scope contains an inventory `NEEDS_REVIEW` id. Make `derive_status` return `pending` while the inventory status is `NEEDS_REVIEW`.
- Confidence: high.

### H3. Export is not gated on a current pilot approval (FR-PIL-05, SRS 5.6 "global style")
- `export_assets.export` (189-285) requires only `status == eligible`. After `invalidate apply style`, any later `batch` approval makes icons eligible again, even though the pilot approval stays stale.
- Scenario (verified, e4.py case 6): change `padding`, run `detect --apply`, pass source QA, then record a `batch` approval for all ids. `approvals.py check --type pilot` prints `closed: approval is stale: style changed`, yet `export_assets.py` exits 0 and exports all 170 files.
- Fix: in `export()` call `approvals.require_valid(set_dir, "pilot")`, or make batch approval require a valid pilot gate, as `batch.plan` already does.
- Confidence: high.

### H4. Palette invalidation resets nothing that is enforced; colour review is write-only
- `invalidate.py:80-82` sets `qa.color_review = "pending"`, and nothing ever reads it. A grep finds it only in invalidate.py and a test. `approvals.evaluate(..., "palette")` exists but no gate calls it.
- Scenario (verified, e4.py case 5): change `themes.light.normal` to `#FF0000`, run `detect --apply`, and `export_assets.py` exits 0, re-rendering 40 PNGs with the unreviewed palette. `approvals.py check --type palette` says `closed: no palette approval recorded`. The SRS 5.6 "Palette only" row (colour review invalidated) is satisfied only on paper.
- Fix: make export (and the `ASSETS_READY` advance) require either no pending `color_review` or a current `palette` approval (`evaluate(set_dir, "palette")`). Clear `color_review` when a palette approval is recorded.
- Confidence: high.

## Medium

### M1. A deleted master or a dropped inventory entry breaks `detect --apply` and orphans its exports
- `invalidate.apply` (54-58) calls `sync` first. `sync` drops icons with no master or no inventory row (`manifest.py:115-118`), and `_select` then raises `no manifest entry`.
- Scenario (verified, e4.py case 4): delete `masters/pump.svg`. The first `invalidate.py detect --apply` exits 2 (`no manifest entry for: pump`), after the manifest has already been rewritten. The second run reports 0 changes. `export_assets.py` then exits 0 with 17 `unknown` files: pump's PNGs and SVG stay in `exports/` untracked. Post-export QA lists them in `unknown_files` but does not fail (`validate_icons.py:243-267`), so `ASSETS_READY` can be reached with a removed icon still in the deliverable. A re-inventory that drops or renames a reference does the same thing silently, with no migration map (FR-INV-03).
- Fix: keep removed icons in the manifest with a `removed` status until their exports are cleaned. Make `apply` tolerate ids that `sync` removed. Treat `unknown_files` as a post-export QA failure, or at least a warning that blocks `ASSETS_READY`.
- Confidence: high.

### M2. Symlinked set subdirectories escape the set root (SEC-04)
- `validate_icons.check_svg:40` checks only whether the file itself is a symlink. Export never calls `is_within` for `exports/`, `masters/` or `variants/` (`export_assets.py:44-48`, `268-277`).
- Scenario (verified, e6.py): with `masters/` a symlink to a directory outside the set, source QA passes. With `exports/` a symlink to an outside directory, export exits 0 and writes all 160 PNGs outside the set.
- Fix: before reading or writing, check `is_within(path, set_dir)` for `masters/`, `variants/` and `exports/`, and every final path. Refuse with exit 2.
- Confidence: high.

### M3. Exit-code contract breaks on non-`ToolError` failures (FR-IF-02, FR-IF-04)
- `common.py:20` imports `defusedxml` at module load, and `doctor.py:19` imports `common`. Verified: with defusedxml missing, `doctor.py --json` dies with a traceback and exit 1, before its own package check runs. The SRS requires exit 3 with an actionable message.
- `run_main` (`common.py:312-318`) maps only `ToolError`. Any `OSError` or `PermissionError` during the export commit (`export_assets.py:268-277`) exits 1 instead of 5. So do a corrupt journal (`json.loads` at 168), a non-dict scores file (`approvals.py:74`) and a bad `--scaling` value (`app_validation.py:140`).
- Fix: lazy-import defusedxml in doctor, or catch ImportError around the `common` import. Map `OSError` to `EXIT_RENDER` and `ValueError`/`JSONDecodeError` to `EXIT_INPUT` in `run_main`.
- Confidence: high for doctor (verified), high for the rest (code read).

### M4. `batch.py done` reports success when the final full source QA fails (FR-WFL-01)
- `batch.py:96-100`: after the last checkpoint, `validate_source(..., None)` runs, but only `blocked` is checked. If any master fails, for example a pilot master edited meanwhile, `done` still returns exit 0 with `pending: 0`.
- Fix: also raise `EXIT_VALIDATION` when `final["summary"]["failed"]` is non-zero.
- Confidence: high (code read).

### M5. The pilot gate does not check that approval covers the pilot sample (FR-PIL-05)
- `approvals.evaluate` (113-136) checks only the latest pilot entry's own scope. `record --type pilot --ids save` with one icon's scores opens `batch.plan` for everything, even when `brief.sample_ids` has 10 icons.
- Fix: for `kind == "pilot"`, require `set(brief.sample_ids) <= set(latest.scope)`.
- Confidence: high (code read).

## Low
- L1. Upstream integrity (FR-DEP-01/02): `upstream_adapter.locate_skill:38-39` hashes only the files listed in the lock. `run_upstream:75` runs the upstream script without `-I`, so its directory is on `sys.path`. An unlisted `scripts/json.py` (the generator's `validate_icons.py` imports `json`) would shadow stdlib and run unverified code. Fix: use `-I`, and fail on any unlisted `.py` under `scripts/`.
- L2. Rubric: `check_scores` (`approvals.py:78`) accepts `NaN`, which `json.loads` allows (`NaN < 4` is False), and accepts values above 5. Fix: require a finite number with `1 <= s <= 5`.
- L3. `export --dry-run` calls `manifest_mod.sync` (`export_assets.py:198`), which rewrites `manifest.json`. New masters and new approvals get absorbed during a supposed no-op.
- L4. `export --target web` still requires resvg (`export_assets.py:192`, exit 3), and `run_state.advance("EXPORTED")` (283) fires after a partial-target export.
- L5. No lock against concurrent exports: one run's `rmtree(staging)` (223) can destroy another run's staged files before its commit.

## Contract mismatches (SRS vs implementation)
- FR-IF-04 exit codes: see M3. All other scripts I checked map their documented paths correctly.
- FR-APP-04: see C2 and H1.
- SRS 5.6 table: the "Palette only" row (H4) and the "Global geometry style" row (H3) are not enforced at export. The "Usage size" row is handled. "Usage context" (`usage_locations`) is not detected by `detect`. It is caught indirectly by `app_validation.effective` through `expected_icons`, so no wrong claim results.
- `--json`: stdout carries JSON and diagnostics go to stderr in every script I read. Not violated.

## Test quality
- No test covers C1 (comment or PI payloads), C2 (empty profile), H1 (evaluate with drift), H2 (approving a `NEEDS_REVIEW` icon), H3 or H4.
- `tests/integration/test_invalidation.py:56-75` asserts `color_review == "pending"` but never asserts that anything is blocked by it. It locks in the write-only flag from H4.
- `tests/integration/test_export.py:358-361` ("no network or LLM calls") greps only `export_assets.py`, not the modules it imports. Weak evidence for FR-IF-05 and NFR-04.
- `tests/test_srs_traceability.py:37-40` counts an AT as covered if the string `AT-nn` appears anywhere in the test sources, comments included. A docstring mention is enough to pass.
- `tests/test_security_inspection.py` checks are text greps (for `shell=True`, network imports). They are fine as inspection aids but do not exercise SEC-02 or SEC-04 behaviour.

## Categories with no findings
- Shell use (SEC-03): every subprocess call uses an argument list and none uses `shell=True`. No issues.
- Network during normal runs: only `setup_upstream.py --clone` reaches the network. No issues.
- Secrets: none found in the shipped artifacts.

## Recommended actions (priority order)
1. C1: sanitize or re-serialize masters, reject comments and PIs, and add tests.
2. C2 and H1: harden `cmd_evaluate` (non-empty profile, drift check).
3. H2, H3, H4: enforce `NEEDS_REVIEW`, the pilot gate and the palette gate at approval and export time.
4. M1 to M5, then the Low items.

## Unresolved questions
- Should a set be allowed to drop all Desktop (or all Web) contexts and still reach `APPLICATION_VALIDATED` for the other platform? Product intent decides the exact C2 rule.
- Is `palette_status: provisional_requires_review` meant to block export until a palette approval exists, or only to label the output? It affects how strict the H4 fix should be.
