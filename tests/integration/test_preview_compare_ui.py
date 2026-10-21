"""Preview compare UI: Before/After controls, group scope, context profiles, offline and escaping guarantees."""
from __future__ import annotations

import json
import re

from conftest import run_json, run_script

CONTEXT_PAGES = ("desktop", "web", "web-img")


def preview(set_dir, *extra):
    proc = run_script("render_preview.py", "--set", set_dir, *extra)
    assert proc.returncode == 0, proc.stderr
    return set_dir / "preview"


def pages(prev):
    return [prev / "index.html", *[prev / "contexts" / f"{n}.html" for n in CONTEXT_PAGES]]


def test_index_labels_before_and_after_and_offers_controls(pilot_set):
    html = (preview(pilot_set) / "index.html").read_text()
    assert "Before (reference)" in html and "After (redrawn)" in html
    for control in ("Theme", "State", "Size", "Show", "Group"):
        assert f"<legend>{control}</legend>" in html
    for ident in ("th-light", "th-dark", "st-normal", "st-disabled", "sz-16", "sz-32", "md-before", "md-after", "g-all", "g-0"):
        assert f'id="{ident}"' in html
    assert re.search(r'data-theme="dark" data-state="disabled"', html)
    assert "No reference" not in html and "No master yet" not in html


def test_group_scope_limits_icons_and_reports_groups(pilot_set):
    proc, out = run_json("render_preview.py", "--set", pilot_set, "--group", "devices-connectivity")
    assert proc.returncode == 0, proc.stderr
    assert out["icons"] == 4 and out["groups"] == [{"name": "devices-connectivity", "icons": 4}]
    html = (pilot_set / "preview" / "index.html").read_text()
    assert 'id="pump"' in html and 'id="save"' not in html


def test_unknown_group_is_rejected_with_valid_names(pilot_set):
    proc = run_script("render_preview.py", "--set", pilot_set, "--group", "nope")
    assert proc.returncode == 2
    assert "nope" in proc.stderr + proc.stdout and "file-edit" in proc.stderr + proc.stdout


def test_narrowed_group_view_does_not_advance_run_state(pilot_set):
    run_json("render_preview.py", "--set", pilot_set, "--group", "file-edit")
    stage = json.loads((pilot_set / "run-state.json").read_text())["stage"]
    assert stage != "PILOT_READY"


def test_three_context_profiles_compare_before_and_after_with_existing_images(pilot_set):
    prev = preview(pilot_set)
    for name in CONTEXT_PAGES:
        page = prev / "contexts" / f"{name}.html"
        html = page.read_text()
        assert "SIMULATION" in html and "not the actual application" in html
        assert 'class="cside before' in html and 'class="cside after' in html
        for src in re.findall(r'src="([^"]+)"', html):
            assert (page.parent / src).is_file(), f"{name}: broken image {src}"
    assert "sc-200" in (prev / "contexts" / "desktop.html").read_text()
    assert ".svg" in (prev / "contexts" / "web-img.html").read_text()


def test_all_pages_stay_offline_and_script_free(pilot_set):
    for page in pages(preview(pilot_set)):
        assert not re.search(r"https?://|//cdn|@import|<script|\son\w+=", page.read_text()), page.name


def test_missing_reference_and_missing_master_get_explicit_placeholders(pilot_set):
    (pilot_set / "preview").mkdir(exist_ok=True)
    inv = json.loads((pilot_set / "inventory.json").read_text())
    ref = next(i for i in inv["icons"] if i["id"] == "pump")["references"][0]["path"]
    (pilot_set / ref).resolve().unlink()
    (pilot_set / "masters" / "network.svg").unlink()
    html = (preview(pilot_set) / "index.html").read_text()
    assert "No reference" in html and "No master yet" in html


def test_group_names_are_escaped_and_never_used_as_ids(pilot_set):
    inv = json.loads((pilot_set / "inventory.json").read_text())
    inv["icons"][0]["functional_group"] = '"><script>alert(1)</script>'
    (pilot_set / "inventory.json").write_text(json.dumps(inv))
    for page in pages(preview(pilot_set)):
        text = page.read_text()
        assert "<script" not in text and "&lt;script&gt;" in text, page.name
        assert re.findall(r'id="g-[^"]*"', text) and all(re.fullmatch(r'id="g-(all|\d+)"', m) for m in re.findall(r'id="g-[^"]*"', text))
