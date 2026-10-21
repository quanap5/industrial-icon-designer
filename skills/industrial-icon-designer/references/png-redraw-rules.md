# PNG interpretation and redraw rules

## Reading a PNG

You can only describe what you see. Write what each reference depicts, then state the intended function from the metadata. Label every such statement "visual interpretation". If the picture and the metadata disagree, or the picture could mean two things, mark the icon `NEEDS_REVIEW` and ask the user; do not pick for them.

When both a PNG and an SVG exist for one icon, use the SVG for geometry and keep both references. Report differences instead of silently choosing a version.

## Redesign modes (record one in the brief)

- `normalize`: keep the shape, standardize stroke, color and alignment.
- `redraw`: keep functional meaning, redesign geometry. Default recommendation.
- `reinterpret`: change the visual metaphor. Requires explicit semantic approval (`analysis.py brief --mode reinterpret --semantic-approval`). Do not choose it because a source icon is hard to recognize: ask what it means first.

## Redraw procedure

1. Restate the function in one sentence ("Open historical trend view").
2. Choose the metaphor that conveys that function, compatible with the existing family. Prefer the established SCADA convention when one exists (valve as two opposed triangles, pump as circle with outlet).
3. Draw with the style spec: grid, stroke, caps, joins, padding. Use shared parts from `icon-style.md`.
4. Write real paths and shapes. Check with `validate_icons.py --phase source`.
5. Compare with the reference side by side at 16, 20, 24 and 32 px in the preview. Check the meaning is still recognizable and that it is not confusable with a neighbor.

## Forbidden

- Embedding the PNG (or any raster) in an SVG.
- Auto-tracing pixels in the redraw route. Tracing is an optional future adapter, not part of this workflow.
- Merging an action and a state into one icon.
- Changing an approved ID without a migration map.
