# Dependency routing

The orchestrator uses three upstream skills from `https://github.com/shadcn-labs/skills`, locked in `dependencies.lock.json` (commit SHA and per-file SHA-256). They are instructions plus scripts, not services.

| Need | Upstream skill | How it is used |
|---|---|---|
| Baseline audit of existing SVG references, whole-set consistency | `icon-set-audit` | `analysis.py audit` and `upstream_adapter.audit_svgs` run `audit_icons.py <dir> --json` |
| Generating the pilot and batches on a frozen spec | `icon-set-generator` | read its `SKILL.md` and `references/` and follow the guidance; `upstream_adapter.validate_masters` runs `validate_icons.py <dir> --spec --json` |
| Adding icons to an approved family | `icon-set-extend` | read its guidance; `upstream_adapter.infer_style` runs `infer_spec.py <dir>` to recover the spec of the existing masters |

## Rules

1. Upstream skills are not shell commands. Never run `/icon-set-generator` as a program. Use the skill by reading its resolved `SKILL.md` and references in this session, and call its scripts only through `upstream_adapter.py`.
2. Use only interfaces that exist at the locked revision (listed in the adapter docstring). Do not invent filenames or flags.
3. Before every upstream call the adapter verifies installed files against the lock. A missing skill, an origin mismatch or a changed file blocks the affected phase (`pilot`, `generate`, `extend`, `audit`) with an actionable message. Independent phases such as `export` continue.
4. Our `style-spec.json` and upstream's differ. The adapter translates ours into upstream's format and never writes upstream's file into the set.
5. Never update or install upstream material during a normal run. `setup_upstream.py` is a separate, explicit step; it verifies the clone's origin and rewrites the lock.
6. Upstream and this project ship with licenses. The upstream repository is MIT licensed; `THIRD_PARTY_NOTICES.md` keeps the notice. Do not redistribute third-party assets without checking where they came from.

## When blocked

Say which phase is blocked and why, give the exact fix (`setup_upstream.py --source <clone> --dest .claude/skills --lock dependencies.lock.json`), and continue with whatever does not depend on it.
