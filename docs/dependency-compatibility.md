# Dependency and compatibility record

Recorded 2026-10-21 for `industrial-icon-designer` v0.1.0. Everything here was observed on the machine named below; nothing is inferred from other environments.

## Tested environment

| Item | Value |
|---|---|
| OS | Ubuntu 22.04.5 LTS on WSL2, kernel 6.6.87.2-microsoft-standard-WSL2 |
| Claude Code | 2.1.305 |
| Python | 3.11.13 (uv-managed), environment `env-py311/` |
| Python packages | Pillow 13.0.0, jsonschema 4.26.0, defusedxml 0.7.1, pytest 9.1.1 (full list in `requirements.lock`) |
| Renderer | resvg 0.48.1, installed with `cargo install resvg`; the only renderer used for QA |
| Upstream skills | `https://github.com/shadcn-labs/skills` at commit `5316082202ab6a7e0779b16b5c58b846c006a460`, MIT |
| Install method | `setup_upstream.py --source <verified clone> --dest .claude/skills --lock dependencies.lock.json` |

The upstream skills are `icon-set-generator`, `icon-set-extend` and `icon-set-audit`. Their `SKILL.md`, `references/` and `scripts/` files are installed unmodified; SHA-256 values are in `dependencies.lock.json` and are checked on every use. Any changed or unlisted file blocks the affected phase.

## Upstream interfaces used (inspected at the locked commit)

| Skill | Script | Interface |
|---|---|---|
| icon-set-audit | `audit_icons.py` | `<dir> [--spec FILE] [--report FILE] [--json] [--fix]` |
| icon-set-generator | `validate_icons.py` | `<dir> [--spec FILE] [--json] [--focus a,b]` |
| icon-set-extend | `infer_spec.py` | `<dir> [--write] [--out-dir DIR] [--json]` |

Upstream's `style-spec.json` has a different shape from this project's. `upstream_adapter.to_upstream_spec` translates ours into theirs and never writes theirs into a set.

## Smoke tests on this environment

| Check | Result |
|---|---|
| `doctor.py --json` in the project | exit 0; renderer matches the lock; three upstream skills match the lock |
| Skill discovery (non-interactive `claude -p`, project directory) | listed `industrial-icon-designer`, `icon-set-audit`, `icon-set-extend`, `icon-set-generator` |
| Full test suite (`pytest`) | 183 passed in 11 min 50 s (first full run, before review fixes: 151 passed in 10 min 19 s) |
| Ten-icon synthetic pipeline (`examples/build_demo.py`) | `ASSETS_READY`; 160 PNGs and 10 inline SVGs; byte-identical on a second independent build |
| Export timing (170 files) | about 15 s; preview about 15 s; source QA about 3 s; post-export QA about 13 s |

## Not tested

- DevExpress 15.1.11 and any real Desktop or Web application: every actual context is `not-tested`.
- Native Windows, macOS, or any Python other than 3.11.
- Other resvg versions. A different version invalidates raster outputs by design (`invalidate.py` detects it).

## Updating

Dependencies change only through explicit setup, never during ordinary runs. After changing any of them, rerun `setup_upstream.py` (upstream), regenerate `requirements.lock`, update this record, then run `invalidate.py detect --apply` on existing sets.
