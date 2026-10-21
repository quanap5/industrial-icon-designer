# Changelog

## Unreleased

- Project license is MIT; README now opens with the project logo, a tech stack badge row and a pixel-art intro GIF (`docs/media/intro.gif`, built by `examples/build_intro_gif.py`).

## 0.1.0 (2026-10-21)

First implementation of SRS v2.0 for the `industrial-icon-designer` skill.

- Orchestrator `SKILL.md` with six phase-loaded references.
- Scripts: `doctor`, `setup_upstream`, `inventory_icons`, `analysis`, `style_spec`, `render_preview`, `approvals`,
  `batch`, `validate_icons` (source and exported), `manifest`, `invalidate`, `export_assets`, `app_validation`,
  `duplicate_check`; seven JSON schemas.
- Locked upstream skills from `shadcn-labs/skills` and the pinned `resvg` renderer.
- Ten-icon synthetic example under `examples/scada-demo/`; acceptance tests AT-01 to AT-26 and SRS traceability checks.
- Known gaps: no real application tested (all contexts `not-tested`); the example pilot review is an agent review.
