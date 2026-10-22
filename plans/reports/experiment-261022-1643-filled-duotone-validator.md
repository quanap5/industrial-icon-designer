# Experiment: filled and duotone icons against the existing validators

Date: 2026-10-22. Read-only except for temporary SVGs in the session scratchpad.

## Setup

Four 24x24 SVGs with root `stroke-width="1.5"`, round caps and joins:

| File | Construction |
|---|---|
| `valve-outline` | `fill="none" stroke="currentColor"`, circle r=8 plus cross (control) |
| `valve-filled` | `fill="currentColor" stroke="none"`, circle r=9 with a plus knocked out by `fill-rule="evenodd"` |
| `tank-filled-edge` | filled rect at x=2..22, exactly on the padding boundary |
| `pump-duotone` | outline circle with `fill="currentColor" fill-opacity="0.25"` plus cross |

Spec: grid 24, stroke 1.5, padding 2, as produced by `upstream_adapter.to_upstream_spec`.

## Results

| Check | Outcome |
|---|---|
| Upstream `icon-set-generator/validate_icons.py` | 0 errors, 1 warning (`tank-filled-edge` overfills the square envelope at 111%) |
| Local `validate_icons.check_svg` | 0 errors, 0 warnings for all four |
| `resvg 0.48.1` on `valve-filled` | centre pixel transparent: the `evenodd` knock-out renders as a real hole |
| `resvg 0.48.1` on `pump-duotone` | secondary fill pixel alpha 64 (0.25 x 255), stroke pixel alpha 255 |

## Conclusions

- The suspected false error "stroke paints outside the viewBox" for filled icons did not occur. The padding rule keeps geometry two units inside the canvas, which already exceeds half the stroke width.
- Neither validator rejects `fill="currentColor"` with `stroke="none"`, nor `fill-opacity` on `currentColor`. Filled and opacity-based duotone need no change to the locked upstream.
- The only upstream signal for filled icons is the optical-size warning. Filled shapes legitimately measure larger than outline shapes, so comparing them against a median that mixes modes will produce noise.
- Not yet verified: DevExpress 15.1.11 rendering of `fill-opacity`, the exported-phase checks with a filled icon, and `duplicate_check.py` with an `x` / `x-filled` pair (read in code: same meaning in the same group is a duplicate unless the roles differ).
- `style_spec.geometry_hash` hashes the dict of `GEOMETRY_KEYS`. Adding `style_mode` as an always-present key changes the hash of every existing set.
