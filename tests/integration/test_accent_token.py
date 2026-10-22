"""The optional accent palette token: contract, rules, export and post-export QA (constructed fixtures)."""
from __future__ import annotations

import copy
import json
import shutil

import pytest
from PIL import Image

import consistency
import palette
import style_spec
from common import ACCENT_PAINT, ToolError, parse_svg, recolor_svg, validate_schema
from conftest import FIXTURES, ROOT, approve_set, restrict_pilot, run_json, run_script

HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" '
        'stroke-linejoin="round" ')
ACCENT_ICON = HEAD + (f'fill="none" stroke="currentColor"><circle cx="9" cy="9" r="5"/>'
                      f'<circle cx="16" cy="16" r="4" fill="{ACCENT_PAINT}" stroke="none"/></svg>')
LIGHT_ACCENT, DARK_ACCENT = "#7C3AED", "#A78BFA"
NORMAL = {"light": (0x33, 0x41, 0x55), "dark": (0xE2, 0xE8, 0xF0)}


@pytest.fixture
def spec():
    base = json.loads((FIXTURES / "style-spec.json").read_text())
    base["style_mode"] = "outline"
    base["themes"]["light"]["accent"] = LIGHT_ACCENT
    base["themes"]["dark"]["accent"] = DARK_ACCENT
    return base


def findings(svg, spec):
    return consistency.icon_findings(parse_svg(svg.encode()), spec)


def rules(found, severity=None):
    return {f["rule"] for f in found if severity in (None, f["severity"])}


# ------------------------------------------------------------------ contract

def test_the_accent_paint_is_resolved_before_current_color():
    text = f'<path fill="{ACCENT_PAINT}"/><path stroke="currentColor"/>'
    assert recolor_svg(text, "#111111", "#222222") == '<path fill="#222222"/><path stroke="#111111"/>'
    assert recolor_svg(text, "#111111") == '<path fill="#111111"/><path stroke="#111111"/>', "no accent: normal color"


def test_disabled_paints_every_layer_with_the_disabled_token(spec):
    tokens = spec["themes"]["light"]
    assert palette.state_colors(tokens, "normal") == (tokens["normal"].upper(), LIGHT_ACCENT)
    assert palette.state_colors(tokens, "disabled") == (tokens["disabled"].upper(), None)
    plain = {k: v for k, v in tokens.items() if k != "accent"}
    assert palette.state_colors(plain, "normal")[1] is None


def test_the_accent_belongs_to_the_palette_hash_not_the_geometry_hash(spec):
    plain = copy.deepcopy(spec)
    for theme in plain["themes"].values():
        theme.pop("accent")
    assert style_spec.geometry_hash(spec) == style_spec.geometry_hash(plain)
    assert style_spec.palette_hash(spec) != style_spec.palette_hash(plain)


def test_a_spec_without_an_accent_keeps_its_palette_hash():
    legacy = json.loads((FIXTURES / "style-spec.json").read_text())
    assert style_spec.palette_hash(legacy) == style_spec.palette_hash(copy.deepcopy(legacy))
    assert all("accent" not in t for t in legacy["themes"].values())


@pytest.mark.parametrize("bad", ["violet", "#7C3AE", "7C3AED"])
def test_the_schema_rejects_a_malformed_accent(spec, bad):
    spec["themes"]["light"]["accent"] = bad
    with pytest.raises(ToolError):
        validate_schema(spec, "style-spec", "spec")


def test_the_style_summary_lists_the_accent_rows(tmp_path):
    set_dir = tmp_path / "s"
    run_script("style_spec.py", "init", "--set", set_dir, "--style-mode", "outline")
    path = set_dir / "style-spec.json"
    data = json.loads(path.read_text())
    data["themes"]["light"]["accent"] = LIGHT_ACCENT
    data["themes"]["dark"]["accent"] = DARK_ACCENT
    path.write_text(json.dumps(data))
    run_script("style_spec.py", "generate", "--set", set_dir)
    assert f"| `themes.light.accent` | {LIGHT_ACCENT} |" in (set_dir / "icon-style.md").read_text()
    proc, out = run_json("style_spec.py", "check", "--set", set_dir)
    assert proc.returncode == 0 and out["consistent"] is True


def test_the_contrast_report_includes_the_accent(spec):
    report = palette.contrast_report(spec)
    assert report["themes"]["light"]["accent"]["passes"] and report["passes"] is True
    spec["themes"]["light"]["accent"] = "#F5F5F5"
    low = palette.contrast_report(spec)
    assert low["themes"]["light"]["accent"]["passes"] is False and low["passes"] is False


# ------------------------------------------------------------------ rules

def test_a_valid_accent_has_no_findings(spec):
    assert consistency.spec_findings(spec) == []
    assert findings(ACCENT_ICON, spec) == []


def test_a_faint_accent_is_reported_with_a_suggestion(spec):
    spec["themes"]["light"]["accent"] = "#E2E8F0"
    found = [f for f in consistency.spec_findings(spec) if f["rule"] == "accent-contrast"]
    assert [f["severity"] for f in found] == ["error"] and "at least 3.0:1" in found[0]["suggested"]
    legacy = {k: v for k, v in spec.items() if k != "style_mode"}
    assert {f["severity"] for f in consistency.spec_findings(legacy) if f["rule"] == "accent-contrast"} == {"warning"}


def test_an_accent_too_close_to_the_normal_colour_is_a_warning(spec):
    spec["themes"]["light"]["accent"] = "#3B4A5F"
    found = [f for f in consistency.spec_findings(spec) if f["rule"] == "accent-distinct"]
    assert found and found[0]["severity"] == "warning" and "RGB" in found[0]["suggested"]


def test_every_theme_must_have_an_accent_or_none(spec):
    del spec["themes"]["dark"]["accent"]
    assert "accent-token-complete" in rules(consistency.spec_findings(spec), "error")


def test_a_layer_painted_with_the_accent_needs_a_token(spec):
    for theme in spec["themes"].values():
        theme.pop("accent")
    found = findings(ACCENT_ICON, spec)
    assert rules(found, "error") == {"accent-token-declared"} and found[0]["suggested"]


def test_an_override_can_relax_the_accent_limits(spec):
    spec["themes"]["light"]["accent"] = "#9AA5B8"
    assert "accent-contrast" in rules(consistency.spec_findings(spec))
    spec["consistency_overrides"] = {"accent-contrast": {"reason": "decorative badge", "value": 1.5}}
    assert "accent-contrast" not in rules(consistency.spec_findings(spec))


def test_the_local_checker_accepts_the_accent_paint_and_rejects_other_variables(spec, tmp_path):
    import validate_icons
    ok, bad = tmp_path / "ok.svg", tmp_path / "bad.svg"
    ok.write_text(ACCENT_ICON)
    bad.write_text(ACCENT_ICON.replace(ACCENT_PAINT, "var(--brand, red)"))
    assert validate_icons.check_svg(ok, 24, tmp_path, spec)[0] == []
    assert any("fixed fill color" in e for e in validate_icons.check_svg(bad, 24, tmp_path, spec)[0])


# ------------------------------------------------------------------ pipeline

pytestmark_renderer = pytest.mark.skipif(shutil.which("resvg") is None, reason="needs the pinned renderer")


@pytest.fixture
def accent_set(pilot_set, tmp_path):
    """One accent icon, outline mode declared, an approved pilot and passing source QA."""
    restrict_pilot(pilot_set, ["valve"])
    (pilot_set / "masters" / "valve.svg").write_text(ACCENT_ICON)
    path = pilot_set / "style-spec.json"
    data = json.loads(path.read_text())
    data["style_mode"] = "outline"
    data["themes"]["light"]["accent"], data["themes"]["dark"]["accent"] = LIGHT_ACCENT, DARK_ACCENT
    path.write_text(json.dumps(data))
    approve_set(pilot_set, tmp_path, kind="pilot")
    proc, report = run_json("validate_icons.py", "--set", pilot_set, "--phase", "source", "--project-root", ROOT)
    assert proc.returncode == 0, report["icons"]
    return pilot_set


def png(set_dir, theme, state, size=32):
    return Image.open(set_dir / "exports" / "desktop" / theme / state / str(size) / "valve.png").convert("RGBA")


def near(pixel, rgb):
    return max(abs(pixel[c] - rgb[c]) for c in range(3)) <= 8


def hex_rgb(value):
    return tuple(int(value.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


@pytestmark_renderer
def test_the_locked_upstream_validator_accepts_a_master_with_an_accent_layer(accent_set):
    proc, report = run_json("validate_icons.py", "--set", accent_set, "--phase", "source", "--project-root", ROOT)
    assert proc.returncode == 0 and report["blocked"] is None
    assert report["icons"]["valve"]["errors"] == []


@pytestmark_renderer
def test_desktop_png_shows_the_accent_in_the_badge_and_the_normal_colour_elsewhere(accent_set):
    assert run_script("export_assets.py", "--set", accent_set).returncode == 0
    proc, report = run_json("validate_icons.py", "--set", accent_set, "--phase", "exported")
    assert proc.returncode == 0, report["icons"]["valve"]
    for theme, accent in (("light", LIGHT_ACCENT), ("dark", DARK_ACCENT)):
        im = png(accent_set, theme, "normal")
        s = im.size[0] / 24
        assert near(im.getpixel((int(17.5 * s), int(17.5 * s))), hex_rgb(accent)), "badge interior"
        assert near(im.getpixel((int(3.45 * s), int(9 * s))), NORMAL[theme]), "left edge of the main circle"


@pytestmark_renderer
def test_the_disabled_state_is_a_single_colour(accent_set):
    run_script("export_assets.py", "--set", accent_set)
    im = png(accent_set, "light", "disabled")
    tokens = json.loads((accent_set / "style-spec.json").read_text())["themes"]["light"]["disabled"]
    solid = {im.getpixel((x, y))[:3] for y in range(im.size[1]) for x in range(im.size[0]) if im.getpixel((x, y))[3] == 255}
    assert solid and all(near(c, hex_rgb(tokens)) for c in solid)


@pytestmark_renderer
def test_web_inline_keeps_the_variable_and_web_img_resolves_it(accent_set):
    assert run_script("export_assets.py", "--set", accent_set).returncode == 0
    assert run_script("export_assets.py", "--set", accent_set, "--target", "web", "--web-img").returncode == 0
    inline = (accent_set / "exports" / "web" / "valve.svg").read_text()
    assert inline == (accent_set / "masters" / "valve.svg").read_text() and ACCENT_PAINT in inline
    light = (accent_set / "exports" / "web" / "img" / "light" / "normal" / "valve.svg").read_text()
    assert LIGHT_ACCENT in light.upper() and "currentColor" not in light and "var(" not in light
    disabled = (accent_set / "exports" / "web" / "img" / "light" / "disabled" / "valve.svg").read_text()
    assert LIGHT_ACCENT not in disabled.upper()
    proc, report = run_json("validate_icons.py", "--set", accent_set, "--phase", "exported")
    assert proc.returncode == 0, report["icons"]["valve"]


@pytestmark_renderer
def test_post_export_qa_rejects_a_png_with_a_foreign_colour(accent_set):
    run_script("export_assets.py", "--set", accent_set)
    path = accent_set / "exports" / "desktop" / "light" / "normal" / "32" / "valve.png"
    im = Image.open(path).convert("RGBA")
    px = im.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            if px[x, y][3] == 255 and near(px[x, y], hex_rgb(LIGHT_ACCENT)):
                px[x, y] = (0, 200, 0, 255)
    im.save(path)
    import validate_icons
    item = {"size_px": 32, "color": "#334155", "accent": LIGHT_ACCENT, "theme": "light", "state": "normal",
            "source": accent_set / "masters" / "valve.svg"}
    assert any("match neither" in e for e in validate_icons._png_problems(path, item,
                                                                         json.loads((accent_set / "style-spec.json").read_text())))


@pytestmark_renderer
def test_changing_only_the_accent_makes_exports_stale_but_keeps_the_geometry_approval(accent_set):
    run_script("export_assets.py", "--set", accent_set)
    path = accent_set / "style-spec.json"
    data = json.loads(path.read_text())
    before = style_spec.geometry_hash(data)
    data["themes"]["light"]["accent"] = "#0E7490"
    path.write_text(json.dumps(data))
    assert style_spec.geometry_hash(data) == before
    proc, report = run_json("validate_icons.py", "--set", accent_set, "--phase", "exported")
    assert proc.returncode == 4 and any("stale" in e for e in report["icons"]["valve"]["errors"])
