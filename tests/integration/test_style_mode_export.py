"""AT-12 and AT-14 for filled variants and opacity-duotone icons: export, post-export QA and preview
(constructed fixtures, not designs)."""
from __future__ import annotations

import json
import shutil

import pytest
from PIL import Image

from conftest import ROOT, approve_set, restrict_pilot, run_json, run_script
from test_style_modes import DUOTONE, FILLED, OUTLINE

pytestmark = pytest.mark.skipif(shutil.which("resvg") is None, reason="needs the pinned renderer")

SECONDARY_ALPHA = round(0.3 * 255)


def source_qa(set_dir):
    return run_json("validate_icons.py", "--set", set_dir, "--phase", "source", "--project-root", ROOT)


def export_and_inspect(set_dir):
    assert run_script("export_assets.py", "--set", set_dir).returncode == 0
    return run_json("validate_icons.py", "--set", set_dir, "--phase", "exported")


def png(set_dir, theme, state, size, icon):
    return Image.open(set_dir / "exports" / "desktop" / theme / state / str(size) / f"{icon}.png").convert("RGBA")


@pytest.fixture
def filled_pair_set(pilot_set, tmp_path):
    """Outline set whose valve also has a filled variant, pilot and variant approved, source QA passed."""
    (pilot_set / "masters" / "valve.svg").write_text(OUTLINE)
    assert run_script("variants.py", "add", "--set", pilot_set, "--base", "valve").returncode == 0
    (pilot_set / "masters" / "valve-filled.svg").write_text(FILLED)
    approve_set(pilot_set, tmp_path, kind="pilot")
    approve_set(pilot_set, tmp_path, kind="batch", ids=["valve-filled"])
    proc, report = source_qa(pilot_set)
    assert proc.returncode == 0, report["icons"]
    return pilot_set


@pytest.fixture
def duotone_set(pilot_set, tmp_path):
    """One-icon set in duotone mode with an approved pilot and passing source QA."""
    restrict_pilot(pilot_set, ["valve"])
    (pilot_set / "masters" / "valve.svg").write_text(DUOTONE)
    spec_path = pilot_set / "style-spec.json"
    spec = json.loads(spec_path.read_text())
    spec.update(style_mode="duotone", duotone_secondary_opacity=0.3)
    spec_path.write_text(json.dumps(spec))
    approve_set(pilot_set, tmp_path, kind="pilot")
    proc, report = source_qa(pilot_set)
    assert proc.returncode == 0, report["icons"]
    return pilot_set


def test_a_filled_variant_exports_beside_its_base_in_every_theme_state_and_size(filled_pair_set):
    proc, report = export_and_inspect(filled_pair_set)
    assert proc.returncode == 0, report["icons"]["valve-filled"]
    for theme in ("light", "dark"):
        for state in ("normal", "disabled"):
            for size in (16, 20, 24, 32):
                assert png(filled_pair_set, theme, state, size, "valve-filled").size == (size, size)
                assert png(filled_pair_set, theme, state, size, "valve").size == (size, size)


def test_the_filled_knockout_exports_as_transparent_pixels(filled_pair_set):
    export_and_inspect(filled_pair_set)
    im = png(filled_pair_set, "light", "normal", 32, "valve-filled")
    cx = cy = im.size[0] // 2
    assert im.getpixel((cx, cy))[3] == 0, "the plus is cut out of the disc"
    assert im.getpixel((cx, cy - 11))[3] > 200, "the disc is solid"


def test_the_filled_web_svg_is_the_master_and_keeps_current_color(filled_pair_set):
    export_and_inspect(filled_pair_set)
    svg = (filled_pair_set / "exports" / "web" / "valve-filled.svg").read_text()
    assert svg == (filled_pair_set / "masters" / "valve-filled.svg").read_text() and "currentColor" in svg


def test_the_resolved_color_web_variant_of_a_filled_icon_has_no_current_color(filled_pair_set):
    assert export_and_inspect(filled_pair_set)[0].returncode == 0
    assert run_script("export_assets.py", "--set", filled_pair_set, "--target", "web", "--web-img").returncode == 0
    img = list((filled_pair_set / "exports" / "web" / "img").rglob("valve-filled.svg"))
    assert img and all("currentColor" not in p.read_text() for p in img)
    proc, report = run_json("validate_icons.py", "--set", filled_pair_set, "--phase", "exported")
    assert proc.returncode == 0, report["icons"]["valve-filled"]


def test_the_manifest_status_of_a_variant_follows_its_own_approval(filled_pair_set):
    entries = {i["id"]: i for i in json.loads((filled_pair_set / "manifest.json").read_text())["icons"]}
    assert entries["valve-filled"]["status"] == "eligible" and entries["valve-filled"]["variant_of"] == "valve"


def test_duotone_keeps_the_secondary_layer_translucent_and_the_primary_opaque_in_the_png(duotone_set):
    proc, report = export_and_inspect(duotone_set)
    assert proc.returncode == 0, report["icons"]["valve"]
    im = png(duotone_set, "light", "normal", 32, "valve")
    cx = cy = im.size[0] // 2
    alphas = {im.getpixel((x, y))[3] for x in range(im.size[0]) for y in range(im.size[1])}
    off_axis = im.getpixel((cx + 4, cy - 4))[3]
    assert abs(off_axis - SECONDARY_ALPHA) <= 3, f"secondary layer alpha {off_axis}"
    assert 255 in alphas, "the primary stroke is opaque"


def test_duotone_web_svg_keeps_fill_opacity_and_current_color(duotone_set):
    export_and_inspect(duotone_set)
    svg = (duotone_set / "exports" / "web" / "valve.svg").read_text()
    assert 'fill-opacity="0.3"' in svg and "currentColor" in svg


def test_post_export_qa_flags_a_png_that_lost_its_secondary_layer(duotone_set, tmp_path):
    import validate_icons
    spec = json.loads((duotone_set / "style-spec.json").read_text())
    item = {"size_px": 32, "color": "#334155", "theme": "light", "state": "normal",
            "source": duotone_set / "masters" / "valve.svg"}
    export_and_inspect(duotone_set)
    good = duotone_set / "exports" / "desktop" / "light" / "normal" / "32" / "valve.png"
    assert validate_icons._png_problems(good, item, spec) == []
    # what a renderer that ignores fill-opacity would have produced
    import re

    from common import recolor_svg, render_svg
    master = (duotone_set / "masters" / "valve.svg").read_text()
    flat = tmp_path / "flat.png"
    render_svg(recolor_svg(re.sub(r'\sfill-opacity="[^"]*"', "", master), "#334155").encode(), flat, 32)
    assert any("secondary layer is missing" in e for e in validate_icons._png_problems(flat, item, spec))


@pytest.mark.parametrize("size", [16, 24, 32])
def test_the_secondary_layer_check_is_not_fooled_by_antialiased_edges_of_an_outline_icon(duotone_set, tmp_path, size):
    """An outline PNG has anti-aliased pixels near any alpha value, but it still shows no translucent layer."""
    import validate_icons
    spec = json.loads((duotone_set / "style-spec.json").read_text())
    outline_source = tmp_path / "outline-with-claim.svg"
    outline_source.write_text(OUTLINE.replace("<circle", '<circle fill-opacity="0.3"'))
    export_and_inspect(duotone_set)
    png_path = duotone_set / "exports" / "desktop" / "light" / "normal" / str(size) / "valve.png"
    stripped = tmp_path / "outline.png"
    from common import recolor_svg, render_svg
    render_svg(recolor_svg(OUTLINE, "#334155").encode(), stripped, size)
    item = {"size_px": size, "color": "#334155", "theme": "light", "state": "normal", "source": outline_source}
    assert any("secondary layer is missing" in e for e in validate_icons._png_problems(stripped, item, spec))
    item["source"] = duotone_set / "masters" / "valve.svg"
    assert validate_icons._png_problems(png_path, item, spec) == []


def test_a_filled_variant_in_a_duotone_set_passes_post_export_qa(duotone_set, tmp_path):
    assert run_script("variants.py", "add", "--set", duotone_set, "--base", "valve").returncode == 0
    (duotone_set / "masters" / "valve-filled.svg").write_text(FILLED)
    approve_set(duotone_set, tmp_path, kind="batch", ids=["valve-filled"])
    proc, report = source_qa(duotone_set)
    assert proc.returncode == 0, report["icons"]["valve-filled"]
    proc, report = export_and_inspect(duotone_set)
    assert proc.returncode == 0, report["icons"]["valve-filled"]


def preview_html(set_dir, *extra):
    proc = run_script("render_preview.py", "--set", set_dir, *extra)
    assert proc.returncode == 0, proc.stderr
    return (set_dir / "preview" / "index.html").read_text()


def test_preview_offers_a_form_filter_and_links_a_variant_to_its_base(filled_pair_set):
    html = preview_html(filled_pair_set)
    assert 'id="fm-filled"' in html and 'id="fm-outline"' in html
    assert 'data-form="filled"' in html and 'data-form="outline"' in html
    assert 'variant of <a href="#valve">valve</a>' in html
    assert 'body:has(#fm-filled:checked) .icon:not([data-form="filled"])' in html


def test_preview_pilot_scope_carries_the_variant_in_with_its_base(filled_pair_set):
    brief_path = filled_pair_set / "brief.json"
    brief = json.loads(brief_path.read_text())
    brief["sample_ids"] = ["valve"]
    brief_path.write_text(json.dumps(brief))
    html = preview_html(filled_pair_set, "--scope", "pilot")
    assert 'id="valve-filled"' in html and 'id="add"' not in html


def test_preview_of_a_single_form_set_has_no_form_filter(pilot_set):
    html = preview_html(pilot_set, "--scope", "all")
    assert 'name="fm"' not in html and "mode outline" in html


def test_preview_states_the_duotone_mode(duotone_set):
    assert "mode duotone" in preview_html(duotone_set, "--scope", "all")
