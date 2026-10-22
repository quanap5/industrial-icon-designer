# Desktop export profile

The primary Desktop application is likely built on DevExpress 15.1.11. That version's handling of SVG, automatic recoloring and display scaling is not assumed; export a conservative PNG profile and test it in the real application.

## Output

`exports/desktop/<theme>/<state>/<size>/<icon-id>.png`

- RGBA PNG, fully transparent background. Preview backgrounds are never baked in.
- One file per icon, theme, state and size listed for that icon (`sizes_px`). Per-icon sizes override the set default; sizes an icon does not need are not exported.
- Each size is rendered directly from the master at that size with the pinned renderer. Never upscale a smaller PNG.
- Theme and state choose a palette token (`normal` or `disabled`) substituted for `currentColor`. Geometry is unchanged.
- Small variants replace the master at the sizes they are mapped to.
- A filled variant (`<id>-filled`) exports like any icon. A duotone secondary layer is rendered with its `fill-opacity` as PNG alpha, and post-export QA requires pixels at that alpha. Whether the DevExpress control composes those translucent pixels as expected is `not-tested` until `app_validation.py` records evidence from the real application.

## What is not exported

Desktop SVG, ICO and ICNS are deferred profiles. Do not enable them unless the user requests it. Additional DPI-derived bitmap sizes come from an explicit target profile; a display scaling percentage alone does not add sizes.

## Application validation

Inspect real screens: toolbar, Ribbon, menu, device list; both themes; supported states; display scaling 100%, 125%, 150% and 200%. Record the control behavior at each scale. Until that evidence exists, the status is `not-tested`, and a simulation is never a substitute.
