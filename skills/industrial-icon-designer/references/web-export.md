# Web export profile

Two explicit consumption profiles. Do not promise that a color set by host CSS reaches an SVG loaded through `<img>`.

## Inline (monochrome)

`exports/web/<icon-id>.svg` keeps `currentColor` (as `stroke`, as `fill`, or both, following the master). Duotone keeps its `fill-opacity`. The SVG is inserted inline in the page, so the surrounding CSS `color` themes it. The consuming UI is responsible for accessibility: decorative icons get `aria-hidden="true"`; informative icons need an accessible name on the control or an inline `<title>`.

## Image (`<img src=...>`)

CSS color does not cross the `<img>` boundary. Export resolved-color variants instead: `exports/web/img/<theme>/<state>/<icon-id>.svg`, with `currentColor` replaced by the theme token. Resolved-color variants are counted separately from the inline set.

## Rules

- Same geometry as the master. Themes change color only.
- No scripts, external references or raster in exports; they are validated again after export.
- Deterministic bytes: no timestamps or generator comments in the payload.
- Validate in real navigation, toolbar/action and list contexts. Record browser version and rendering conditions. Without that evidence the status is `not-tested`.
