"""Consistency rules for style modes (outline, filled, duotone).

Every rule returns findings of the shape {rule, severity, message, suggested}. `suggested` is the value
or action that would make the finding go away. Spec-level rules judge `style-spec.json`; icon-level rules
judge one parsed master against the mode it is meant to have.

Strictness is opt-in so a set written before modes existed keeps its validation result: a spec without an
explicit `style_mode` reports mode mismatches as warnings, a spec that declares one reports errors. A
filled variant of an outline icon is always judged strictly because it declares itself.

Thresholds are starting values, not standards. A spec may override a rule's value under
`consistency_overrides.<rule> = {"reason": ..., "value": ...}`; overrides are listed in the report. The input-size limits in
`guardrails.json` are a different mechanism (common.guardrails). The gap rule is not
duplicated here: the locked upstream validator already checks minimum gaps.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import palette
import style_spec
from common import EXIT_INPUT, ToolError

DRAWABLE = {"path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}
STROKE_MIN_PX = 1.0
OPACITY_RANGE = (0.2, 0.5)
SECONDARY_CONTRAST_MIN = 1.5
OPACITY_TOLERANCE = 0.01
VARIANT_BOUNDS_TOLERANCE = 1.0  # grid units
LIMIT_RULES = ("stroke-min-at-smallest", "duotone-opacity-range", "duotone-secondary-contrast",
               "variant-bounds-parity")
RULES = ("stroke-min-at-smallest", "duotone-opacity-range", "duotone-secondary-contrast", "mode-matches-spec",
         "duotone-opacity-consistent", "variant-bounds-parity")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def finding(rule: str, severity: str, message: str, suggested) -> dict:
    return {"rule": rule, "severity": severity, "message": message, "suggested": suggested}


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _valid_limit(rule: str, value) -> bool:
    if rule == "duotone-opacity-range":
        return (isinstance(value, list) and len(value) == 2 and all(_number(v) and v < 1 for v in value)
                and value[0] < value[1])
    return _number(value)


def check_overrides(spec: dict) -> None:
    """Refuse an override that names no rule or carries a value of the wrong shape, instead of letting a
    typo silently do nothing or a bad value crash a later check."""
    for rule, override in spec.get("consistency_overrides", {}).items():
        if rule not in LIMIT_RULES:
            raise ToolError(EXIT_INPUT, f"consistency_overrides names unknown rule '{rule}'; rules with a limit: "
                            + ", ".join(sorted(LIMIT_RULES)), "style-spec.json")
        if "value" in override and not _valid_limit(rule, override["value"]):
            expected = "[low, high] with 0 < low < high < 1" if rule == "duotone-opacity-range" else "a number above 0"
            raise ToolError(EXIT_INPUT, f"consistency_overrides.{rule}.value must be {expected}", "style-spec.json")


def limit(spec: dict, rule: str, default):
    override = spec.get("consistency_overrides", {}).get(rule)
    return override["value"] if override and "value" in override else default


def overrides(spec: dict) -> list[dict]:
    return [{"rule": r, "reason": o["reason"]} for r, o in sorted(spec.get("consistency_overrides", {}).items())]


def is_strict(spec: dict) -> bool:
    return "style_mode" in spec


def split(findings: list[dict]) -> tuple[list[str], list[str]]:
    """Errors and warnings as `[rule] message (suggested: ...)` strings for the validator reports."""
    def text(f: dict) -> str:
        return f"[{f['rule']}] {f['message']} (suggested: {f['suggested']})"
    return ([text(f) for f in findings if f["severity"] == "error"],
            [text(f) for f in findings if f["severity"] == "warning"])


# ------------------------------------------------------------------------------ spec level

def _blend(fg: str, bg: str, alpha: float) -> str:
    f, b = fg.lstrip("#"), bg.lstrip("#")
    mixed = (round(int(f[i:i + 2], 16) * alpha + int(b[i:i + 2], 16) * (1 - alpha)) for i in (0, 2, 4))
    return "#" + "".join(f"{c:02X}" for c in mixed)


def _opacity_reaching(token: str, background: str, floor: float, low: float, high: float) -> float | None:
    """Smallest opacity in the allowed range whose blend reaches the contrast floor."""
    for step in range(math.ceil(low * 20), math.floor(high * 20) + 1):
        level = step * 0.05
        if palette.contrast_ratio(_blend(token, background, level), background) >= floor:
            return round(level, 2)
    return None


def spec_findings(spec: dict) -> list[dict]:
    check_overrides(spec)
    out: list[dict] = []
    mode = style_spec.style_mode(spec)
    if mode in ("outline", "duotone"):
        smallest = min(spec["preview_sizes_px"] + spec["default_export_sizes_px"])
        floor = limit(spec, "stroke-min-at-smallest", STROKE_MIN_PX)
        rendered = spec["stroke_width"] * smallest / spec["grid"]
        if rendered < floor:
            wanted = math.ceil(floor * spec["grid"] / smallest * 4) / 4
            out.append(finding(
                "stroke-min-at-smallest", "error" if is_strict(spec) else "warning",
                f"stroke {spec['stroke_width']} renders {rendered:.2f}px at {smallest}px, below {floor}px",
                f"stroke_width {wanted:g}"))
    if mode == "duotone":
        low, high = limit(spec, "duotone-opacity-range", list(OPACITY_RANGE))
        level = style_spec.duotone_opacity(spec)
        if not low <= level <= high:
            out.append(finding("duotone-opacity-range", "error",
                               f"duotone_secondary_opacity {level} is outside {low} to {high}",
                               f"duotone_secondary_opacity {min(max(level, low), high):g}"))
        floor = limit(spec, "duotone-secondary-contrast", SECONDARY_CONTRAST_MIN)
        for name, tokens in sorted(spec["themes"].items()):
            blended = _blend(tokens["normal"], tokens["background"], level)
            ratio = palette.contrast_ratio(blended, tokens["background"])
            if ratio < floor:
                wanted = _opacity_reaching(tokens["normal"], tokens["background"], floor, low, high)
                out.append(finding(
                    "duotone-secondary-contrast", "error" if is_strict(spec) else "warning",
                    f"secondary layer {blended} on {tokens['background'].upper()} in theme '{name}' has contrast "
                    f"{ratio}:1, below {floor}:1",
                    f"duotone_secondary_opacity {wanted:g}" if wanted else "a darker or lighter normal token"))
    return out


# ------------------------------------------------------------------------------ icon level

def _parents(root) -> dict:
    return {child: parent for parent in root.iter() for child in parent}


def _inherited(el, name: str, parents: dict) -> str | None:
    while el is not None:
        value = el.attrib.get(name)
        if value is not None:
            return value.strip().lower()
        el = parents.get(el)
    return None


def _parse_opacity(raw: str | None) -> float | None:
    """A fill-opacity as a number between 0 and 1; a percentage is accepted. None when unreadable."""
    if raw in (None, ""):
        return 1.0
    text = raw.strip()
    try:
        value = float(text[:-1]) / 100 if text.endswith("%") else float(text)
    except ValueError:
        return None
    return value if 0.0 <= value <= 1.0 else None


def _layers(root) -> dict:
    parents = _parents(root)
    layers = {"stroke": False, "fill": False, "secondary": [], "primary_fill": False, "unreadable_opacity": [],
              "unfilled": 0, "hidden_opacity": 0}
    for el in root.iter():
        if "opacity" in el.attrib or re.search(r"opacity\s*:", el.attrib.get("style", ""), re.I):
            layers["hidden_opacity"] += 1  # element opacity or style opacity: the checks cannot read it
        if _local(el.tag) not in DRAWABLE:
            continue
        if _inherited(el, "fill", parents) is None:
            layers["unfilled"] += 1
        if _inherited(el, "stroke", parents) == "currentcolor":
            layers["stroke"] = True
        if _inherited(el, "fill", parents) == "currentcolor":
            layers["fill"] = True
            raw = _inherited(el, "fill-opacity", parents)
            opacity = _parse_opacity(raw)
            if opacity is None:
                layers["unreadable_opacity"].append(raw)
            elif opacity < 1.0:
                layers["secondary"].append(opacity)
            else:
                layers["primary_fill"] = True
    return layers


def icon_findings(root, spec: dict, mode: str | None = None) -> list[dict]:
    """Judge one parsed master against `mode` (default: the mode of the set)."""
    explicit = mode is not None
    mode = mode or style_spec.style_mode(spec)
    severity = "error" if explicit or is_strict(spec) else "warning"
    layers = _layers(root)
    out: list[dict] = []

    def add(rule: str, message: str, suggested, level: str = severity) -> None:
        out.append(finding(rule, level, message, suggested))

    if layers["unreadable_opacity"]:
        add("mode-matches-spec", f"fill-opacity {layers['unreadable_opacity']} is not a number between 0 and 1",
            'fill-opacity="0.3" (a number from 0 to 1, or a percentage)', "error")
    if layers["hidden_opacity"]:
        add("mode-matches-spec", "opacity set by an `opacity` attribute or a style declaration is not read by "
            "these checks", 'use the fill-opacity attribute on the secondary shape')
    if layers["unfilled"]:
        add("mode-matches-spec", f"{layers['unfilled']} shape(s) have no fill and would paint black",
            'set fill="currentColor" or fill="none" on the shape or on the root svg')

    if mode == "outline":
        if not layers["stroke"]:
            add("mode-matches-spec", "outline icon has no currentColor stroke",
                'draw with stroke="currentColor", or declare the icon a filled variant (variant_of)')
        if layers["secondary"]:
            add("mode-matches-spec", "outline icon has a partly transparent fill",
                'remove fill-opacity, or use style_mode "duotone"')
    elif mode == "filled":
        if not layers["fill"]:
            add("mode-matches-spec", "filled icon has no currentColor fill", 'set fill="currentColor"')
        if layers["stroke"]:
            add("mode-matches-spec", "filled icon carries a currentColor stroke, so its weight would depend "
                "on the stroke width", 'set stroke="none" and draw the outline as a filled shape')
        if layers["secondary"]:
            add("mode-matches-spec", "filled icon has a partly transparent fill", 'remove fill-opacity')
    elif mode == "duotone":
        level = style_spec.duotone_opacity(spec)
        if not layers["secondary"]:
            add("mode-matches-spec", "duotone icon has no secondary layer",
                f'add fill="currentColor" fill-opacity="{level:g}" to the secondary shape')
        if not (layers["stroke"] or layers["primary_fill"]):
            add("mode-matches-spec", "duotone icon has no primary layer",
                'draw the primary shape with stroke="currentColor" or a fully opaque fill')
        if any(abs(o - level) > OPACITY_TOLERANCE for o in layers["secondary"]):
            add("duotone-opacity-consistent",
                f"secondary opacity {sorted(set(layers['secondary']))} differs from the set level {level:g}",
                f'fill-opacity="{level:g}"', "error")
    return out


# ------------------------------------------------------------------------------ variant pairs

def rendered_bounds(svg_bytes: bytes, grid: int, scale: int = 8) -> tuple[float, float, float, float] | None:
    """Bounding box of the painted pixels in grid units, measured on a render by the pinned renderer."""
    import tempfile

    from PIL import Image

    import common

    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "bounds.png"
        common.render_svg(svg_bytes, png, grid * scale)
        with Image.open(png) as im:
            box = im.convert("RGBA").getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    return None if box is None else tuple(v / scale for v in box)  # type: ignore[return-value]


def variant_findings(base_bytes: bytes, variant_bytes: bytes, grid: int, spec: dict) -> list[dict]:
    """The filled variant of an icon must occupy the same box as its base, within a tolerance."""
    tol = limit(spec, "variant-bounds-parity", VARIANT_BOUNDS_TOLERANCE)
    base, var = rendered_bounds(base_bytes, grid), rendered_bounds(variant_bytes, grid)
    if base is None or var is None:
        return [finding("variant-bounds-parity", "error", "the base or the variant renders no painted pixels",
                        "draw geometry inside the viewBox")]
    drift = max(abs(a - b) for a, b in zip(base, var))
    if drift <= tol:
        return []
    fmt = lambda box: f"x {box[0]:g}-{box[2]:g}, y {box[1]:g}-{box[3]:g}"  # noqa: E731
    return [finding("variant-bounds-parity", "error" if drift > 2 * tol else "warning",
                    f"variant occupies {fmt(var)} but its base occupies {fmt(base)} (edge drift {drift:g} units)",
                    f"match the base box {fmt(base)} within {tol:g} unit")]
