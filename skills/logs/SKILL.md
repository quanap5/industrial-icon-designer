---
name: logs
description: Show where an industrial-icon-designer work set is in the workflow as a vertical step timeline (current step, gates between steps, next action) and summarize what each step produced. Use when the user asks which step they are on, for progress, status, a recap or a summary of the icon redesign workflow, or wants to resume after a break. Read-only.
---

# Icon workflow logs

A read-only view of a work set created by `industrial-icon-designer`. Never modify a file, run a generator, install anything or record an approval from this skill.

## Run it

`progress.py` derives everything from the files the workflow already wrote (`run-state.json`, inventory, brief, style spec, approvals, manifest, QA and application reports). It uses only the standard library, so a plain `python3` is enough. Run it from the user's project:

| | Installed as a plugin | Used from a checkout |
|---|---|---|
| `SCRIPTS` | `${CLAUDE_PLUGIN_ROOT}/skills/industrial-icon-designer/scripts` | `skills/industrial-icon-designer/scripts` |

```bash
python3 "$SCRIPTS/progress.py" --color never                 # newest set under ./icon-work
python3 "$SCRIPTS/progress.py" --color never --set icon-work/<id>
python3 "$SCRIPTS/progress.py" --format json --set icon-work/<id>   # details and file paths per step
```

Tool output is often collapsed in the terminal, so paste the vertical timeline into your answer in a fenced code block, unchanged.

## Then summarize

1. One sentence: the step number and name, whether it is running, waiting for the user or stopped, and the next action (`next:` line).
2. One line per step from its `detail`. For more depth, use `--format json` and read only the `files` it lists for the steps the user asks about.
3. Call out what matters: a decision waiting for the user (name it), a stopped step with its errors and recovery action, a stale pilot approval (`STALE`), an approval that came from an agent and not a human, and pending changes.
4. Be exact about what has been shown: source quality, export success and application validation are different. `ASSETS_READY` never means the icons were tested in the real application.
5. No set found: say so and offer to start with `init` from the `industrial-icon-designer` skill.

## Status line

The same script gives a one-line form for Claude Code's status line (`--from-stdin --format line --color always`); the README shows the setting. It stays silent in a project with no work set.
