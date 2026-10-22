# Software Requirements Specification
# Industrial Icon Designer for Claude Code

| Field | Value |
| --- | --- |
| Document version | 2.4 |
| Date | 2026-10-22 |
| Supersedes | 2.3 (preserved as `docs/SRS-v2.3.md`); earlier: `docs/SRS-v2.2.md`, `docs/SRS-v2.1.md`, `docs/SRS-v2.0.md`, `docs/SRS-v1.1.md` |
| Structure | Aligned with ISO/IEC/IEEE 29148 (requirements separated from design, atomic and verifiable) |
| Implementation status | Implemented as v0.1.0 on WSL2/Linux (see `docs/implementation-plan.md` and `docs/dependency-compatibility.md`); no real Desktop or Web application has been tested |
| Project type | Greenfield personal skill project |
| Skill name | `industrial-icon-designer` |
| Language | English (documents, code, skill instructions) |
| Primary runtime | Claude Code on WSL2/Linux |

## 1. Introduction

### 1.1 Purpose

Define the requirements for a personal Claude Code skill that redesigns existing PNG/SVG icon sets into one consistent industrial/SCADA visual system, keeps one authoritative SVG source set, and generates Desktop and Web assets through repeatable scripts.

### 1.2 Scope

In scope (MVP):

- PNG/SVG references and JSON/CSV semantic inventories; stable icon IDs and source mapping.
- Reference analysis, three explicit redesign modes, baseline SVG audit.
- Human-readable and machine-readable style specifications.
- An 8–12 icon pilot with an approval gate, then functional batches of 5–10 icons.
- Previews at 16/20/24/32 px, Light/Dark, normal/disabled, with UI-context simulations.
- SVG masters, optional small-size variants, themed transparent Desktop PNGs, Web SVGs.
- Structural, visual, pre-export, post-export and application-context QA.
- Resume, dependency locking, provenance, versioning and a maintenance workflow.

Out of scope (deferred; never enabled silently):

- Training models; raster concept generation through additional paid providers.
- Potrace or multicolor tracing; multi-agent orchestration; an MCP server.
- React component generation, icon fonts, Figma integration.
- Brand/launcher/application icon design, ICO/ICNS packaging. Application icons and UI toolbar icons are separate design problems.
- Automatic integration into application source code; runtime theme switching.
- Native Windows execution until explicitly tested; WSL2 is the initial supported environment.

### 1.3 Definitions

| Term | Meaning |
| --- | --- |
| Master | Authoritative editable SVG for one icon (`masters/<id>.svg`) |
| Small variant | Explicit optical variant of a master for specific small sizes |
| Pilot | The 8–12 icon sample redrawn and approved before full generation |
| Redesign mode | One of `normalize`, `redraw`, `reinterpret` (section 4.2) |
| Action / state | An action (`device-connect`) is a command; a state (`device-connected`) is a condition. They are different icons |
| Provisional palette | Placeholder colors that are not the user's official brand palette |
| ASSETS_READY | Assets passed source and post-export QA; application validation may be pending |
| APPLICATION_VALIDATED | Every required actual application context has passed with current hashes |
| Simulation | A standalone UI mock-up; it is not the target application |

### 1.4 Conventions

- **shall** = mandatory; **should** = recommended, deviation recorded; **may** = optional.
- Requirement IDs are stable: `FR-<area>-NN`, `SEC-NN`, `NFR-NN`, `DR-NN`, `AT-NN`. IDs are never reused; a removed requirement is marked withdrawn.
- Priority: **M** (must, MVP), **S** (should), **C** (could).
- Verification: **T** automated test, **I** inspection, **D** demonstration, **A** analysis.
- All personal script names, schemas, states and commands are proposed contracts, not existing upstream functionality. Nothing is called verified until the corresponding work has been performed.

### 1.5 References

- Claude Code skills: https://code.claude.com/docs/en/skills
- Core upstream skills: https://github.com/shadcn-labs/skills (not audited or executed when this SRS was written)
- Optional tracing reference: https://github.com/JKc66/custom-icons-skill
- Optional critique/export reference: https://github.com/Paldom/icon-designer-skills/blob/main/docs/setup-prompt.md

## 2. Overall description

### 2.1 Product perspective

One personal orchestration skill, three separately installed upstream skills, and local scripts. A skill is instructions and supporting tools, not an autonomous service; reading PNG references requires an image-capable model and tools, which installing a skill does not provide.

| Component | Responsibility |
| --- | --- |
| Personal orchestrator | Intake, reference interpretation, routing, approvals, checkpoints, handoff |
| `shadcn-labs/icon-set-generator` | Guidance for generating a consistent SVG family |
| `shadcn-labs/icon-set-extend` | Guidance for additions to an approved family |
| `shadcn-labs/icon-set-audit` | Inspection of consistency of existing and generated SVG sets |
| Claude Code image-capable model/tools | Inspect PNG references; redraw vector geometry |
| Local scripts | Inventory, schemas, rendering, previews, export, hashes, reports |
| User | Resolve ambiguous meaning; approve visual design |

No native PNG-to-SVG tracing is assumed. The default PNG route is visual interpretation followed by vector redraw; automated tracing is an optional future adapter.

### 2.2 Users and stakeholders

| Role | Interest |
| --- | --- |
| Icon set owner (the user, a developer of an industrial/SCADA product) | Consistent icons for a Desktop application (likely DevExpress 15.1.11) and a Web application |
| Application developers | Correctly sized, themed, named assets that are easy to integrate |
| Operators (end users of the SCADA UI) | Recognizable icons at 16–32 px; no misleading alarm semantics |

### 2.3 Operating environment

- Python 3.11+, Pillow, a JSON Schema validator, a safely configured XML parser, and one pinned SVG renderer (preferably the `resvg` CLI). Final versions are selected and locked during implementation (OI-01).
- Node.js only if a selected installer or optimizer needs it. SVGO is optional and any optimization shall be followed by rendering checks.
- Generation uses the configured Claude Code model and needs network access to it. Validation, rendering and export work locally without network after setup. Model-assisted image interpretation is not offline.

### 2.4 Constraints

- C-01 The project starts in a new repository and shall not depend on an existing application repository, resource collection, preinstalled personal scripts or private prior conversation context.
- C-02 The Desktop PNG profile shall be conservative; SVG loading, automatic recoloring and DPI behavior of any control shall not be assumed until tested.
- C-03 Creating the project does not authorize creating or publishing a remote repository, committing, or pushing.
- C-04 The pinned renderer is the reference renderer for QA. Output of other renderers shall not be used as QA evidence.

### 2.5 Assumptions and dependencies

- A-01 Reference icons and target application access are supplied separately and may be absent at first.
- A-02 The three upstream skills are installable from `shadcn-labs/skills`; their actual interfaces are unverified until inspected (OI-05).
- A-03 The tested Claude Code version discovers skills at `.claude/skills/` or `~/.claude/skills/` (verified per OI-06).

### 2.6 Risks

| ID | Risk | Mitigation |
| --- | --- | --- |
| R-01 | Model misreads a PNG reference and changes meaning | NEEDS_REVIEW for ambiguity; before/after pilot review; `reinterpret` needs approval |
| R-02 | Upstream skills change or differ from assumptions | Pin revision and file hashes; adapter tests; block affected phase only |
| R-03 | Details disappear at 16 px | Small variants; 16/20/24/32 preview; visual rubric |
| R-04 | Provisional palette mistaken for brand palette | Mandatory labeling; palette-only invalidation |
| R-05 | DevExpress rendering/DPI differs from simulation | Conservative PNG profile; actual-context validation; `not-tested` reporting |
| R-06 | A non-reference renderer misdraws valid SVG and QA is wrong | C-04; doctor reports renderer name and version; pilot and exports are checked with the pinned renderer only |

## 3. Process model

| Stage | Output | Gate |
| --- | --- | --- |
| 1 Inventory and semantics | `inventory.json`, unresolved list | Ambiguity resolved or NEEDS_REVIEW |
| 2 Analyze and select direction | `reports/reference-analysis.md`, redesign mode in `brief.json` | Mode recorded |
| 3 Establish specification | `icon-style.md`, `style-spec.json` | Documents agree |
| 4 Pilot and approval | Pilot masters, previews, approval record | User approval on current hashes |
| 5 Functional batches | Masters, checkpoints | Batch inspected |
| 6 Pre-export QA and export | `reports/pre-export-qa.json`, exports | Only eligible icons exported |
| 7 Post-export and application validation | `reports/post-export-qa.json`, `reports/application-validation.json` | Per-context status recorded |
| 8 Maintenance | Updated manifest, changelog | Duplicate-meaning check passed |

Normal states: `NEW → INVENTORIED → REFERENCES_ANALYZED → SPEC_READY → PILOT_READY → PILOT_APPROVED → GENERATING → SOURCE_QA_PASSED → EXPORTED → POST_EXPORT_QA_PASSED → ASSETS_READY`. Application validation is tracked per context. `APPLICATION_VALIDATED` is reached only when all required actual contexts pass, then `COMPLETE`. Exceptional states: `BLOCKED`, `NEEDS_REVIEW`, `FAILED`.

## 4. Functional requirements

Implementation order is sequential for the MVP. Add tracing or multi-agent orchestration only after the basic ten-icon workflow works.

### 4.1 Inventory (FR-INV)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-INV-01 | The system shall accept individual PNG/SVG files or directories and JSON/CSV inventory data with the fields in 5.1. | M | T |
| FR-INV-02 | The system shall leave reference files unchanged and record each reference's path and SHA-256 in the inventory. | M | T |
| FR-INV-03 | The system shall assign stable kebab-case IDs, unique case-insensitively, and map each source filename to its ID. An application-facing ID shall not be renamed without an explicit migration map. | M | T |
| FR-INV-04 | The system shall inspect dimensions, alpha, hashes, duplicates and filename collisions of references. | M | T |
| FR-INV-05 | Inferred inventory fields shall carry an explicit confidence/note. An icon whose meaning is unresolved shall enter `NEEDS_REVIEW` and shall not be approved automatically. Actions and states shall not be conflated. | M | T |
| FR-INV-06 | When both PNG and SVG represent one icon, the system shall use the SVG for geometry analysis, retain both references, and report conflicting meanings or versions instead of choosing silently. | M | T |

### 4.2 Reference analysis (FR-ANA)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-ANA-01 | The system shall select 8–12 representative icons covering simple marks, familiar commands, specialized equipment and dense symbols. With fewer than eight available icons, all shall be reviewed and the exception recorded. | M | I |
| FR-ANA-02 | The PNG route shall be visual interpretation followed by vector redraw. Interpretations shall be labeled as such. Pixels shall not be auto-traced silently. | M | I |
| FR-ANA-03 | For SVG references, the system shall apply `icon-set-audit` before redesign and preserve the baseline findings. | M | I |
| FR-ANA-04 | The system shall record one redesign mode in `brief.json`: `normalize` (preserve shape; standardize stroke, color, alignment), `redraw` (preserve functional meaning; redesign geometry; default recommendation) or `reinterpret` (change the visual metaphor). `reinterpret` shall require explicit semantic approval and shall not be chosen merely because a source icon is hard to recognize; clarification shall be requested first. | M | T |
| FR-ANA-05 | The system shall produce `reports/reference-analysis.md` with the selected sample, current inconsistencies, proposed direction and rationale. The pilot later supplies the before/after comparison. | M | I |

### 4.3 Style specification (FR-SPC)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-SPC-01 | The system shall produce `icon-style.md` and `style-spec.json` before batch generation. | M | T |
| FR-SPC-02 | `style-spec.json` shall be authoritative for structured parameters. A check shall detect contradictory values between the two documents, and the explanatory parameter summary shall be regenerated when the JSON changes. | M | T |
| FR-SPC-03 | The specification shall define grid, stroke, cap/join, corner treatment, safe padding, optical balance, common parts, theme tokens, states, size variants and export profiles. Grid 24×24 is a starting point and stroke widths 1.5 and 2 shall be compared during the pilot; both are configurable, not universal standards. | M | I |
| FR-SPC-04 | `style-spec.json` shall declare the drawing form in `style_mode` (`outline`, `filled` or `duotone`; absent means `outline`) and, for duotone, `duotone_secondary_opacity`. Duotone shall be one colour at two opacities (`fill-opacity` on `currentColor`); a second colour requires an explicit token contract. A spec that declares no mode shall keep the geometry hash and validation result it had before modes existed. | M | T |
| FR-SPC-05 | The system shall check the specification and each master against named consistency rules (minimum rendered stroke at the smallest size, mode per master, duotone opacity range, consistency and secondary contrast) and shall report a suggested value with every finding. A declared mode shall produce errors, an undeclared one warnings. A rule limit may be overridden only with a written reason, and overrides shall be listed in the report. | M | T |

### 4.4 Pilot (FR-PIL)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-PIL-01 | The system shall redraw the selected 8–12 icons using `icon-set-generator` guidance. | M | D |
| FR-PIL-02 | The preview shall show each reference/new pair at 16, 20, 24 and 32 px on Light and Dark surfaces in normal and disabled states. Enlarged views are supplementary to actual-size views. | M | T |
| FR-PIL-03 | The preview shall include standalone Desktop contexts (toolbar, menu, Ribbon-like, device-list) and Web contexts (navigation, actions) with labels and surrounding UI elements. They shall be labeled as simulations. | M | I |
| FR-PIL-04 | Pilot review shall cover recognizability, small-size gaps, optical weight, confusingly similar meanings and accidental alarm-state color implications. An explicit small variant shall be created when needed; arbitrary downscaling shall not be assumed to give a good 16 px result. | M | I |
| FR-PIL-05 | The user shall approve the pilot before full generation. The approval shall be recorded against the style hash and pilot asset hashes. Approval shall be requested again only for unresolved semantics or material style changes. Unattended agent review, when explicitly authorized, shall be recorded separately and never labeled human approval. | M | T |

### 4.5 Generation (FR-GEN)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-GEN-01 | The system shall generate batches of 5–10 icons within functional groups, reuse shared geometry (arrowheads, gears, badges), inspect each batch next to related icons, and save a checkpoint after every batch. | M | D |
| FR-GEN-02 | Icons shall be real vector geometry (paths and shapes). Embedding PNG data in an SVG, or silently auto-tracing source pixels in the redraw route, is prohibited. | M | T |
| FR-GEN-03 | `masters/` shall be the authoritative editable set. Small variants shall be explicit exceptions mapped to sizes. Exports are derived artifacts and shall not become the source of truth. Masters with embedded raster shall be rejected. | M | T |
| FR-GEN-04 | Additions to the approved family shall apply `icon-set-extend` with the style and approved samples. | M | D |
| FR-GEN-05 | A filled variant of an outline icon shall be its own inventory entry and master (`<id>-filled`) that records `variant_of`, shall not be reported as a duplicate of its base, shall always be judged as filled, and shall occupy the same painted box as its base within a tolerance. | M | T |

### 4.6 Quality assurance (FR-QA)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-QA-01 | The system shall run structural validation on masters and variants and report failures with the affected icon ID. | M | T |
| FR-QA-02 | The visual review shall score meaning, 16 px clarity, optical balance, family consistency and contrast, each 1–5. Pilot acceptance requires all scores ≥4 and no semantic defect. Agent and human reviews shall be labeled separately. This rubric is not an objective automated guarantee. | M | I |
| FR-QA-03 | For normal icons the token-level check shall target a 3:1 foreground/background contrast ratio on declared backgrounds. Disabled contrast shall be reported separately. This does not establish application-wide accessibility compliance. | M | T |
| FR-QA-04 | Only eligible icons shall enter final exports; pending drafts remain available for preview with clear labels. | M | T |
| FR-QA-05 | Post-export QA shall inspect the generated files (size, alpha, colors, mapping, completeness, clipping, visual quality) separately from source SVG QA. | M | T |
| FR-QA-06 | For a duotone set, post-export QA shall require exported pixels at the configured secondary alpha, so a renderer that drops `fill-opacity` is detected. | M | T |

### 4.7 Export (FR-EXP)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-EXP-01 | The system shall export transparent RGBA PNGs using the approved Desktop palette, per-icon `sizes_px`, themes and states. Each size shall be rendered directly at the target size, not upscaled from a smaller PNG. Preview backgrounds shall not appear in exports. | M | T |
| FR-EXP-02 | The system shall export inline monochrome Web SVGs (outline, filled or opacity-duotone) that use `currentColor`; accessibility expectations shall be documented for the consuming UI. | M | T |
| FR-EXP-03 | For SVG used through an `img` element, the system shall resolve colors or generate explicitly selected variants. It shall not promise inherited host CSS color through `img`. | M | T |
| FR-EXP-04 | Desktop SVG export, React components and ICO are deferred profiles and shall not be enabled silently. | M | I |
| FR-EXP-05 | The Desktop profile shall be conservative for the likely DevExpress 15.1.11 target and make no SVG, recoloring or DPI assumption until tested (C-02). | M | I |
| FR-EXP-06 | Identical sources, config and tool versions shall produce identical asset bytes. Volatile timestamps belong in logs, not in SVG/PNG payloads. | M | T |
| FR-EXP-07 | Export shall stage writes, validate them and commit each managed file safely, retaining a recovery journal for partial failure. It shall not delete unknown files or overwrite manually changed exports without explicit resolution, and shall offer `--dry-run` listing expected changes without modifying the output set. | M | T |
| FR-EXP-08 | Export shall refuse to run while a current pilot approval is missing or stale, while icons of a changed palette have no palette approval, while drift is unprocessed, or while another export of the same set is running. Removed icons' files shall be cleaned up (or reported as conflicts if edited by hand). | M | T |

### 4.8 Application validation (FR-APP)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-APP-01 | Each target context shall record status `passed`, `failed` or `not-tested`, a reason, environment, tested icon IDs, exported hashes and an evidence reference. Screenshots are optional; a precise manual checklist is acceptable. | M | I |
| FR-APP-02 | Desktop validation shall cover toolbar, Ribbon, menu and device-list screens in both themes and supported states, and display scaling at 100%, 125%, 150% and 200%, recording the framework/control behavior. | M | I |
| FR-APP-03 | Web validation shall cover navigation, toolbar/action and list contexts, both themes and supported states, recording browser version and rendering conditions. | M | I |
| FR-APP-04 | Without target application access the delivery shall be `ASSETS_READY` with actual contexts `not-tested`. `APPLICATION_VALIDATED` shall not be claimed and a simulation shall not substitute for an actual application test. | M | T |
| FR-APP-05 | The system shall not modify target application code unless the task authorizes it. The user may integrate assets and supply evidence for review. | M | I |
| FR-APP-06 | `APPLICATION_VALIDATED` shall be claimed only when at least one required context remains in the profile, every required context has passed on current exported hashes, covers every icon used in it, and no change is waiting to be processed. | M | T |

### 4.9 Maintenance and invalidation (FR-MNT)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-MNT-01 | Before adding an icon the system shall inspect the manifest for duplicate meaning. | M | T |
| FR-MNT-02 | An addition shall apply `icon-set-extend`, run source QA, regenerate affected outputs, run post-export checks and update the asset-set version and changelog. Affected application contexts shall be revalidated when geometry, palette or rendering behavior changes. | M | D |
| FR-MNT-03 | Changes shall invalidate outputs per 5.6. Stale approval hashes shall never be accepted; logs and prior evidence remain available for history. | M | T |

### 4.10 Workflow, state and dependencies (FR-WFL, FR-DEP)

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-WFL-01 | The system shall follow the state model in section 3. Exceptional states shall preserve the last valid stage and a recovery action. A run shall not be reported successful while silently dropping failed icons. | M | T |
| FR-WFL-02 | The system shall resume from checkpoints, retaining approved work and invalidating only affected outputs and reviews. | M | T |
| FR-WFL-03 | First run shall execute capability and dependency checks before generation. Without references it shall allow scaffolding and synthetic fixtures labeled as fixtures, not approved artwork. Without brand colors it shall use a labeled provisional palette. Without the target application it shall generate standalone previews and mark application validation `not-tested`. Missing references or application access shall not block independent infrastructure work. | M | T |
| FR-WFL-04 | The system shall distinguish "skill implementation ready" from "this icon set validated in a production application". | M | I |
| FR-WFL-05 | The system shall record provenance, dependency and config hashes, errors, approvals and remaining limitations, per 5.5. | M | T |
| FR-WFL-06 | The skill shall keep core instructions concise and load references by phase, infer routine defaults from project data, and ask only for unresolved meanings, pilot approval or material design changes. It shall not introduce hidden shell execution or request unrestricted permissions. | M | I |
| FR-WFL-07 | Decisions that belong to the user shall be asked as structured multiple-choice questions (the `AskUserQuestion` tool) defined in `references/questions.md`: 1-4 questions per call, 2-4 options each, the recommended option first, never an "Other" option, and nothing the request or the project files already answer. Only a real answer may be recorded as a user approval; no option shall let the agent approve for the user. When asking is impossible (headless run, subagent), the documented default shall be used for reversible choices, the assumption recorded in `brief.json` `notes`, and the run shall stop at the gate that needs a human. | S | T |
| FR-WFL-08 | The system shall give a read-only view of where a work set is in the workflow (`progress.py`, used by the `logs` skill): a vertical step timeline with the step in progress and its state (running, waiting for the user, stopped), the gates between steps, the next action, pending changes and a one-line form for a status line. It shall derive everything from recorded files, write nothing, need only the standard library, honor `NO_COLOR`, and label an approval made by an agent as not human. | S | T |
| FR-DEP-01 | The three upstream skills shall be installed separately, with repository origin and actual resolved files verified. Same-named skills from other repositories are not interchangeable. | M | T |
| FR-DEP-02 | The upstream commit SHA and relevant file SHA-256 values shall be recorded in `dependencies.lock.json`. A branch-based installation is not a lock. | M | T |
| FR-DEP-03 | Before writing an adapter, the installed `SKILL.md`, referenced files and actual script interfaces shall be inspected. Upstream filenames and arguments shall not be invented, and an upstream skill shall not be executed as a shell program. | M | I |
| FR-DEP-04 | Personal schemas shall be translated to upstream formats only through a tested adapter where required. | M | T |
| FR-DEP-05 | A missing dependency, origin mismatch or incompatible revision shall block the affected phase with an actionable message; independent phases may continue. | M | T |
| FR-DEP-06 | Ordinary generation runs shall not update dependencies or install over the network. Setup is separate and explicit. | M | T |
| FR-DEP-07 | A compatibility record shall list the Claude Code version tested, upstream revision, renderer version, OS, installation method and smoke-test results. Required licenses and notices shall be retained for copied or modified upstream material; third-party assets shall not be redistributed without checking provenance. | S | I |

## 5. External interfaces and data

### 5.1 Input contract

| Field | Requirement |
| --- | --- |
| `id` | Stable kebab-case identifier, unique case-insensitively |
| `meaning` | Functional meaning, e.g. "Open historical trend view" |
| `source_path` | Original reference location |
| `usage_locations` | Array such as toolbar, ribbon, menu, device-list, web-navigation |
| `sizes_px` | Required sizes for this icon, not only a set-wide default |
| `functional_group` | File/edit, navigation/layout, devices/connectivity, alarms/events, trends/reports, users/settings |
| `semantic_role` | Action, state, object, or navigation |
| `notes` | Optional ambiguity or design constraints |

### 5.2 Output layout

```text
icon-work/<set-id>/
  brief.json  inventory.json  icon-style.md  style-spec.json
  manifest.json  run-state.json  approvals.json
  masters/<icon-id>.svg
  variants/small/<icon-id>.svg
  preview/index.html  preview/renders/  preview/contexts/
  exports/web/<icon-id>.svg
  exports/desktop/<theme>/<state>/<size>/<icon-id>.png
  reports/reference-analysis.md  reports/pre-export-qa.json
  reports/post-export-qa.json    reports/review.md
  reports/application-validation.json
```

### 5.3 Repository and installation layout

Suggested repository name `industrial-icon-designer`. The implementer shall first inspect the supplied project directory and any `AGENTS.md` or `CLAUDE.md`, scaffold only into an empty project, never overwrite unrelated files, and assume no remote repository, credentials, reference assets or target application.

```text
industrial-icon-designer/
  README.md  CHANGELOG.md  LICENSE  THIRD_PARTY_NOTICES.md
  pyproject.toml  requirements.lock  dependencies.lock.json  .gitignore
  skills/industrial-icon-designer/
    SKILL.md
    references/  industrial-style.md  png-redraw-rules.md  dependency-routing.md
                 desktop-export.md  web-export.md  review-checklist.md
    schemas/     brief  inventory  style-spec  manifest  run-state  approvals
                 application-validation  (each *.schema.json)
    scripts/     doctor.py  inventory_icons.py  validate_icons.py
                 render_preview.py  export_assets.py
    assets/approved-examples/
  tests/fixtures/  tests/integration/
  examples/scada-demo/
  docs/  SRS.md  implementation-plan.md  dependency-compatibility.md
```

The canonical package lives in `skills/industrial-icon-designer/`. Installation copies or links it to `.claude/skills/industrial-icon-designer/` (project) or `~/.claude/skills/industrial-icon-designer/` (personal). Scripts resolve support files relative to the installed package, never to a developer-specific absolute path. User outputs live in the working project.

### 5.4 Claude Code and script interfaces

Proposed invocation conventions, not built-in commands:

```text
/industrial-icon-designer init refs=./references out=./icon-work/scada
/industrial-icon-designer analyze|pilot|generate|audit|export|validate-app|resume set=./icon-work/scada
/industrial-icon-designer extend set=./icon-work/scada icons=pump-stop,valve-open
```

Minimal frontmatter:

```yaml
---
name: industrial-icon-designer
description: Redesign industrial and SCADA UI icon sets from PNG or SVG references; maintain consistent SVG masters and export Light/Dark Desktop PNG and Web SVG assets.
---
```

Scripts (to be implemented; they do not describe existing upstream scripts):

```bash
python scripts/doctor.py --set ./icon-work/scada --json
python scripts/inventory_icons.py --input ./references --set ./icon-work/scada
python scripts/validate_icons.py --set ./icon-work/scada --phase source|exported
python scripts/render_preview.py --set ./icon-work/scada
python scripts/export_assets.py --set ./icon-work/scada --target all [--dry-run]
```

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| FR-IF-01 | Scripts shall be run from the installed package or resolved by the orchestrator; output paths remain in the user's project. | M | T |
| FR-IF-02 | `doctor.py` shall work without `--set` for greenfield capability checks, shall check dependencies without installing them, and shall report renderer name and version. | M | T |
| FR-IF-03 | With `--json`, scripts shall emit machine-readable results on stdout and diagnostics on stderr. | M | T |
| FR-IF-04 | Exit codes shall be 0 success, 2 input/configuration, 3 dependency, 4 validation, 5 rendering/write failure. | M | T |
| FR-IF-05 | Export shall never call an LLM. | M | T |

### 5.5 Data contracts

All JSON artifacts shall be validated against versioned schemas with field-specific errors. The examples describe the personal contract, not upstream formats.

```json
{
  "schema_version": "1.0",
  "set_id": "scada-core",
  "style_version": "1.0.0",
  "grid": 24,
  "stroke_width": 1.5,
  "linecap": "round",
  "linejoin": "round",
  "padding": 2,
  "preview_sizes_px": [16, 20, 24, 32],
  "default_export_sizes_px": [16, 20, 24, 32],
  "themes": {
    "light": {"background": "#FFFFFF", "normal": "#334155", "disabled": "#94A3B8"},
    "dark": {"background": "#1E293B", "normal": "#E2E8F0", "disabled": "#64748B"}
  },
  "states": ["normal", "disabled"],
  "small_variant_sizes_px": [16],
  "palette_status": "provisional_requires_review"
}
```

Optional: `style_mode` (`outline` default, `filled`, `duotone`), `duotone_secondary_opacity` (duotone only) and `consistency_overrides` (`{rule: {reason, value}}`). Inventory entries may carry `variant_of` and `variant_kind` (`filled`).

- Per-icon `sizes_px` overrides export defaults. Preview still includes the four mandatory sizes, with actual usage sizes identified. Additional DPI-derived bitmap sizes come from a target profile and are not implied by a display scaling percentage.
- Manifest icon fields (required): `id`, `meaning`, `semantic_role`, `functional_group`, `usage_locations`, `sizes_px`, `source_path`, `source_sha256`, `master_path`, `master_sha256`, `route`, `status`, `style_version`, `variants`, `qa`, `exports`; optional `notes`.
- `variants`: path/hash/size mapping; records an explicit fallback to master when no small variant is needed.
- `qa`: structural status, visual status (`pending/approved/rejected`), reviewer type (`user/agent`), report references.
- `exports`: target, theme/state when relevant, dimensions, path/hash, source hash, export-config hash.
- `approvals.json`: approval type, reviewer type, timestamp, scope, approved hashes.
- `application-validation.json`: context, target/profile, environment, IDs tested, exported hashes, status, reason, evidence.
- `run-state.json`: stage, dependency/config hashes, pending IDs, errors, resumable phase.
- A content change shall normally preserve the ID and update the set version.

### 5.6 Invalidation

| Change | Invalidate |
| --- | --- |
| Reference content | Interpretation/review of the affected icon |
| Geometry or optical variant | Related visual approvals, previews, exports, application evidence |
| Global geometry style | Pilot approval and affected icons/exports |
| Palette only | Color review, themed previews/exports, affected application evidence; geometry is not redrawn |
| Renderer/version | Related raster outputs and visual/post-export checks |
| Usage size or context | Relevant outputs and application-context checks |

## 6. Non-functional requirements

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| NFR-01 | Determinism: two consecutive exports with identical sources, config and tool versions shall produce files with identical SHA-256. LLM generation is not claimed deterministic. | M | T |
| NFR-02 | Recoverability: after an interrupted run, zero approved icons shall be regenerated on resume; only pending work continues. | M | T |
| NFR-03 | Traceability: every exported file shall be resolvable through `manifest.json` to its source hash, style version, approval and toolchain (100% of exports). | M | T |
| NFR-04 | Offline operation: preview, QA and export shall succeed with the network disabled after setup, and generated previews shall contain no CDN references. | M | T |
| NFR-05 | Diagnostics: every failure shall name the icon ID or file path, the failed check and a recovery action. A partial run shall report the counts of succeeded and failed items. | M | T |
| NFR-06 | Portability: the installed package shall contain no developer-specific absolute paths. | M | T |
| NFR-07 | Timing: scripts shall log render and export time separately from model time. No latency SLA is set until measured (OI-02). | S | T |
| NFR-08 | Paths with spaces and Unicode shall work on WSL2/Linux. | M | T |

## 7. Security and preservation requirements

| ID | Requirement | Pri | Ver |
| --- | --- | --- | --- |
| SEC-01 | Input SVG and metadata shall be treated as untrusted. Masters shall reject scripts, event handlers, external resource references, `foreignObject`, DTD/entities and embedded raster. | M | T |
| SEC-02 | Preview HTML shall escape labels and shall never embed unvalidated input SVG as executable page content. | M | T |
| SEC-03 | Subprocesses shall use argument arrays, not shell interpolation. | M | T |
| SEC-04 | The system shall reject path traversal and case-insensitive filename collisions and shall not follow symlinks outside configured roots. | M | T |
| SEC-05 | Default guardrails, configurable: 10 MiB per input, 4096×4096 raster dimensions, 200 icons per run. Exceeded limits shall be reported with a configuration path, not skipped silently. | M | T |
| SEC-06 | Originals and unrelated project files shall be preserved. | M | T |
| SEC-07 | Reading images through Claude Code may transmit their content to the configured model service. Assets shall not be sent to additional third-party generation or conversion services without task authorization. | M | I |
| SEC-08 | No artifact shall contain API secrets or unrelated private transcripts. The system shall not change global Claude settings, install dependencies during ordinary runs, or commit, push or publish automatically. | M | I |
| SEC-09 | Masters and small variants shall contain no comments, processing instructions or CDATA (a browser can end them early and run what follows when the SVG is inlined). Set subdirectories shall not resolve outside the set. Unresolved-meaning (`NEEDS_REVIEW`) icons shall not be approved. | M | T |

## 8. Industrial design rules

| ID | Rule | Ver |
| --- | --- | --- |
| DR-01 | Prefer clear, compact geometry and deliberate negative space over decoration. | I |
| DR-02 | Keep stroke, caps, joins and recurring parts consistent. | I |
| DR-03 | Balance perceived size; identical bounding boxes are insufficient. | I |
| DR-04 | Preserve geometry across themes; change palette tokens only. | T |
| DR-05 | Use an explicit disabled token rather than relying solely on opacity. | T |
| DR-06 | Icons are monochrome in the forms `outline`, `filled` and `duotone` (one colour, two opacities). A real second colour needs an explicit token contract. | I |
| DR-07 | Do not imply red/yellow/green equipment states without approved semantic rules. | I |
| DR-08 | Provisional colors shall never be described as the user's official brand palette. | I |
| DR-09 | Small variants may remove details but shall preserve meaning. | I |
| DR-10 | This workflow does not certify compliance with industrial safety standards. | I |

## 9. Verification

### 9.1 Fixtures

Ten representative fixtures: save, open-folder, settings, add, alarm-list, trend-chart, pump, valve, device-connect and network. They include PNGs, SVGs, an ambiguous image and intentionally invalid files, and are identified as synthetic.

### 9.2 Acceptance tests

| ID | Scenario | Expected evidence |
| --- | --- | --- |
| AT-01 | Empty project bootstrap and skill discovery | Package installed/discovered; doctor works without references |
| AT-02 | Missing, wrong-origin or changed dependency | Clear blocked phase; no silent substitution or update |
| AT-03 | Inventory with usage metadata | IDs, meanings, groups, sizes, locations preserved; sources unchanged |
| AT-04 | PNG redraw | Editable vector geometry, no embedded PNG; before/after review |
| AT-05 | Ambiguous meaning | NEEDS_REVIEW, not automatically approved |
| AT-06 | Existing SVG analysis | Baseline audit and selected redesign mode recorded |
| AT-07 | Style outputs | `icon-style.md` and `style-spec.json` agree; style modes keep old hashes and report consistency findings with suggestions |
| AT-08 | Pilot and gate | 8–12 icons or documented exception; no full generation before valid approval |
| AT-09 | Context preview | Four sizes, two themes/states, comparison and Desktop/Web context views |
| AT-10 | Batch generation | Functional grouping, shared parts, per-batch checkpoints; filled variants paired with their base |
| AT-11 | Invalid/clipped source | Structural failure or visual finding with affected ID; not export-eligible |
| AT-12 | Full export fixture matrix | 10 icons × 4 sizes × 2 themes × 2 states = 160 PNGs, plus 10 inline Web SVGs |
| AT-13 | Per-icon size override | Output count follows inventory; irrelevant sizes not exported |
| AT-14 | Theme/alpha and post-export QA | Correct RGBA dimensions, transparent backgrounds, palette, content mapping, duotone secondary alpha |
| AT-15 | Web consumption profiles | Inline `currentColor` works; `img` profile uses resolved color |
| AT-16 | Repeat export | Identical asset hashes; original references unchanged |
| AT-17 | Interrupt and resume | Approved batches retained; pending work continued |
| AT-18 | Invalidation | Only affected outputs/reviews rerun; stale approval rejected |
| AT-19 | Hostile input/path | Safe rejection; no external fetch or out-of-root write |
| AT-20 | Manual export edits/unknown files | Conflict report; no silent overwrite or delete |
| AT-21 | Space/Unicode paths | Inventory, render, export succeed on declared runtime |
| AT-22 | Desktop validation | Toolbar, Ribbon, menu, device-list records; themes/states; 100/125/150/200% scaling |
| AT-23 | Web validation | Navigation, actions, list contexts; browser/theme/state evidence |
| AT-24 | Missing application access | ASSETS_READY, actual contexts not-tested; no APPLICATION_VALIDATED claim |
| AT-25 | Maintenance addition | Duplicate-meaning check, consistent extension, regenerated outputs, version/changelog |
| AT-26 | Greenfield automated run | Synthetic fixture pipeline runs without application repo or private assets |

The 160 PNG count applies only to AT-12's uniform configuration. Production counts follow each icon's sizes, themes and states; resolved-color Web variants are counted separately.

### 9.3 Traceability

| Acceptance test | Verifies |
| --- | --- |
| AT-01 | FR-WFL-03, FR-WFL-06, FR-WFL-07, FR-IF-01, FR-IF-02, NFR-06 |
| AT-02 | FR-DEP-01, FR-DEP-02, FR-DEP-03, FR-DEP-04, FR-DEP-05, FR-DEP-06, FR-DEP-07 |
| AT-03 | FR-INV-01, FR-INV-02, FR-INV-03, FR-INV-04 |
| AT-04 | FR-ANA-02, FR-PIL-01, FR-GEN-02, FR-GEN-03 |
| AT-05 | FR-INV-05 |
| AT-06 | FR-INV-06, FR-ANA-03, FR-ANA-04, FR-ANA-05 |
| AT-07 | FR-SPC-01, FR-SPC-02, FR-SPC-03, FR-SPC-04, FR-SPC-05 |
| AT-08 | FR-ANA-01, FR-PIL-05, FR-QA-02 |
| AT-09 | FR-PIL-02, FR-PIL-03, FR-PIL-04, DR-01, DR-02, DR-03, DR-06, DR-07, DR-08, DR-09, DR-10 |
| AT-10 | FR-GEN-01, FR-GEN-04, FR-GEN-05, FR-WFL-02 |
| AT-11 | FR-QA-01, FR-QA-04 |
| AT-12 | FR-EXP-01, FR-EXP-02, FR-EXP-04, DR-04, DR-05 |
| AT-13 | FR-EXP-01 |
| AT-14 | FR-QA-03, FR-QA-05, FR-QA-06, FR-EXP-05, FR-IF-03, FR-IF-04, FR-IF-05 |
| AT-15 | FR-EXP-02, FR-EXP-03 |
| AT-16 | FR-EXP-06, FR-INV-02, FR-WFL-05, NFR-01, NFR-03 |
| AT-17 | FR-WFL-01, FR-WFL-02, FR-WFL-08, NFR-02, NFR-05 |
| AT-18 | FR-MNT-03, FR-PIL-05, FR-WFL-05 |
| AT-19 | SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-09 |
| AT-20 | FR-EXP-07, FR-EXP-08 |
| AT-21 | NFR-08 |
| AT-22 | FR-APP-01, FR-APP-02, FR-EXP-05 |
| AT-23 | FR-APP-01, FR-APP-03 |
| AT-24 | FR-APP-04, FR-APP-05, FR-APP-06, FR-WFL-04 |
| AT-25 | FR-MNT-01, FR-MNT-02 |
| AT-26 | FR-WFL-03, FR-WFL-04, NFR-04, NFR-07 |

Requirements verified by inspection only and not covered by a test above: SEC-07, SEC-08 (reviewed against the implementation at each milestone). Requirement coverage is checked mechanically: every `FR-*`, `SEC-*`, `NFR-*` and `DR-*` ID shall appear in this table or in the inspection list above.

## 10. Delivery

### 10.1 Milestones

1. **M1 Foundation:** scaffold, schemas, dependency resolution/lock, doctor, inventory. AT-01/02/03/21.
2. **M2 Reference and pilot:** baseline audit, redesign modes, style outputs, PNG redraw, context preview, approval gate. AT-04–09.
3. **M3 Production and source QA:** functional batches, manifest, checkpoints, upstream adapters, safe validation. AT-10/11/17/18/19.
4. **M4 Export and post-export QA:** palette resolution, raster renderer, Web profiles, dry-run, conflict handling. AT-12–16/20.
5. **M5 Handoff and maintenance:** demo, documentation, application-validation records, extension/versioning. AT-22–26; actual-application tests may remain `not-tested` only with explicit reporting.

The implementer shall start with M1, resolve the upstream revisions, and write a milestone checklist in `docs/implementation-plan.md`. Do not install every repository mentioned in prior research and do not implement deferred features as prerequisites. Proceed with infrastructure and synthetic fixtures when private references are unavailable; request real references when the design pilot begins. Ask only for information that materially changes semantics or design, and preserve approved decisions. For each milestone, report changes, executed checks, evidence and limitations, and distinguish source quality, export success and application validation.

Suggested kickoff instruction:

> Implement this greenfield project according to docs/SRS.md. Start with M1, inspect applicable repository instructions, establish the package structure and dependency compatibility record, then run the M1 acceptance checks. Continue through independently executable milestones. Present the design pilot for review before generating the full user icon set. Do not commit, push, publish or modify a target application unless explicitly requested.

### 10.2 Definition of Done

**Skill implementation ready** — all of:
- Installable in a clean Claude Code project; tested environment documented.
- Upstream sources and toolchain verified and locked.
- Mandatory automated tests pass; visual pilot review recorded.
- Ten-icon example with SVG masters, mapping, synchronized style documents, context previews and reports.
- Fixture export produces the expected 160 PNGs and 10 inline Web SVGs.
- Resume, invalidation, conflict handling and deterministic export demonstrated.
- README documents setup, usage, troubleshooting, uninstall and limitations.
- Application validation is implemented and reports honest statuses, including lack of target access.

**Icon set assets ready:** all requested icon IDs have valid source/visual review and post-export checks, with no unresolved semantic defects or missing required assets. Pending application tests remain visible.

**Icon set application validated:** every required Desktop/Web actual context passed with current exported hashes and environment evidence. An inapplicable context shall be removed from the required target profile explicitly with a reason, never counted as passed.

A greenfield repository can satisfy implementation readiness without a user application; it cannot claim that the user's icon set is validated in that application until evidence exists.

## 11. Open issues

| ID | Issue | Resolve by |
| --- | --- | --- |
| OI-01 | Select and lock Python dependency versions and the pinned renderer. `resvg` is a Rust CLI (install via `cargo install resvg` or a release binary), not an npm package named `@aspect-build/resvg`. | Resolved in M1: Python 3.11.13, `requirements.lock`, resvg 0.48.1 |
| OI-02 | Set a measurable export-time target for NFR-07 after the first benchmark. | Measured: 170 exports in about 15 s on the development machine; proposed goal 30 s for that set. Needs the owner's decision |
| OI-03 | Determine DevExpress 15.1.11 PNG/DPI behavior for the Desktop profile. | M5 |
| OI-04 | Decide whether native Windows execution is needed. | After M5 |
| OI-05 | Audit the actual interfaces of the three `shadcn-labs` skills at the selected revision. | Resolved in M1: interfaces recorded in `upstream_adapter.py`, commit locked in `dependencies.lock.json` |
| OI-06 | Verify skill discovery on the tested Claude Code version. | Resolved: Claude Code 2.1.305 listed the project skill and the three upstream skills from `.claude/skills/` |
| OI-07 | Define the required application-context profile (which contexts count for `APPLICATION_VALIDATED`). | Default recorded in `brief.json`: Desktop toolbar, ribbon, menu, device list; Web navigation, actions, list. Removing one needs a reason; owner to confirm |

## Appendix A. Change from 1.1 to 2.0

Restructured to ISO/IEC/IEEE 29148 sections. Atomic IDs, priority and verification added to every requirement; acceptance tests mapped to requirements (9.3); NFRs rewritten to be measurable; glossary, stakeholders, constraints, assumptions, risks and open issues added; design layout and script interfaces moved under external interfaces. The renderer risk (R-06, C-04) and the `resvg` installation correction (OI-01) were added from direct experience with this project. No design decision from 1.1 was changed: the 8–12 pilot, three redesign modes, approval gate, batch sizes, state model, export profiles, definitions of done and MVP scope are unchanged.

Old-to-new requirement map:

| 1.1 | 2.0 |
| --- | --- |
| FR-01 | FR-INV-01, FR-INV-02 |
| FR-02 | FR-INV-03 |
| FR-03 | FR-ANA-02 |
| FR-04 | FR-ANA-03, FR-ANA-04 |
| FR-05 | FR-SPC-01, FR-SPC-02 |
| FR-06 | FR-PIL-01, FR-PIL-05 |
| FR-07 | FR-PIL-02, FR-PIL-03 |
| FR-08 | FR-GEN-01 |
| FR-09 | FR-GEN-03 |
| FR-10 | FR-QA-01 to FR-QA-05 |
| FR-11 | FR-EXP-01 |
| FR-12 | FR-EXP-02, FR-EXP-03 |
| FR-13 | FR-WFL-02, FR-MNT-03 |
| FR-14 | FR-WFL-05, FR-DEP-02 |
| FR-15 | FR-APP-05 |
| FR-16 | FR-APP-01, FR-APP-04 |
| FR-17 | FR-MNT-01, FR-MNT-02 |
| FR-18 | FR-WFL-03 |
| NFR-01 to NFR-08 | NFR-01 to NFR-08 (same numbers; criteria made measurable) |
| AT-01 to AT-26 | AT-01 to AT-26 (unchanged) |

### Changes from 2.0 to 2.1

Added FR-EXP-08, FR-APP-06 and SEC-09 after an independent review of the implementation found gaps the 2.0 text did
not state: export gates (current pilot approval, palette review, drift, single writer), the rule that nothing is
validated when no required context remains or changes are pending, and the ban on comments and processing
instructions in masters. Open-issue statuses were updated. No earlier requirement was changed or withdrawn.

### Changes from 2.1 to 2.2

Added FR-WFL-07: the skill asks the user's decisions as structured multiple-choice questions and records user approval only from a real answer. The question catalog is `skills/industrial-icon-designer/references/questions.md` and is checked against the tool's limits by `tests/test_skill_questions.py`. No earlier requirement was changed or withdrawn.

### Changes from 2.2 to 2.3

Added FR-WFL-08: a read-only progress view (`progress.py` and the `logs` skill) with a vertical step timeline, status-line form and JSON, covered by `tests/integration/test_progress.py`. No earlier requirement was changed or withdrawn.

## Appendix B. Revision history

| Version | Changes |
| --- | --- |
| 1.0 | Initial Vietnamese specification for a personal Claude Code icon skill |
| 1.1 | Full English rewrite; eight workflow stages; per-icon usage metadata; audit and redesign modes; 8–12 pilot; post-export checks; application validation; expanded acceptance tests |
| 2.0 | Restructured to 29148; atomic traceable requirements; measurable NFRs; risks, constraints, open issues; renderer and `resvg` corrections; no design decision changed |
| 2.1 | Implementation status and open issues updated; FR-EXP-08, FR-APP-06, SEC-09 added from review findings |
| 2.2 | FR-WFL-07 added: structured user questions with a human-only approval rule |
| 2.3 | FR-WFL-08 added: read-only progress view (`logs`) |
