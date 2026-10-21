# Review checklist

Use for the pilot review, each batch, and any later change. Record who reviewed: `user` or `agent`.

## Per icon (score 1-5)

| Criterion | Question |
|---|---|
| Meaning | Does it still say the same function as the reference? Can it be confused with a neighbor? |
| 16 px clarity | At actual 16 px, are gaps open and shapes distinct? Is a small variant needed? |
| Optical balance | Does it carry the same visual weight as the rest of the set, not just the same bounding box? |
| Family consistency | Same stroke, caps, joins, corner treatment and shared parts? |
| Contrast | Does the normal token reach 3:1 on its background? Is disabled reported separately? |

Pilot acceptance: every score at least 4 and no semantic defect.

## Look at

- Actual-size renders first, enlarged views only as a supplement.
- Light and Dark, normal and disabled.
- Simulated toolbar, menu, Ribbon-like and device-list contexts, and Web navigation and actions. They are simulations, not the real application.
- Accidental alarm colors: nothing red, yellow or green without an approved rule.
- Action versus state pairs: they must stay visually distinct.

## Before approval

- `style_spec.py check` passes (JSON and Markdown agree).
- `validate_icons.py --phase source` passes for every icon in scope.
- Unresolved meanings are resolved or the icons are excluded.
- The approval will be recorded against the style hash and the exact asset hashes. Any later change to style or pilot assets makes it stale; ask again only for unresolved semantics or material style changes.

## Honest reporting

Say which of these has been shown: source quality, export success, application validation. A passing script is not a visual review, and a simulation is not an application test.
