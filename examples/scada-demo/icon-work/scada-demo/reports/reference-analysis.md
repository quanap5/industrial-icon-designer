# Reference analysis: scada-demo

Redesign mode: **redraw**

## Sample (10 of 10)

| ID | Meaning | Group | Role | Reference | Interpretation |
|---|---|---|---|---|---|
| add | Add new item | file-edit | action | png | visual interpretation (PNG) |
| alarm-list | Open active alarm list | alarms-events | navigation | png | visual interpretation (PNG) |
| device-connect | Connect to selected device | devices-connectivity | action | png | visual interpretation (PNG) |
| network | Open network overview | devices-connectivity | navigation | png | visual interpretation (PNG) |
| open-folder | Open project folder | file-edit | action | svg | native SVG geometry |
| pump | Pump equipment | devices-connectivity | object | png | visual interpretation (PNG) |
| save | Save current project | file-edit | action | svg | native SVG geometry |
| settings | Open application settings | users-settings | navigation | svg | native SVG geometry |
| trend-chart | Open historical trend view | trends-reports | navigation | png | visual interpretation (PNG) |
| valve | Valve equipment | devices-connectivity | object | svg+png | native SVG geometry |

## Current inconsistencies

Baseline audit of 4 SVG reference(s): 8 blocking.
- `open-folder`: root stroke-width is 2.5; the set converges on 2.0
- `open-folder`: root stroke='#555555'. The icon cannot inherit colour
- `save`: root stroke-width is 1.0; the set converges on 2.0
- `save`: root stroke-linecap is 'round'; the set converges on 'butt'
- `settings`: root stroke-linecap is 'round'; the set converges on 'butt'
- `settings`: root stroke='#ff7f0e'. The icon cannot inherit colour
- `valve`: root stroke='#ff7f0e'. The icon cannot inherit colour

## Proposed direction

Redraw on a 24 grid with a 1.5 stroke, round caps and joins and 2 units of padding. Keep established SCADA conventions (valve as two opposed triangles, pump as a circle with an outlet). Icons are stroke-only with currentColor, so themes and states change palette tokens and never geometry.
