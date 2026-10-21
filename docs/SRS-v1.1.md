# Software Requirements Specification
# Industrial Icon Designer for Claude Code

| Field | Value |
| --- | --- |
| Document version | 1.1 |
| Date | 2026-10-21 |
| Implementation status | Specification only; implementation and runtime compatibility remain to be verified |
| Project type | Greenfield personal skill project |
| Skill name | `industrial-icon-designer` |
| Document and implementation language | English |
| Primary runtime | Claude Code on WSL2/Linux |
| Primary deliverables | Reusable skill package, SVG masters, Desktop PNG assets, Web SVG assets, review evidence |

## 1. Purpose

Build a personal Claude Code skill that redesigns existing PNG/SVG icon sets into a consistent industrial/SCADA visual system. Preserve recognizable functional meaning, maintain one authoritative SVG source set, and generate platform-specific assets through repeatable scripts.

The mandatory product workflow is:

1. Inventory the existing icons and their usage.
2. Analyze representative references and select a redesign direction.
3. Establish and approve the icon specification.
4. Create and review a small pilot set.
5. Generate the complete SVG set in functional batches.
6. Export assets for Desktop and Web applications.
7. Validate exported assets and inspect them in realistic and actual interfaces.
8. Maintain and extend the set using the approved specification.

The project starts in a new repository. It must not depend on an existing application repository, existing resource collection, preinstalled personal scripts, or private prior conversation context. Reference icons and target application access are supplied separately.

## 2. Architecture decisions

### 2.1 Reuse rather than reimplement

Version 1 consists of one personal orchestration skill, three separately installed upstream skills, and local processing scripts.

| Component | Responsibility |
| --- | --- |
| Personal orchestrator | Intake, reference interpretation, routing, approvals, checkpoints, handoff |
| `shadcn-labs/icon-set-generator` | Apply upstream guidance for generating a consistent SVG family |
| `shadcn-labs/icon-set-extend` | Apply upstream guidance for additions to an approved SVG family |
| `shadcn-labs/icon-set-audit` | Inspect consistency of the existing and generated SVG sets |
| Claude Code image-capable model/tools | Inspect PNG references and redraw vector geometry |
| Local scripts | Inventory, schemas, rendering, previews, export, hashes and reports |
| User | Resolve ambiguous meaning and approve visual design |

A skill is instructions and supporting tools, not an independent model or autonomous service. Reading PNG references requires image-capable tools and a suitable model. Installing a skill does not add that capability.

No verified native PNG-to-SVG tracing capability is assumed for shadcn-labs. The default PNG route is visual interpretation followed by vector redraw. Automated tracing is an optional future adapter.

### 2.2 Scope boundaries

Mandatory MVP:

- PNG/SVG references and JSON/CSV semantic inventories.
- Stable icon IDs and mapping to original filenames.
- Reference analysis, three explicit redesign modes, initial SVG audit.
- Human-readable and machine-readable style specifications.
- An 8–12 icon pilot, approval gate, and batches of 5–10 icons.
- Preview at 16, 20, 24 and 32 pixels, Light/Dark, normal/disabled.
- Real SVG masters, optional small-size variants, themed transparent PNGs and Web SVGs.
- Structural QA, visual QA, post-export QA and application validation status.
- Resume, dependency locking, provenance, versioning and a maintenance workflow.

Deferred:

- Training models, generating raster concepts through additional paid providers.
- Potrace/multicolor tracing, multi-agent orchestration, MCP server.
- React component generation, icon fonts, Figma integrations.
- Brand/launcher icon design, ICO/ICNS packaging.
- Automatic integration into application source code or runtime theme switching.
- Native Windows execution until explicitly tested; WSL2 is the initial supported execution environment.

Application icons and UI toolbar icons are separate design problems. The former must not be silently added to this MVP.

## 3. Greenfield bootstrap

### 3.1 New repository

Suggested repository name: `industrial-icon-designer`.

The implementer shall first inspect the supplied project directory and any applicable `AGENTS.md` or `CLAUDE.md`. If empty, scaffold the repository below. Do not assume a remote repository, credentials, reference assets, or target application exists. Never overwrite unrelated files. Creating the project does not authorize creating a remote repository or publishing it.

```text
industrial-icon-designer/
  SRS.md
  README.md
  CHANGELOG.md
  LICENSE
  THIRD_PARTY_NOTICES.md
  pyproject.toml
  requirements.lock
  dependencies.lock.json
  .gitignore
  skills/
    industrial-icon-designer/
      SKILL.md
      references/
        industrial-style.md
        png-redraw-rules.md
        dependency-routing.md
        desktop-export.md
        web-export.md
        review-checklist.md
      schemas/
        brief.schema.json
        inventory.schema.json
        style-spec.schema.json
        manifest.schema.json
        run-state.schema.json
        approvals.schema.json
        application-validation.schema.json
      scripts/
        doctor.py
        inventory_icons.py
        validate_icons.py
        render_preview.py
        export_assets.py
      assets/approved-examples/
  tests/
    fixtures/
    integration/
  examples/
    scada-demo/
  docs/
    implementation-plan.md
    dependency-compatibility.md
```

The canonical package lives in `skills/industrial-icon-designer/`. Installation copies or links that directory into the chosen Claude Code skill location. Scripts resolve their support files relative to the installed package, never relative to a developer-specific absolute path. User outputs live in the working project, not the installed skill directory.

### 3.2 First-run behavior

- Run capability/dependency checks before generation.
- If references are absent, allow scaffolding and synthetic test fixtures; clearly label these as fixtures, not user-approved artwork.
- If brand colors are absent, use a clearly labeled provisional palette for the pilot.
- If the target application is absent, generate standalone context previews and mark actual-application validation `not-tested`.
- Missing references or application access must not prevent independent infrastructure implementation.
- Distinguish “skill implementation ready” from “this icon set validated in a production application.”

## 4. Runtime and dependency management

### 4.1 Runtime baseline

Proposed baseline: Python 3.11+, Pillow, a JSON Schema validator, a safely configured XML parser, and one pinned SVG renderer, preferably resvg. Final versions must be selected and locked during implementation. Node.js is required only if the selected installer/renderer/optimizer uses it. SVGO is optional; any optimization must be followed by rendering checks.

Generation uses the configured Claude Code model. Validation, rendering and export shall work locally without network after setup. Do not claim that model-assisted image interpretation runs offline.

The developer's likely Desktop target is DevExpress 15.1.11. Use a conservative PNG export profile. Do not assume SVG loading, automatic recoloring, or DPI behavior in any particular control until tested.

### 4.2 Upstream skill contract

1. Install the three skills from `https://github.com/shadcn-labs/skills` separately.
2. Verify repository origin and the actual resolved files; identical skill names from other repositories are not interchangeable.
3. Record the upstream commit SHA and relevant file SHA-256 values in `dependencies.lock.json`.
4. Inspect each installed `SKILL.md`, referenced files and actual script interfaces before writing an adapter.
5. Resolve dependencies from configured/discovered installation paths. Do not invent upstream filenames or arguments.
6. Use Claude Code's available skill mechanism, or explicitly read and apply the resolved instructions in the current session. Naming another skill is not an API call or an installer.
7. Never execute `/icon-set-generator` as a shell program.
8. Translate personal schemas to upstream formats in an adapter only where required; test the mapping.
9. A missing dependency, origin mismatch or incompatible revision blocks the affected phase with an actionable message. Independent phases may continue.
10. No dependency updates or network installation during ordinary generation runs. Setup is separate and explicit.

Documentation may show `npx skills add shadcn-labs/skills --skill icon-set-generator` and equivalent commands as bootstrap examples. A branch-based installation is not a lock: the implementer must record and verify the exact revision used afterward.

Maintain a compatibility record containing the Claude Code version tested, upstream revision, renderer version, OS, installation method and smoke-test results. Retain required licenses and notices if upstream material is copied or modified. Do not redistribute third-party assets without checking their provenance.

## 5. Inputs and output layout

### 5.1 Input contract

Accept individual PNG/SVG files or directories. JSON/CSV inventory fields:

| Field | Requirement |
| --- | --- |
| `id` | Stable kebab-case identifier, unique case-insensitively |
| `meaning` | Functional meaning, e.g. “Open historical trend view” |
| `source_path` | Original reference location |
| `usage_locations` | Array such as toolbar, ribbon, menu, device-list, web-navigation |
| `sizes_px` | Required sizes for this icon, not only a set-wide default |
| `functional_group` | File/edit, navigation/layout, devices/connectivity, alarms/events, trends/reports, users/settings |
| `semantic_role` | Action, state, object, or navigation |
| `notes` | Optional ambiguity or design constraints |

Missing information may be inferred only with an explicit confidence/note; unresolved meaning must be reviewed before the icon is approved. If both PNG and SVG represent the same icon, prefer the SVG for geometry analysis while retaining both references. Identify conflicting meanings or versions instead of silently choosing one.

Do not confuse an action such as `device-connect` with a state such as `device-connected`.

### 5.2 Output layout

```text
icon-work/<set-id>/
  brief.json
  inventory.json
  icon-style.md
  style-spec.json
  manifest.json
  run-state.json
  approvals.json
  masters/<icon-id>.svg
  variants/small/<icon-id>.svg
  preview/index.html
  preview/renders/
  preview/contexts/
  exports/web/<icon-id>.svg
  exports/desktop/<theme>/<state>/<size>/<icon-id>.png
  reports/reference-analysis.md
  reports/pre-export-qa.json
  reports/post-export-qa.json
  reports/review.md
  reports/application-validation.json
```

`masters/` is the authoritative editable SVG set. Small variants are explicit exceptions mapped to sizes. Exported files are derived artifacts and must not become the source of truth. Original references remain unchanged; inventory records their path and content hash.

## 6. Mandatory design workflow

### Stage 1 — Inventory and semantics

Inspect source files, dimensions, alpha, hashes, duplicates, filename collisions and usage metadata. Produce inventory and a concise unresolved-items list. Map existing names to stable IDs; never rename application-facing IDs silently.

### Stage 2 — Analyze references and select direction

Select 8–12 representative icons covering simple marks, familiar commands, specialized equipment and dense symbols. For fewer than eight available icons, review all and record the exception. For SVG input, apply `icon-set-audit` before redesign; preserve baseline findings. For PNG, perform visual reference analysis and label interpretations as such.

Record one of three explicit redesign modes in the brief:

| Mode | Meaning |
| --- | --- |
| `normalize` | Preserve shape; standardize stroke, color and alignment |
| `redraw` | Preserve functional meaning; redesign geometry; default recommendation |
| `reinterpret` | Change the visual metaphor; requires explicit semantic approval |

Do not use `reinterpret` merely because a source icon is difficult to recognize. Request clarification first. Produce `reports/reference-analysis.md` with the selected sample, current inconsistencies, proposed direction and rationale. The pilot later supplies the before/after comparison.

### Stage 3 — Establish the specification

Produce both `icon-style.md` and `style-spec.json` before batch generation. The JSON is authoritative for structured parameters; the Markdown explains rationale, shared geometry, exceptions and examples. A validation check must detect contradictory values between them; regenerate the explanatory parameter summary when JSON changes.

Define grid, stroke, cap/join, corner treatment, safe padding, optical balance, common parts, theme tokens, states, size variants and export profiles. Use 24×24 as a starting grid and compare stroke widths 1.5 and 2 during the pilot. These are configurable starting points, not universal standards.

### Stage 4 — Pilot and approval

Use `icon-set-generator` guidance to redraw the selected 8–12 icons. Preview each reference/new pair at 16/20/24/32 px on Light/Dark surfaces with normal/disabled states. Show enlarged views only as a supplement to actual-size views.

Include standalone toolbar, menu, Ribbon-like and device-list contexts with labels and surrounding UI elements. Also provide Web navigation/action contexts. These are simulations, explicitly distinct from the actual target application.

Review recognizability, small-size gaps, optical weight, confusingly similar meanings and accidental alarm-state color implications. Create an explicit small variant if necessary; do not assume arbitrary downscaling produces a good 16 px result.

Record approval against the style hash and pilot asset hashes. The user approves the pilot before full generation. Ask again only for unresolved semantics or material style changes. If the user explicitly authorizes unattended operation, record agent review separately; never label it human approval.

### Stage 5 — Functional batch generation

Generate batches of 5–10 icons within functional groups. Reuse arrowheads, gears, badges and other shared geometry. Inspect each batch next to related icons before continuing. Save checkpoints after every batch. Apply `icon-set-extend` when adding to the approved family.

Write actual vector geometry: paths and shapes. Do not wrap PNG data in an SVG and call it vector conversion. Do not silently auto-trace source pixels in the redraw route.

### Stage 6 — Pre-export QA and export

Run structural validation and visual review on masters and variants. Only eligible icons may enter final exports; pending drafts remain available for preview.

Export transparent PNGs using the approved Desktop palette, per-icon size requirements and state matrix. Render directly at each target size, not by upscaling a small PNG. Export Web SVGs with explicit consumption profiles:

- Inline monochrome SVG: use `currentColor` and document accessibility expectations in the consuming UI.
- SVG used through an `img` element: resolve colors or generate explicitly selected variants; do not promise inherited host CSS color through `img`.

Desktop SVG export, React components and ICO are deferred profiles, not silently enabled targets.

### Stage 7 — Post-export and application validation

First inspect the actual generated files: size, alpha, colors, mapping, completeness, clipping and visual quality. This is separate from source SVG QA.

Then validate representative exported assets in Desktop toolbar, Ribbon, menu and device-list screens and in Web navigation, toolbar/action and list contexts. Test both themes and supported states. For Desktop, inspect display scaling at 100%, 125%, 150% and 200%, recording the framework/control behavior. Record browser/version and relevant rendering conditions for Web.

Each target context must have a status of `passed`, `failed`, or `not-tested`, a reason, environment, tested icon IDs and evidence reference. Screenshot paths are optional evidence where capture is available; a precise manual checklist is also acceptable. Actual application changes are out of scope unless requested. The user may integrate assets and supply evidence for review.

If target application access is unavailable, deliver the asset package as `ASSETS_READY`, with actual-application validation `not-tested`. Do not claim `APPLICATION_VALIDATED` or mark the complete delivery criterion as met. A synthetic preview cannot substitute for an actual application test.

### Stage 8 — Maintenance

Before adding an icon, inspect the manifest for duplicate meaning. Apply `icon-set-extend` with the style and approved samples, run source QA, regenerate affected outputs, run post-export checks and update the asset-set version/changelog. Revalidate affected application contexts when geometry, palette or rendering behavior changes.

## 7. Functional requirements

| ID | Requirement |
| --- | --- |
| FR-01 | Preserve reference files and generate inventory with semantic and usage metadata |
| FR-02 | Enforce stable, case-insensitive unique IDs and source-to-output mapping |
| FR-03 | Separate PNG interpretation/redraw from native SVG processing and optional tracing |
| FR-04 | Audit existing SVG references before design and record one of three redesign modes |
| FR-05 | Maintain synchronized human-readable and machine-readable style specifications |
| FR-06 | Produce and approve an 8–12 icon pilot, with a documented small-input exception |
| FR-07 | Preview 16/20/24/32 px, both themes and states, in comparison and UI context views |
| FR-08 | Generate functional batches of 5–10 using shared geometry and stable style rules |
| FR-09 | Store SVG masters and explicitly mapped optical variants; reject embedded raster masters |
| FR-10 | Distinguish structural, visual, pre-export, post-export and actual-application QA |
| FR-11 | Generate Desktop RGBA PNGs according to per-icon export requirements |
| FR-12 | Distinguish inline-currentColor and resolved-color Web SVG consumption |
| FR-13 | Resume from checkpoints and invalidate only affected outputs/reviews |
| FR-14 | Track provenance, dependency versions, errors, approvals and remaining limitations |
| FR-15 | Avoid modifying target application code without task authorization |
| FR-16 | Record application-context validation and distinguish ASSETS_READY from APPLICATION_VALIDATED |
| FR-17 | Support extension, duplicate-meaning checks, asset-set version updates and changelog entries |
| FR-18 | Bootstrap and test in a new repository without access to an existing application |

## 8. Industrial design rules

- Prefer clear, compact geometry and deliberate negative space over decoration.
- Keep stroke, caps, joins and recurring parts consistent.
- Balance perceived size; identical bounding boxes are insufficient.
- Preserve the geometry across themes; change palette tokens.
- Use an explicit disabled token rather than relying solely on opacity.
- Primary MVP icons are monochrome. Filled areas are allowed when consistent with the approved design; secondary color/duotone requires a later explicit token contract.
- Do not imply red/yellow/green equipment states without approved semantic rules.
- Provisional colors must never be described as the user's official brand palette.
- Small variants may remove details but must preserve meaning.
- This design workflow does not certify compliance with industrial safety standards.

## 9. Data contracts

All JSON artifacts shall be validated against versioned schemas with field-specific errors. Examples below describe the proposed personal contract, not upstream shadcn-labs formats.

### 9.1 Style specification example

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

Preview backgrounds are not exported into transparent PNGs. For normal icons, target a 3:1 foreground/background contrast ratio on declared backgrounds. Report disabled contrast separately. This token-level check does not replace visual review or establish application-wide accessibility compliance.

Per-icon `sizes_px` overrides export defaults. Preview still includes the four mandatory sizes for comparison, with actual usage sizes identified. Additional DPI-derived bitmap sizes may be configured by a target profile; they are not automatically implied by a display scaling percentage.

### 9.2 Manifest and related artifacts

Every manifest icon requires: `id`, `meaning`, `semantic_role`, `functional_group`, `usage_locations`, `sizes_px`, `source_path`, `source_sha256`, `master_path`, `master_sha256`, `route`, `status`, `style_version`, `variants`, `qa`, `exports`, and optional `notes`.

- `variants`: path/hash/size mapping; explicitly record fallback to master when no small variant is needed.
- `qa`: structural status, visual status (`pending/approved/rejected`), reviewer type (`user/agent`), report references.
- `exports`: target, theme/state when relevant, dimensions, path/hash, source hash and export-config hash.
- `approvals.json`: approval type, reviewer type, timestamp, scope and approved hashes.
- `application-validation.json`: context, target/profile, environment, IDs tested, exported hashes, status, reason and evidence.
- `run-state.json`: stage, dependency/config hashes, pending IDs, errors and resumable phase.
- No artifact shall contain API secrets or unrelated private transcripts.

An approved user-facing ID must not be renamed without an explicit migration map. A content change should normally preserve the ID and update the set version.

### 9.3 Invalidation

| Change | Invalidate |
| --- | --- |
| Reference content | Interpretation/review of the affected icon |
| Geometry or optical variant | Related visual approvals, previews, exports and application evidence |
| Global geometry style | Pilot approval and affected icons/exports |
| Palette only | Color review, themed previews/exports and affected application evidence; do not redraw geometry |
| Renderer/version | Related raster outputs and visual/post-export checks |
| Usage size or context | Relevant outputs and application-context checks |

Stale approval hashes must never be accepted. Logs and prior review evidence remain available for history.

## 10. State model

Normal production stages:

`NEW → INVENTORIED → REFERENCES_ANALYZED → SPEC_READY → PILOT_READY → PILOT_APPROVED → GENERATING → SOURCE_QA_PASSED → EXPORTED → POST_EXPORT_QA_PASSED → ASSETS_READY`

Application validation is tracked per context. A set reaches `APPLICATION_VALIDATED` only when all required actual contexts pass; it may then reach `COMPLETE`. If context access is missing, keep `ASSETS_READY` and expose `not-tested` entries. Failed contexts require revision and revalidation.

Exceptional states: `BLOCKED`, `NEEDS_REVIEW`, `FAILED`; preserve the last valid stage and recovery action. Never mark an entire run successful while silently dropping failed icons.

## 11. Claude Code interface

Install to `.claude/skills/industrial-icon-designer/` for a project or `~/.claude/skills/industrial-icon-designer/` for personal use. Verify discovery on the tested Claude Code version.

Proposed invocation conventions, not built-in commands:

```text
/industrial-icon-designer init refs=./references out=./icon-work/scada
/industrial-icon-designer analyze set=./icon-work/scada
/industrial-icon-designer pilot set=./icon-work/scada
/industrial-icon-designer generate set=./icon-work/scada
/industrial-icon-designer extend set=./icon-work/scada icons=pump-stop,valve-open
/industrial-icon-designer audit set=./icon-work/scada
/industrial-icon-designer export set=./icon-work/scada
/industrial-icon-designer validate-app set=./icon-work/scada
/industrial-icon-designer resume set=./icon-work/scada
```

Minimal proposed frontmatter:

```yaml
---
name: industrial-icon-designer
description: Redesign industrial and SCADA UI icon sets from PNG or SVG references; maintain consistent SVG masters and export Light/Dark Desktop PNG and Web SVG assets.
---
```

Use concise core instructions and load references by phase. Do not introduce hidden shell execution or request unrestricted permissions. The agent should infer routine defaults from project data and ask only for unresolved meanings, pilot approval or material design changes.

## 12. Local script interfaces

The following interfaces must be implemented; they do not describe existing upstream scripts.

```bash
python scripts/doctor.py --set ./icon-work/scada --json
python scripts/inventory_icons.py --input ./references --set ./icon-work/scada
python scripts/validate_icons.py --set ./icon-work/scada --phase source
python scripts/render_preview.py --set ./icon-work/scada
python scripts/export_assets.py --set ./icon-work/scada --target all --dry-run
python scripts/export_assets.py --set ./icon-work/scada --target all
python scripts/validate_icons.py --set ./icon-work/scada --phase exported
```

- Run from the installed package or resolve script paths through the orchestrator; output paths remain in the user's project.
- `doctor.py` must also work without `--set` for greenfield capability checks.
- `--json` emits machine-readable results; diagnostics go to stderr.
- Exit codes: 0 success, 2 input/configuration, 3 dependency, 4 validation, 5 rendering/write failure.
- Doctor checks dependencies but does not install them. Export never calls an LLM.
- Export stages writes, validates them, and commits each managed file safely. Do not claim cross-directory transaction atomicity unless implemented; retain a recovery journal for partial failure.
- Do not delete unknown files or overwrite manually changed exports without explicit resolution.
- Draft preview can include pending icons with clear labels; final export cannot.
- `--dry-run` lists expected changes without modifying the output set.
- Identical sources/config/tool versions must produce identical asset bytes. Keep volatile timestamps in logs, not SVG/PNG payloads.

## 13. Security and preservation

Treat input SVG and metadata as untrusted data. Reject scripts, event handlers, external resource references, foreignObject, DTD/entities and embedded raster in masters. Escape labels in preview HTML; never embed unvalidated input SVG as executable page content.

Use subprocess argument arrays, not shell interpolation. Reject path traversal and case-insensitive filename collisions; do not follow symlinks outside configured roots. Preserve originals and unrelated project files.

Proposed configurable guardrails: 10 MiB per input, 4096×4096 raster dimensions, 200 icons per run. Report exceeded limits with a configuration path rather than silently skipping inputs.

Reading images through Claude Code may transmit their content to the configured model service. Do not send assets to additional third-party generation/conversion services without task authorization. Do not change global Claude settings, install dependencies during ordinary runs, or commit/push/publish automatically.

## 14. Nonfunctional requirements

| ID | Requirement |
| --- | --- |
| NFR-01 | Deterministic local rendering/export under locked inputs and tools; no deterministic LLM-generation claim |
| NFR-02 | Checkpoint recovery without unnecessary regeneration of approved work |
| NFR-03 | Traceability from each output to source, style, approval and toolchain |
| NFR-04 | Offline preview and local QA/export after setup; no CDN assets |
| NFR-05 | Actionable per-file errors and honest partial-completion reporting |
| NFR-06 | Installed package portability; no developer-specific absolute paths |
| NFR-07 | Separate generation/render/export timing; no unmeasured model latency SLA |
| NFR-08 | Paths with spaces and Unicode supported on the declared WSL2/Linux baseline |

## 15. Acceptance tests

Use ten representative fixtures: save, open-folder, settings, add, alarm-list, trend-chart, pump, valve, device-connect and network. Include PNGs, SVGs, an ambiguous image and intentionally invalid files. Synthetic fixtures must be identified as such.

| ID | Scenario | Expected evidence |
| --- | --- | --- |
| AT-01 | Empty project bootstrap and skill discovery | Package installed/discovered; doctor works without references |
| AT-02 | Missing, wrong-origin or changed dependency | Clear blocked phase; no silent substitution/update |
| AT-03 | Inventory with usage metadata | IDs, meanings, groups, sizes and locations preserved; sources unchanged |
| AT-04 | PNG redraw | Editable vector geometry, no embedded PNG; before/after review |
| AT-05 | Ambiguous meaning | NEEDS_REVIEW, not automatically approved |
| AT-06 | Existing SVG analysis | Baseline audit and selected redesign mode recorded |
| AT-07 | Style outputs | icon-style.md and style-spec.json agree |
| AT-08 | Pilot and gate | 8–12 icons or documented exception; no full generation before valid approval |
| AT-09 | Context preview | Four sizes, two themes/states, comparison and Desktop/Web context views |
| AT-10 | Batch generation | Functional grouping, shared parts and per-batch checkpoints |
| AT-11 | Invalid/clipped source | Structural failure or visual finding with affected ID; not final-export eligible |
| AT-12 | Full export fixture matrix | 10 icons × 4 sizes × 2 themes × 2 states = 160 PNGs, plus 10 inline Web SVGs |
| AT-13 | Per-icon size override | Output count follows inventory; irrelevant sizes are not exported |
| AT-14 | Theme/alpha and post-export QA | Correct RGBA dimensions, transparent backgrounds, palette and content mapping |
| AT-15 | Web consumption profiles | Inline currentColor works; img profile uses resolved color |
| AT-16 | Repeat export | Identical asset hashes; original references unchanged |
| AT-17 | Interrupt and resume | Approved batches retained; pending work continued |
| AT-18 | Invalidation | Only affected outputs/reviews rerun; stale approval rejected |
| AT-19 | Hostile input/path | Safe rejection; no external fetch or out-of-root write |
| AT-20 | Manual export edits/unknown files | Conflict report; no silent overwrite/delete |
| AT-21 | Space/Unicode paths | Inventory/render/export succeed on declared runtime |
| AT-22 | Desktop validation | Toolbar, Ribbon, menu and device-list records; themes/states and 100/125/150/200% scaling |
| AT-23 | Web validation | Actual navigation, actions and list contexts; browser/theme/state evidence |
| AT-24 | Missing application access | ASSETS_READY, actual contexts not-tested; no APPLICATION_VALIDATED claim |
| AT-25 | Maintenance addition | Duplicate-meaning check, consistent extension, regenerated outputs and version/changelog |
| AT-26 | Greenfield automated run | Synthetic fixture pipeline runs without an application repo or private assets |

The 160 PNG count applies only to AT-12's uniform fixture configuration. Production counts must be calculated from each icon's target sizes, themes and states. Additional resolved-color Web variants are counted separately.

Visual rubric: meaning, 16 px clarity, optical balance, family consistency and contrast. Score each 1–5; pilot acceptance requires all scores ≥4 and no semantic defect. This is a review rubric, not an objective automated guarantee. Label agent and human reviews separately.

## 16. Delivery milestones

1. **M1 — Foundation:** greenfield scaffold, schemas, dependency resolution/lock, doctor and inventory. Tests: AT-01/02/03/21.
2. **M2 — Reference and pilot:** baseline audit, redesign modes, style outputs, PNG redraw, context preview and approval gate. Tests: AT-04–09.
3. **M3 — Production and source QA:** functional batches, manifest, checkpoints, upstream adapters, safe validation. Tests: AT-10/11/17/18/19.
4. **M4 — Export and post-export QA:** palette resolution, raster renderer, Web profiles, dry-run and conflict handling. Tests: AT-12–16/20.
5. **M5 — Handoff and maintenance:** demo, documentation, application-validation records, extension/versioning. Tests: AT-22–26; actual-application tests may remain not-tested only with explicit reporting.

Implement sequentially for MVP. Add tracing or multi-agent orchestration only after the basic ten-icon workflow works.

## 17. Definition of Done

### 17.1 Skill implementation ready

- Installable in a clean Claude Code project with the tested environment documented.
- Upstream sources and toolchain verified and locked.
- Mandatory automated tests pass; visual pilot review is recorded.
- Ten-icon example includes SVG masters, mapping, synchronized style documents, context previews and reports.
- Fixture export produces the expected 160 PNGs and 10 inline Web SVGs.
- Resume, invalidation, conflict handling and deterministic export are demonstrated.
- README documents setup, usage, troubleshooting, uninstall and limitations.
- Application validation is implemented and reports honest statuses, including lack of target access.

### 17.2 Icon set assets ready

All requested icon IDs have valid source/visual review and post-export checks, with no unresolved semantic defects or missing required assets. Pending application tests remain visible.

### 17.3 Icon set application validated

Every required Desktop/Web actual context has passed with current exported hashes and environment evidence. Any inapplicable context must be removed from the required target profile explicitly with a reason, not silently counted as passed.

A greenfield repository can satisfy implementation readiness without access to a user's application. It cannot claim that the user's icon set has been validated in that application until evidence exists.

## 18. Implementer handoff

Read this SRS and the current repository instructions. Start with M1, resolve the upstream revisions, and write a milestone checklist in `docs/implementation-plan.md`. Do not install every repository mentioned in prior research. Do not implement deferred features as prerequisites.

Proceed with infrastructure and synthetic fixtures when private references are unavailable. Request real reference assets when beginning the user's design pilot. Ask only for missing information that materially changes semantics or design; preserve previously approved decisions.

For each milestone, report changes, executed checks, evidence and limitations. Distinguish source quality, asset export success and actual application validation. Never call a proposed script, visual review or compatibility claim verified until the corresponding work has actually been performed.

Suggested kickoff instruction:

> Implement this greenfield project according to SRS.md. Start with M1, inspect applicable repository instructions, establish the package structure and dependency compatibility record, then run the M1 acceptance checks. Continue through independently executable milestones. Present the design pilot for review before generating the full user icon set. Do not commit, push, publish or modify a target application unless explicitly requested.

## 19. References and evidence limitations

Public documentation reviewed on 2026-10-21; repository code has not been fully audited or executed as part of writing this specification. Validate source contracts at the revision selected during implementation.

- Claude Code skills: https://code.claude.com/docs/en/skills
- Core upstream skills: https://github.com/shadcn-labs/skills
- Optional future tracing reference: https://github.com/JKc66/custom-icons-skill
- Optional critique/export workflow reference: https://github.com/Paldom/icon-designer-skills/blob/main/docs/setup-prompt.md

All personal script names, schemas, states and commands in this document are proposed implementation contracts. They must not be presented as existing upstream functionality.

## 20. Revision history

| Version | Changes |
| --- | --- |
| 1.0 | Initial Vietnamese specification for a personal Claude Code icon skill |
| 1.1 | Full English rewrite for greenfield implementation; aligned to all eight workflow stages; added per-icon usage metadata, baseline audit/redesign modes, icon-style.md, 8–12 pilot, 20 px previews, functional batches, post-export checks, Desktop/Web application validation, readiness distinctions and expanded acceptance tests |
