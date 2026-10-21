# Application validation checklist: scada-demo

Test the exported assets in the real application. A simulation or preview does not count.
Record each result with `app_validation.py record` (status, reason, environment, evidence).

## desktop-toolbar (desktop)

Icons used here: add, device-connect, open-folder, save, settings

- [ ] Theme `dark`, states normal, disabled
- [ ] Theme `light`, states normal, disabled
- [ ] Display scaling 100%, 125%, 150%, 200%: note whether the control picks the right bitmap size, or scales or blurs it
- [ ] Record framework and control (for example DevExpress 15.1.11, which control)
- [ ] Icons are the intended ones, not clipped, correct color in each state

## desktop-ribbon (desktop)

Icons used here: alarm-list, save, trend-chart

- [ ] Theme `dark`, states normal, disabled
- [ ] Theme `light`, states normal, disabled
- [ ] Display scaling 100%, 125%, 150%, 200%: note whether the control picks the right bitmap size, or scales or blurs it
- [ ] Record framework and control (for example DevExpress 15.1.11, which control)
- [ ] Icons are the intended ones, not clipped, correct color in each state

## desktop-menu (desktop)

Icons used here: network, open-folder, save

- [ ] Theme `dark`, states normal, disabled
- [ ] Theme `light`, states normal, disabled
- [ ] Display scaling 100%, 125%, 150%, 200%: note whether the control picks the right bitmap size, or scales or blurs it
- [ ] Record framework and control (for example DevExpress 15.1.11, which control)
- [ ] Icons are the intended ones, not clipped, correct color in each state

## desktop-device-list (desktop)

Icons used here: add, device-connect, pump, valve

- [ ] Theme `dark`, states normal, disabled
- [ ] Theme `light`, states normal, disabled
- [ ] Display scaling 100%, 125%, 150%, 200%: note whether the control picks the right bitmap size, or scales or blurs it
- [ ] Record framework and control (for example DevExpress 15.1.11, which control)
- [ ] Icons are the intended ones, not clipped, correct color in each state

## web-navigation (web)

Icons used here: alarm-list, network, settings, trend-chart

- [ ] Theme `dark`, states normal, disabled
- [ ] Theme `light`, states normal, disabled
- [ ] Record browser and version and rendering conditions (zoom, device pixel ratio)
- [ ] Icons are the intended ones, not clipped, correct color in each state

## web-actions (web)

Icons used here: add

- [ ] Theme `dark`, states normal, disabled
- [ ] Theme `light`, states normal, disabled
- [ ] Record browser and version and rendering conditions (zoom, device pixel ratio)
- [ ] Icons are the intended ones, not clipped, correct color in each state

## web-list (web)

Icons used here: none recorded

- [ ] Theme `dark`, states normal, disabled
- [ ] Theme `light`, states normal, disabled
- [ ] Record browser and version and rendering conditions (zoom, device pixel ratio)
- [ ] Icons are the intended ones, not clipped, correct color in each state

