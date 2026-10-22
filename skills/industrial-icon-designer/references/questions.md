# Asking the user

Load this file the first time you are about to ask the user something. The choices below are for the `AskUserQuestion` tool. If the tool is listed as deferred, load its schema first.

## Rules

1. **Ask only when all three hold:** the decision is the user's, the project cannot answer it (inventory, `brief.json`, `style-spec.json`, earlier answers, scripts), and the answer changes the outcome, a safety boundary or a public contract. Otherwise take the documented default and say so.
2. **Skip what is already answered** by the request or the files. Never re-ask a settled decision; check `brief.json` `notes` for earlier answers and assumptions.
3. **One call per decision point**, with 1-4 related questions in it. Never ask status questions ("Shall I continue?").
4. **Options:** 2-4 per question, labels of 1-5 words, a description that states the consequence. Put the recommended option first and append `(Recommended)` only when evidence supports it. Never add an "Other" option: the tool adds it. Use `multiSelect` only when several answers can be true at once.
5. **Ask in the user's language.** Keep icon ids, flags, file names and state names literal.
6. **Approval questions are the one place where the answer is evidence.** Only a real answer from the user may be recorded with `--reviewer user`. Silence, a skipped question or a headless run is never approval. Never offer "let the agent approve" as an option; unattended agent review exists only when the user asks for it themselves.
7. **When you cannot ask** (headless `claude -p`, a subagent, no tool): use the documented default for reversible choices, write each assumption into `brief.json` `notes`, and stop at the gate that needs a human (for example `PILOT_READY`) with a short report.
8. **Free text ("Other"):** follow it. If it is unclear, ask once more, then stop and report instead of guessing.
9. After the answer, state in one line what you will do, then do it.

## Decision points

Each entry is one call. `when` says where it belongs; do not ask it earlier or in other cases. Fill the `<placeholders>` from real project data. The JSON is machine-checked against the tool's limits.

```json
{
  "setup": {
    "when": "Plugin install only, when doctor reports missing Python packages or resvg; before running any install command.",
    "questions": [
      {
        "question": "Install the Python environment and the resvg renderer now?",
        "header": "Setup",
        "multiSelect": false,
        "options": [
          {"label": "Install now (Recommended)", "description": "Runs the one-time setup commands from SKILL.md; nothing else is installed."},
          {"label": "Show commands only", "description": "Prints the commands so you can run them yourself."},
          {"label": "Not now", "description": "Stops here; phases that need the renderer stay blocked."}
        ]
      }
    ]
  },
  "intake": {
    "when": "Stage 1, only for facts the request and the project files do not already state.",
    "questions": [
      {
        "question": "Where will the redesigned icons be used?",
        "header": "Targets",
        "multiSelect": true,
        "options": [
          {"label": "Desktop app", "description": "Exports transparent PNGs per size, theme and state."},
          {"label": "Web app", "description": "Exports inline SVGs that follow the CSS currentColor."}
        ]
      },
      {
        "question": "Which colors should the icons use?",
        "header": "Palette",
        "multiSelect": false,
        "options": [
          {"label": "Provisional slate (Recommended)", "description": "Labeled provisional until you review it; geometry never depends on it."},
          {"label": "My brand colors", "description": "You give the hex values for the light and dark themes."}
        ]
      }
    ]
  },
  "meaning": {
    "when": "Stage 1, for each icon marked NEEDS_REVIEW. At most 4 per call; ask in rounds when there are more.",
    "questions": [
      {
        "question": "What does `<icon-id>` mean in your application?",
        "header": "Meaning",
        "multiSelect": false,
        "options": [
          {"label": "<best guess>", "description": "Read from the file name, the metadata and the image; say which one."},
          {"label": "Skip this icon", "description": "Leaves it out of this run; it stays NEEDS_REVIEW."}
        ]
      }
    ]
  },
  "mode": {
    "when": "Stage 2, only when the request does not already say how to redesign.",
    "questions": [
      {
        "question": "How should the old icons be redesigned?",
        "header": "Redesign",
        "multiSelect": false,
        "options": [
          {"label": "Redraw (Recommended)", "description": "Keeps each meaning and redesigns the geometry."},
          {"label": "Normalize", "description": "Keeps each shape; unifies stroke, color and alignment."},
          {"label": "Reinterpret", "description": "Changes the visual metaphor; needs your explicit approval next."}
        ]
      }
    ]
  },
  "reinterpret": {
    "when": "Stage 2, only after the user chose Reinterpret; name the affected icon ids in the question.",
    "questions": [
      {
        "question": "Approve changing the visual metaphor of <icon-ids>?",
        "header": "Approval",
        "multiSelect": false,
        "options": [
          {"label": "Approve the change", "description": "Records semantic approval so the brief may use reinterpret."},
          {"label": "Keep the metaphor", "description": "Uses redraw instead and preserves each meaning."}
        ]
      }
    ]
  },
  "grid": {
    "when": "Stage 3, only when the smallest usage size is 20 px or less, or the user asked for heavier or lighter strokes. Otherwise use grid 24 and stroke 1.5 without asking.",
    "questions": [
      {
        "question": "Which grid and stroke should the set use?",
        "header": "Grid",
        "multiSelect": false,
        "options": [
          {"label": "24 grid, 1.5 (Recommended)", "description": "Balanced default; compared with stroke 2 in the pilot."},
          {"label": "24 grid, 2", "description": "Heavier strokes for busy backgrounds."},
          {"label": "16 grid, 1.25", "description": "For sets that render at 20 px or smaller."}
        ]
      }
    ]
  },
  "stroke": {
    "when": "Stage 4, after the pilot preview shows stroke 1.5 and 2 side by side.",
    "questions": [
      {
        "question": "Which stroke weight reads better in the preview?",
        "header": "Stroke",
        "multiSelect": false,
        "options": [
          {"label": "1.5 (Recommended)", "description": "Lighter and closer to the existing family."},
          {"label": "2", "description": "Heavier; stays clearer at 16 px."},
          {"label": "Compare again", "description": "Re-render the pilot with both weights."}
        ]
      }
    ]
  },
  "pilot": {
    "when": "Stage 4, after previews and your rubric review. Put Approve pilot first with (Recommended) only when every score is 4 or more and there is no semantic defect; otherwise put Revise some icons first.",
    "questions": [
      {
        "question": "Approve the pilot icons?",
        "header": "Pilot",
        "multiSelect": false,
        "options": [
          {"label": "Approve pilot (Recommended)", "description": "Opens batch generation; bound to the geometry style and these exact files."},
          {"label": "Revise some icons", "description": "You name the icons to redraw; the rest stay."},
          {"label": "Change the style", "description": "Adjust grid, stroke or palette, then preview again."},
          {"label": "Redraw the pilot", "description": "Starts the pilot over with a new direction."}
        ]
      }
    ]
  },
  "revise_which": {
    "when": "Stage 4, after the user chose Revise some icons. At most 4 options; with more candidates, ask for the ids in plain text instead.",
    "questions": [
      {
        "question": "Which icons should be redrawn?",
        "header": "Icons",
        "multiSelect": true,
        "options": [
          {"label": "<icon-id>", "description": "<what scored low or should change>"},
          {"label": "<other-icon-id>", "description": "<what scored low or should change>"}
        ]
      }
    ]
  },
  "batch": {
    "when": "Stage 5, once after all batches of this run pass source QA, not after every batch. Ask earlier only when a batch fails review.",
    "questions": [
      {
        "question": "Approve the generated icons?",
        "header": "Batch",
        "multiSelect": false,
        "options": [
          {"label": "Approve all (Recommended)", "description": "Records your approval for every icon generated in this run."},
          {"label": "Review by group", "description": "You pick which functional groups to look at first."},
          {"label": "Request changes", "description": "You say what to change; nothing is approved yet."}
        ]
      }
    ]
  },
  "export_scope": {
    "when": "Stage 6, only when the outputs are not already clear from the targets. Put the defaults for the chosen targets first.",
    "questions": [
      {
        "question": "Which outputs should be exported?",
        "header": "Outputs",
        "multiSelect": true,
        "options": [
          {"label": "Desktop PNG", "description": "Transparent RGBA per size, theme and state."},
          {"label": "Web inline SVG", "description": "Keeps currentColor for inline use."},
          {"label": "Web img SVG", "description": "Resolved colors for img tags; counted separately."}
        ]
      }
    ]
  },
  "drift": {
    "when": "Stage 6, when export reports drift (style, palette, renderer, size or geometry changes waiting).",
    "questions": [
      {
        "question": "Pending changes were found. Process them before exporting?",
        "header": "Changes",
        "multiSelect": false,
        "options": [
          {"label": "Apply them (Recommended)", "description": "Runs invalidate.py detect --apply; affected outputs are reset."},
          {"label": "Show details first", "description": "Lists what changed before anything is reset."}
        ]
      }
    ]
  },
  "conflict": {
    "when": "Stage 6, when export reports files that were edited by hand or are unknown at a planned path.",
    "questions": [
      {
        "question": "Some exports were edited by hand. How should the export proceed?",
        "header": "Conflicts",
        "multiSelect": false,
        "options": [
          {"label": "Keep my edits (Recommended)", "description": "Stops; nothing is overwritten or deleted."},
          {"label": "Overwrite, keep backups", "description": "Uses --resolve overwrite; originals go to exports/.conflicts/."},
          {"label": "Show the list", "description": "Prints every conflicting file first."}
        ]
      }
    ]
  },
  "palette": {
    "when": "Stage 6, when the palette changed after approval and export asks for a palette review.",
    "questions": [
      {
        "question": "The palette changed. Approve the new colors?",
        "header": "Palette",
        "multiSelect": false,
        "options": [
          {"label": "Approve palette", "description": "Records your palette approval so themed outputs can be exported."},
          {"label": "Revise colors", "description": "You give new values; nothing is exported meanwhile."}
        ]
      }
    ]
  },
  "app_access": {
    "when": "Stage 7, once, before any application record is written.",
    "questions": [
      {
        "question": "Can you test the exported icons in the real application now?",
        "header": "App test",
        "multiSelect": false,
        "options": [
          {"label": "Yes, testing now", "description": "You report results per context, with evidence."},
          {"label": "Not now", "description": "Every context stays not-tested; the result stays ASSETS_READY."},
          {"label": "Change the profile", "description": "Removes a context that does not apply, with a stated reason."}
        ]
      }
    ]
  },
  "contexts": {
    "when": "Stage 7, after the user chose Yes, testing now. Ask only about platforms in the targets.",
    "questions": [
      {
        "question": "Which Desktop contexts did you test?",
        "header": "Desktop",
        "multiSelect": true,
        "options": [
          {"label": "Toolbar", "description": "Toolbar buttons at their real sizes."},
          {"label": "Ribbon", "description": "Large and small ribbon items."},
          {"label": "Menu", "description": "Menu item icons."},
          {"label": "Device list", "description": "List rows with equipment icons."}
        ]
      },
      {
        "question": "Which Web contexts did you test?",
        "header": "Web",
        "multiSelect": true,
        "options": [
          {"label": "Navigation", "description": "Sidebar or top navigation icons."},
          {"label": "Actions", "description": "Toolbar and action buttons."},
          {"label": "List", "description": "Icons inside list rows."}
        ]
      }
    ]
  },
  "duplicate": {
    "when": "Stage 8, when duplicate_check.py reports a duplicate or a near duplicate.",
    "questions": [
      {
        "question": "`<new-id>` looks like `<existing-id>`. How should it be handled?",
        "header": "Duplicate",
        "multiSelect": false,
        "options": [
          {"label": "Reuse existing icon (Recommended)", "description": "Adds an alias in the application; no new drawing."},
          {"label": "Add as distinct icon", "description": "You explain the difference; it gets its own meaning."},
          {"label": "Cancel the addition", "description": "Leaves the set unchanged."}
        ]
      }
    ]
  }
}
```

## After the answer

| Decision | What to do with it |
|---|---|
| `setup` | Install now: run the setup commands once. Show commands only: print them and stop. Not now: report which phases stay blocked (`doctor.py`). |
| `intake` | Record targets and palette choice in `brief.json` `notes`. For a platform that is not a target, remove its contexts with `app_validation.py profile --remove <context> --reason "<platform> is not a target"`. Provisional slate keeps `palette_status` provisional; brand colors go into `style-spec.json` themes and stay provisional until the palette is approved. |
| `meaning` | Put the confirmed meaning into the metadata file and rerun `inventory_icons.py`. Skip keeps the icon `NEEDS_REVIEW` and out of approvals. |
| `mode` | `analysis.py brief --mode <mode>`. Reinterpret is only recorded after `reinterpret` is answered. |
| `reinterpret` | Approve the change: `analysis.py brief --mode reinterpret --semantic-approval`. Keep the metaphor: use `redraw`. |
| `grid` | Edit `grid`, `stroke_width`, `padding` in `style-spec.json`, then `style_spec.py generate`. |
| `stroke` | Set `stroke_width`, regenerate, rerender; a geometry change makes the pilot approval stale by design. |
| `pilot` | Approve: `approvals.py record --type pilot --reviewer user --scores-file <your rubric>`. This is the only place a pilot approval is recorded. Other answers loop back to drawing and `render_preview.py`. |
| `revise_which` | Redraw only the named icons, rerun `validate_icons.py --phase source` and `render_preview.py`, then ask `pilot` again. |
| `batch` | Approve all: `approvals.py record --type batch --reviewer user --ids <generated ids>`. Review by group: show `render_preview.py --group <groups>` first. |
| `export_scope` | `export_assets.py --target desktop`, `--target web`, or both; add `--web-img` for Web img SVG. Run `--dry-run` first. |
| `drift` | Apply: `invalidate.py detect --apply`, then export again. Show details: `invalidate.py detect --json`. |
| `conflict` | Keep: stop and report the files. Overwrite: `export_assets.py --resolve overwrite`. Show the list: print them, then ask again. |
| `palette` | Approve: `approvals.py record --type palette --reviewer user --ids all`. Revise: edit the themes, then `invalidate.py detect --apply`. |
| `app_access` | Yes: ask `contexts`. Not now: `app_validation.py evaluate` and report `ASSETS_READY`. Change the profile: `app_validation.py profile --remove <context> --reason "<their reason>"`. |
| `contexts` | Record only what the user reports, with their environment and evidence, using `app_validation.py record`. Contexts not selected stay `not-tested`. |
| `duplicate` | Reuse: stop and explain the alias. Distinct: continue with the user's stated difference as the meaning. Cancel: stop. |
