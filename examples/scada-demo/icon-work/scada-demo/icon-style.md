# Icon style: scada-demo

<!-- style-params:start -->
| Parameter | Value |
|---|---|
| `style_version` | 1.0.0 |
| `grid` | 24 |
| `stroke_width` | 1.5 |
| `linecap` | round |
| `linejoin` | round |
| `padding` | 2 |
| `preview_sizes_px` | 16, 20, 24, 32 |
| `default_export_sizes_px` | 16, 20, 24, 32 |
| `small_variant_sizes_px` | 16 |
| `states` | normal, disabled |
| `palette_status` | provisional_requires_review |
| `themes.dark.background` | #1E293B |
| `themes.dark.normal` | #E2E8F0 |
| `themes.dark.disabled` | #64748B |
| `themes.light.background` | #FFFFFF |
| `themes.light.normal` | #334155 |
| `themes.light.disabled` | #94A3B8 |

> Palette is provisional and not the official brand palette; it requires review.
<!-- style-params:end -->

## Rationale

The set is read mostly at 16 to 24 px in dense operator screens. A 24 grid with a 1.5 stroke keeps gaps open at 16 px while staying light beside text; round caps and joins match the existing family. The slate palette is provisional and is not the official brand palette.

## Shared geometry

Equipment glyphs (pump, valve) sit on a 2 unit padding box. A discharge pipe is a 3 unit step up then a 9 unit run; a base is a 12 unit line at y=21; a valve is two opposed triangles joined at the centre with a 7 unit stem and an 8 unit handle.

## Exceptions

`settings` has an explicit 16 px variant without the four diagonal rays, because the full gear closes up at that size. No other icon deviates.

## Examples

All ten icons in `masters/` are the pilot. `pump` and `valve` are the reference for equipment, `trend-chart` for chart axes. The pilot review is an agent review of synthetic fixtures.
