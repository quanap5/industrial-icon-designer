---
phase: 1
title: "Bootstrap and toolchain"
status: completed
priority: P1
effort: 6h
dependencies: []
---

# Phase 1: Bootstrap and toolchain

## Overview

Scaffold the repository layout, lock the toolchain, resolve and lock the upstream skills, and implement `doctor.py`. Covers SRS M1 part 1. Resolves OI-01, OI-05, OI-06.

## Requirements

- FR-WFL-03, FR-WFL-06, FR-DEP-01..07, FR-IF-01..04, NFR-06, SEC-07, SEC-08, C-01..C-04
- SEC-07/SEC-08 (inspection): SKILL.md states that reading images may reach the model service, forbids third-party services, global setting changes, runtime installs and automatic commit/push; re-reviewed at each phase end
- Tests: AT-01, AT-02

## Related files

- Create: `pyproject.toml`, `requirements.lock`, `dependencies.lock.json`, `.gitignore`, `README.md`, `CHANGELOG.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`
- Create: `skills/industrial-icon-designer/SKILL.md` (stub frontmatter only), `skills/industrial-icon-designer/scripts/doctor.py`
- Create: `tests/integration/test_doctor.py`, `docs/dependency-compatibility.md`, `docs/implementation-plan.md`
- Do not touch: `docs/SRS.md`, `docs/SRS-v1.1.md`, `logos/`, `plans/`

## Implementation steps

1. Ask the user whether to run `git init` (open question); do not commit or add remotes.
2. Scaffold directories from SRS 5.3 only where missing; never overwrite existing files.
3. Write `pyproject.toml` (Python >=3.11; deps: Pillow, jsonschema, defusedxml; dev: pytest). Pin with `requirements.lock`.
4. Verify renderer: confirm `resvg --version` (0.48.1 present on this machine, installed via cargo). Record the exact version and install method (OI-01).
5. Install the three upstream skills separately with the documented command, then inspect the resolved files: origin URL, `SKILL.md`, referenced files, real script interfaces (FR-DEP-01, FR-DEP-03). If installation needs network or consent, ask first.
6. Write `dependencies.lock.json` with upstream commit SHA and per-file SHA-256 (FR-DEP-02).
7. Implement `doctor.py`: works without `--set`; checks Python, packages, renderer name and version, upstream skills origin and lock match, skill discovery path; `--json` on stdout, diagnostics on stderr; exit codes 0/2/3/4/5 (FR-IF-02..04); never installs (FR-DEP-06).
8. Verify skill discovery on the tested Claude Code version (OI-06) and record version in `docs/dependency-compatibility.md`.
9. Write `docs/implementation-plan.md` as the milestone checklist mirroring this plan.

## Todo

- [x] git init decision recorded
- [x] Scaffold created without overwriting
- [x] Toolchain and renderer pinned
- [x] Upstream skills installed, inspected, locked
- [x] `doctor.py` with JSON output and exit codes
- [x] Skill discovery verified
- [x] Compatibility record and implementation checklist written

## Verification

- `python skills/industrial-icon-designer/scripts/doctor.py --json` exits 0 with no `--set` (AT-01).
- Tamper test: change a locked file hash, doctor exits 3 with a blocked-phase message and no silent substitution (AT-02).
- `grep -R "/home/\|/mnt/" skills/` returns nothing (NFR-06).

## Risks and rollback

Upstream skills may expose no scripts (instructions only); then adapters in phase 5 are thin. Rollback: delete scaffolded paths created by this phase; existing docs untouched.
