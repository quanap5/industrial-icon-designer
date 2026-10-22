---
name: industrial-icon-designer
description: Redesign industrial and SCADA UI icon sets from PNG or SVG references; maintain consistent SVG masters and export Light/Dark Desktop PNG and Web SVG assets.
---

# Industrial Icon Designer

Redesign a UI icon set into one industrial/SCADA system. SVG masters are the only source of truth; Desktop PNGs and Web SVGs are derived by scripts. Requirements live in the project's `docs/SRS.md`.

All outputs go to the user's working set `icon-work/<set-id>/` in their own project, never into this skill or plugin directory.

## Paths and environment

Run every script as `"$PY" "$SCRIPTS/<name>.py" ...`. Use the column that applies:

| | Installed as a plugin | Used from a checkout of the repository |
|---|---|---|
| `SCRIPTS` | `${CLAUDE_PLUGIN_ROOT}/skills/industrial-icon-designer/scripts` | `skills/industrial-icon-designer/scripts` |
| `PY` (Python 3.11+ with the packages in `requirements.lock`) | `${CLAUDE_PLUGIN_DATA}/env/bin/python` | `env-py311/bin/python` |
| `--project-root` for `doctor.py`, `analysis.py audit`, `validate_icons.py --phase source`, `batch.py done` | `${CLAUDE_PLUGIN_ROOT}` (holds the lock and the locked upstream skills) | `.` (the default) |

The working directory stays the user's project, so `--set icon-work/<id>` and `--input <refs>` are relative to it. When this file is loaded outside a plugin, `${CLAUDE_PLUGIN_ROOT}` is not substituted; use the checkout column.

One-time setup for a plugin install. It installs software, so ask the user first (ask `setup`) and never repeat it during a normal run:

```bash
uv venv --python 3.11 "${CLAUDE_PLUGIN_DATA}/env"
uv pip install --python "${CLAUDE_PLUGIN_DATA}/env/bin/python" -r "${CLAUDE_PLUGIN_ROOT}/requirements.lock"
cargo install resvg        # or a release binary from github.com/linebender/resvg
```

As a plugin the skill is invoked as `/industrial-icon-designer:industrial-icon-designer`; the subcommands below are arguments to it.

## Ground rules

- Real vector geometry only: paths and shapes. Never wrap PNG data in an SVG, and never auto-trace pixels silently.
- Never describe provisional colors as the user's brand palette. Never imply red/yellow/green equipment states without an approved rule.
- Reading a PNG sends its content to the configured model service. Do not send assets to any other service. Do not change global Claude settings, install dependencies during a normal run, or commit, push or publish.
- Scripts decide pass/fail for structure, hashes and exports. You decide design; the user approves it. Agent review is recorded as `agent`, never as human approval.
- Ask only for decisions that are the user's, that the project cannot answer, and that change the outcome. Infer everything else from project data. See "Asking the user".
- A missing dependency blocks only the phase that needs it. Say what is blocked and the exact fix.

## Asking the user

Use the `AskUserQuestion` tool (multiple-choice, recommended option first) for the decision points marked `ask \`id\`` below, not free-text questions. Read `references/questions.md` the first time you ask: it holds the rules, the exact question for each decision point and what to do with each answer.

- Ask only what the request and the project files do not already answer; never re-ask a settled decision.
- One call per decision point, 1-4 related questions, 2-4 options each. Ask in the user's language.
- A pilot or batch approval is recorded as `user` only from a real answer to the approval question. Never offer agent self-approval, and never treat silence or a headless run as approval.
- If you cannot ask (headless run, subagent), use the documented default for reversible choices, write the assumption into `brief.json` `notes`, and stop at the gate that needs a human.

## First run

1. `doctor.py --json` with the `--project-root` from the table above (add `--set DIR` inside a set). It reports Python, packages, the pinned `resvg` renderer, the locked upstream skills and which phases are blocked. It installs nothing.
2. If the upstream skills are missing or differ from `dependencies.lock.json`, stop the affected phases. In a checkout the user runs `setup_upstream.py` explicitly; as a plugin they update or reinstall the plugin. Never edit the installed upstream files. Read `references/dependency-routing.md`.
3. No references yet? Offer scaffolding and the synthetic fixtures, labeled as fixtures. No brand colors? Use the provisional palette and say so. No target application? Previews are simulations and application validation stays `not-tested`. Targets and palette still unknown after reading the request and the project: ask `intake`.

## Subcommands (proposed conventions, not built-in commands)

| Command | Stage | What to do |
|---|---|---|
| `init refs=<dir> out=<set>` | 1 Inventory | `inventory_icons.py --input <refs> --set <set>`; resolve `NEEDS_REVIEW` icons with the user; unresolved meaning is never auto-approved |
| `analyze set=<set>` | 2 Analyze | `analysis.py brief|sample|audit`, write the proposed direction, `analysis.py finalize`. Read `references/png-redraw-rules.md` |
| `pilot set=<set>` | 3-4 Spec, pilot | `style_spec.py init|generate|finalize`; redraw the sample; `render_preview.py` (Before/After compare page with group, theme, state and size controls; `--group a,b` limits groups; Desktop, Web inline SVG and Web img context simulations); review with `references/review-checklist.md`; record approval with `approvals.py` |
| `generate set=<set>` | 5 Batches | only after a valid approval; `batch.py plan`, draw 5-10 icons per functional group, `batch.py done`, `validate_icons.py --phase source` |
| `extend set=<set> icons=a,b` | 8 Maintenance | `duplicate_check.py`, then the generate loop for the new ids, then `export_assets.py` |
| `audit set=<set>` | QA | `validate_icons.py --phase source`; upstream audit through `upstream_adapter` |
| `export set=<set>` | 6 Export | `export_assets.py --dry-run` first, then without it; `validate_icons.py --phase exported`. Read `references/desktop-export.md`, `references/web-export.md` |
| `validate-app set=<set>` | 7 Application | `app_validation.py`; real contexts are `passed`, `failed` or `not-tested` with evidence |
| `status set=<set>` | any | the `logs` skill: `progress.py` prints a read-only vertical timeline of the steps, the current one and the next action |
| `resume set=<set>` | any | `run_state` shows what to keep and what to regenerate; never redo approved batches |

## Workflow

1. **Inventory.** Stable kebab-case IDs, meaning, usage locations, per-icon sizes, group, role (action, state, object, navigation). Keep an action (`device-connect`) apart from a state (`device-connected`). For each `NEEDS_REVIEW` icon ask `meaning` (unresolved meaning is never approved).
2. **Analyze.** Pick one redesign mode in the brief (ask `mode` unless the request says; ask `reinterpret` before recording it): `normalize` (keep shape; standardize stroke, color, alignment), `redraw` (keep meaning; redesign geometry; default), `reinterpret` (change the metaphor; needs explicit semantic approval, never because an icon is merely hard to recognize). Select an 8-12 icon sample. Audit SVG references with the upstream audit first; label PNG readings as visual interpretation.
3. **Specify.** `style-spec.json` is authoritative; `icon-style.md` explains it. Start from grid 24 and compare strokes 1.5 and 2 during the pilot; ask `grid` only when the smallest usage size is 20 px or less. Run `style_spec.py check` whenever either changes.
4. **Pilot.** Redraw the sample, generate previews at 16/20/24/32 px, Light and Dark, normal and disabled, plus Desktop and Web context simulations. Score meaning, 16 px clarity, optical balance, family consistency and contrast from 1 to 5; all must be at least 4 with no semantic defect. Ask `stroke` when both weights were previewed, then stop and ask `pilot` (loop through `revise_which` until approved); the approval is bound to the geometry style hash (grid, stroke, caps, joins, padding, small-variant sizes) and to the pilot file hashes, so a palette-only change does not void it but any geometry change does.
5. **Generate** in functional batches of 5-10, reusing shared geometry, checking each batch beside its neighbors, checkpointing after every batch. When every batch passes source QA, ask `batch` once for the whole run.
6. **Export** only icons that passed source QA and visual review. Render each size directly from the master. Web inline SVGs use `currentColor`; `img` use needs resolved colors (`--web-img`). Ask `export_scope` if the outputs are unclear, run `export_assets.py --dry-run` first. If it reports drift, ask `drift`; if it reports conflicts, ask `conflict` and never use `--resolve overwrite` unasked; if it asks for a palette review, ask `palette`.
7. **Validate.** Post-export checks inspect the real files. Then ask `app_access`; if the user can test, ask `contexts` and record only what they report, otherwise leave every context `not-tested`. Without application access the result is `ASSETS_READY`, never `APPLICATION_VALIDATED`.
8. **Maintain.** Check duplicate meaning (ask `duplicate` when one is found), extend with the approved style, regenerate only what changed, bump the set version and changelog.

## Master format

24x24 `viewBox`, no width/height, stroke-based, `fill="none"`, `stroke="currentColor"`, the grid's stroke width, round caps and joins, and no ids on groups. No scripts, event handlers, external references, `foreignObject`, DTD or embedded raster. Geometry never changes between themes; only palette tokens do. Explicit small variants (for 16 px) are separate files mapped in the manifest.

## References (load by phase)

- `references/industrial-style.md` for design rules, palette handling and the rubric.
- `references/png-redraw-rules.md` for PNG interpretation, redesign modes and ambiguity.
- `references/dependency-routing.md` before using any upstream skill.
- `references/desktop-export.md` and `references/web-export.md` before exporting.
- `references/review-checklist.md` for every review and approval.
- `references/questions.md` before the first question to the user (rules, every decision point, what to do with each answer).

## Status vocabulary

States: `NEW`, `INVENTORIED`, `REFERENCES_ANALYZED`, `SPEC_READY`, `PILOT_READY`, `PILOT_APPROVED`, `GENERATING`, `SOURCE_QA_PASSED`, `EXPORTED`, `POST_EXPORT_QA_PASSED`, `ASSETS_READY`, then `APPLICATION_VALIDATED` and `COMPLETE`; exceptional: `BLOCKED`, `NEEDS_REVIEW`, `FAILED`. Report honestly which of source quality, export success and application validation has actually been demonstrated.
