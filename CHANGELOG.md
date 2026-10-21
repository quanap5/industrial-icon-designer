# Changelog

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
