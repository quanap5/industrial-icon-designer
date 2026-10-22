# Changelog

## 0.4.0 (2026-10-22)

- Style modes: `style-spec.json` gains `style_mode` (`outline` default, `filled`, `duotone`), `duotone_secondary_opacity` and `consistency_overrides`. Duotone is one colour at two opacities (`fill-opacity` on `currentColor`); no new palette token. A set that declares no mode keeps its geometry hash, approvals and validation result.
- New `consistency.py`: rules for minimum rendered stroke, mode per master, duotone opacity range, consistency and secondary contrast, and filled-variant box parity. Every finding carries a suggested value; a declared mode gives errors, an undeclared one warnings. `style_spec.py check`, `style_spec.py finalize` and `validate_icons.py --phase source` use them.
- New `variants.py add`: the filled variant `<id>-filled` of an outline icon is its own inventory entry with `variant_of`; `duplicate_check.py --variant-of` accepts it; a re-inventory keeps it; the preview has a Form filter and links the variant to its base.
- Post-export QA requires pixels at the configured secondary alpha for a duotone set.
- New decision point `style_mode`. SRS 2.4 adds FR-SPC-04, FR-SPC-05, FR-GEN-05 and FR-QA-06 and updates FR-EXP-02 and DR-06; 2.3 is kept as `docs/SRS-v2.3.md`.

## 0.3.1 (2026-10-22)

- The plugin is renamed from `industrial-icon-designer` to `qk`: the skills are `/qk:industrial-icon-designer` and `/qk:logs`, and the install id is `qk@quanap5-plugins`. The marketplace lists the old name under `renames`, so existing installs migrate. The skill names themselves are unchanged.

## 0.3.0 (2026-10-22)

- New skill `logs` (`/<plugin>:logs`) and script `progress.py`: a read-only view of where a work set is in the workflow. It prints a vertical step timeline with colored markers (green done, cyan in progress, yellow waiting for you, red stopped, gray not yet), the gates between steps, a `YOU ARE HERE` marker and the next action; it also has a one-line form for Claude Code's status line and a JSON form. Everything is derived from the files the workflow already writes, nothing is written, and only the standard library is needed.
- SRS 2.3 adds FR-WFL-08.

## 0.2.1 (2026-10-22)

- The skill now asks the user's decisions with `AskUserQuestion`: a short "Asking the user" section in `SKILL.md`, a catalog of 17 decision points in `references/questions.md` (setup, intake, meaning, redesign mode, grid and stroke, pilot and batch approval, export scope, drift, conflicts, palette, application tests, duplicates), and `tests/test_skill_questions.py` that checks the catalog against the tool's limits.
- A user approval is recorded only from a real answer; no question offers the agent approving for the user. Without a way to ask, the skill uses documented defaults, records the assumption and stops at the human gate.
- SRS 2.2 adds FR-WFL-07.

## Unreleased

- Preview page reworked for comparison: each icon card shows labeled Before (reference) and After (redrawn) columns at actual size with an enlarged supplement. Group, theme, state, size and Before/After visibility are CSS-only controls, so pages stay offline and script-free.
- `render_preview.py --group a,b` renders only the named functional groups and does not advance the run state; unknown names list the valid groups. The JSON result adds `groups`.
- Context simulations are now three pages (`desktop`, `web`, `web-img`), each showing Before and After side by side in Light and Dark; Desktop adds a CSS-only display scaling control that is not a DPI test.

## 0.2.0 (2026-10-21)

- The repository is now a Claude Code plugin and marketplace (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`): install with `/plugin marketplace add quanap5/industrial-icon-designer`. The locked upstream skills are committed so the plugin is self-contained.
- `SKILL.md` explains plugin and checkout paths (`${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`) and the one-time environment setup.
- Project license is MIT; README opens with the project logo, a tech stack badge row and a pixel-art intro GIF (`docs/media/intro.gif`, built by `examples/build_intro_gif.py`).

## 0.1.0 (2026-10-21)

First implementation of SRS v2.0 for the `industrial-icon-designer` skill.

- Orchestrator `SKILL.md` with six phase-loaded references.
- Scripts: `doctor`, `setup_upstream`, `inventory_icons`, `analysis`, `style_spec`, `render_preview`, `approvals`,
  `batch`, `validate_icons` (source and exported), `manifest`, `invalidate`, `export_assets`, `app_validation`,
  `duplicate_check`; seven JSON schemas.
- Locked upstream skills from `shadcn-labs/skills` and the pinned `resvg` renderer.
- Ten-icon synthetic example under `examples/scada-demo/`; acceptance tests AT-01 to AT-26 and SRS traceability checks.
- Known gaps: no real application tested (all contexts `not-tested`); the example pilot review is an agent review.
