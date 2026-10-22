"""Palette tokens: WCAG contrast ratios and the token-level contrast report (FR-QA-03).

The check is token-level only. It does not replace visual review and does not establish
application-wide accessibility compliance.
"""
from __future__ import annotations

NORMAL_MIN_RATIO = 3.0


def _channel(v: int) -> float:
    c = v / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def state_colors(tokens: dict, state: str) -> tuple[str, str | None]:
    """The color of a state and, for the normal state only, the optional accent. Disabled paints every layer
    with the single disabled token."""
    if state != "normal":
        return tokens["disabled"].upper(), None
    accent = tokens.get("accent")
    return tokens["normal"].upper(), accent.upper() if accent else None


def contrast_report(spec: dict) -> dict:
    """Normal tokens must reach 3:1 on their background; disabled is reported separately."""
    themes = {}
    for name, tokens in sorted(spec["themes"].items()):
        normal = contrast_ratio(tokens["normal"], tokens["background"])
        disabled = contrast_ratio(tokens["disabled"], tokens["background"])
        themes[name] = {
            "background": tokens["background"].upper(),
            "normal": {"color": tokens["normal"].upper(), "ratio": normal, "required": NORMAL_MIN_RATIO,
                       "passes": normal >= NORMAL_MIN_RATIO},
            "disabled": {"color": tokens["disabled"].upper(), "ratio": disabled, "reported_only": True},
        }
        if tokens.get("accent"):
            ratio = contrast_ratio(tokens["accent"], tokens["background"])
            themes[name]["accent"] = {"color": tokens["accent"].upper(), "ratio": ratio, "required": NORMAL_MIN_RATIO,
                                      "passes": ratio >= NORMAL_MIN_RATIO}
    return {"scope": "token-level only; not a substitute for visual review or an accessibility audit",
            "passes": all(t["normal"]["passes"] and t.get("accent", {"passes": True})["passes"]
                          for t in themes.values()), "themes": themes}
