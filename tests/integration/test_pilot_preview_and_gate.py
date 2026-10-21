"""AT-04 (PNG redraw evidence), AT-08 (pilot and approval gate), AT-09 (context preview)."""
from __future__ import annotations

import json
import re

from PIL import Image

from conftest import run_json, run_script, write_scores

TEN = ["add", "alarm-list", "device-connect", "network", "open-folder", "pump", "save", "settings",
       "trend-chart", "valve"]


def preview(set_dir, *extra):
    proc = run_script("render_preview.py", "--set", set_dir, *extra)
    assert proc.returncode == 0, proc.stderr
    return set_dir / "preview"


def read_state(set_dir):
    return json.loads((set_dir / "run-state.json").read_text())


# ------------------------------------------------------------------ AT-04

def test_at04_masters_are_editable_vector_geometry(pilot_set):
    for icon_id in TEN:
        text = (pilot_set / "masters" / f"{icon_id}.svg").read_text()
        assert "<path" in text and "<image" not in text and "base64" not in text


def test_at04_before_after_pairs_exist_at_actual_size(pilot_set):
    prev = preview(pilot_set)
    html = (prev / "index.html").read_text()
    assert 'src="renders/reference/16/pump.png"' in html and 'src="renders/light/normal/16/pump.png"' in html
    new = Image.open(prev / "renders" / "light" / "normal" / "16" / "pump.png")
    ref = Image.open(prev / "renders" / "reference" / "16" / "pump.png")
    assert new.size == (16, 16) and ref.size == (16, 16)
    assert new.mode == "RGBA" and new.getchannel("A").getextrema()[0] == 0, "transparent background"


# ------------------------------------------------------------------ AT-09

def test_at09_four_sizes_two_themes_two_states(pilot_set):
    prev = preview(pilot_set)
    renders = prev / "renders"
    new = [p for p in renders.rglob("*.png") if "reference" not in p.parts and "enlarged" not in p.parts]
    assert len(new) == 10 * 4 * 2 * 2, "10 icons x 4 sizes x 2 themes x 2 states"
    assert len(list((renders / "reference").rglob("*.png"))) == 10 * 4
    assert len(list(renders.rglob("enlarged/*.png"))) == 10 * 2 * 2
    html = (prev / "index.html").read_text()
    for size in (16, 20, 24, 32):
        assert f"{size}px" in html
    assert "light / disabled" in html and "dark / normal" in html
    assert "supplement" in html


def test_at09_contexts_are_labeled_simulations_and_fully_offline(pilot_set):
    prev = preview(pilot_set)
    for name in ("desktop", "web"):
        page = (prev / "contexts" / f"{name}.html").read_text()
        assert "SIMULATION" in page and "not the actual application" in page
    desktop = (prev / "contexts" / "desktop.html").read_text()
    for label in ("Toolbar", "Menu", "Ribbon-like", "Device list"):
        assert label in desktop
    web = (prev / "contexts" / "web.html").read_text()
    for label in ("Navigation", "Actions", "List"):
        assert label in web
    for page in (prev / "index.html", prev / "contexts" / "desktop.html", prev / "contexts" / "web.html"):
        assert not re.search(r"https?://|//cdn|@import|<script", page.read_text()), f"{page.name} must be offline"


def test_preview_escapes_labels_and_blocks_hostile_masters(pilot_set):
    inv = json.loads((pilot_set / "inventory.json").read_text())
    inv["icons"][0]["meaning"] = '<img src=x onerror=alert(1)>'
    (pilot_set / "inventory.json").write_text(json.dumps(inv))
    (pilot_set / "masters" / "save.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><script>alert(1)</script></svg>')
    prev = preview(pilot_set)
    html = (prev / "index.html").read_text() + (prev / "contexts" / "web.html").read_text()
    assert "&lt;img src=x onerror=alert(1)&gt;" in html and "<img src=x" not in html
    assert "alert(1)</script>" not in html and "<script" not in html
    assert not (prev / "renders" / "light" / "normal" / "16" / "save.png").exists()


def test_contrast_is_token_level_with_disabled_reported_separately(pilot_set):
    preview(pilot_set)
    report = json.loads((pilot_set / "reports" / "contrast.json").read_text())
    assert report["passes"] is True
    light = report["themes"]["light"]
    assert light["normal"]["ratio"] >= 3 and light["disabled"]["reported_only"] is True
    assert "token-level" in report["scope"]
    spec = json.loads((pilot_set / "style-spec.json").read_text())
    spec["themes"]["light"]["normal"] = "#CCCCCC"
    (pilot_set / "style-spec.json").write_text(json.dumps(spec))
    prev = preview(pilot_set)
    assert json.loads((pilot_set / "reports" / "contrast.json").read_text())["passes"] is False
    assert "FAIL" in (prev / "index.html").read_text()


def test_small_variant_is_used_only_at_its_sizes(pilot_set):
    (pilot_set / "variants" / "small").mkdir(parents=True)
    master = (pilot_set / "masters" / "pump.svg").read_text()
    (pilot_set / "variants" / "small" / "pump.svg").write_text(master.replace("stroke-width", "data-x=\"1\" stroke-width"))
    html = (preview(pilot_set) / "index.html").read_text()
    assert 'alt="redrawn pump (small-variant)" width="16"' in html
    assert 'alt="redrawn pump (master)" width="24"' in html


def test_preview_marks_icons_without_master_and_draft_status(pilot_set):
    (pilot_set / "masters" / "network.svg").unlink()
    proc, out = run_json("render_preview.py", "--set", pilot_set)
    assert out["missing_masters"] == ["network"]
    html = (pilot_set / "preview" / "index.html").read_text()
    assert "no master yet" in html and "draft (pending approval)" in html
    assert read_state(pilot_set)["stage"] != "PILOT_READY", "an incomplete pilot is not ready"


def test_preview_advances_to_pilot_ready_when_complete(pilot_set):
    preview(pilot_set)
    assert read_state(pilot_set)["stage"] == "PILOT_READY"


# ------------------------------------------------------------------ AT-08

def approve(set_dir, scores, reviewer="user", *extra):
    return run_script("approvals.py", "record", "--set", set_dir, "--type", "pilot", "--reviewer", reviewer,
                      "--scores-file", scores, *extra)


def test_at08_gate_is_closed_without_approval(pilot_set):
    proc, data = run_json("approvals.py", "check", "--set", pilot_set, "--type", "pilot")
    assert proc.returncode == 4 and data["valid"] is False and "no pilot approval" in data["reason"]


def test_at08_pilot_approval_needs_rubric_scores_of_four_or_more(pilot_set, tmp_path):
    assert run_script("approvals.py", "record", "--set", pilot_set, "--type", "pilot",
                      "--reviewer", "user").returncode == 4
    low = write_scores(tmp_path / "low.json", TEN, clarity_16=3)
    refused = approve(pilot_set, low)
    assert refused.returncode == 4 and "below 4 on clarity_16" in refused.stderr
    defect = write_scores(tmp_path / "defect.json", TEN, semantic_defect=True)
    assert "semantic defect" in approve(pilot_set, defect).stderr
    partial = write_scores(tmp_path / "partial.json", TEN[:5])
    assert "no scores" in approve(pilot_set, partial).stderr
    assert not (pilot_set / "approvals.json").exists()


def test_at08_valid_approval_opens_the_gate_and_is_hash_bound(pilot_set, tmp_path):
    scores = write_scores(tmp_path / "ok.json", TEN)
    assert approve(pilot_set, scores, "user", "--note", "pilot looks right").returncode == 0
    proc, data = run_json("approvals.py", "check", "--set", pilot_set)
    assert proc.returncode == 0 and data["valid"] and data["reviewer_type"] == "user"
    assert read_state(pilot_set)["stage"] == "PILOT_APPROVED"
    record = json.loads((pilot_set / "approvals.json").read_text())["approvals"][0]
    assert len(record["style_hash"]) == 64 and set(record["asset_hashes"]) == set(TEN)
    assert record["scores"]["pump"]["meaning"] == 5


def test_at08_stale_approval_is_rejected_after_asset_or_style_change(pilot_set, tmp_path):
    scores = write_scores(tmp_path / "ok.json", TEN)
    assert approve(pilot_set, scores).returncode == 0
    master = pilot_set / "masters" / "pump.svg"
    original = master.read_text()
    master.write_text(original.replace("1.5", "2"))
    proc, data = run_json("approvals.py", "check", "--set", pilot_set)
    assert proc.returncode == 4 and data["stale"] == ["pump"]
    master.write_text(original)
    assert run_script("approvals.py", "check", "--set", pilot_set).returncode == 0
    spec = json.loads((pilot_set / "style-spec.json").read_text())
    spec["stroke_width"] = 2
    (pilot_set / "style-spec.json").write_text(json.dumps(spec))
    proc, data = run_json("approvals.py", "check", "--set", pilot_set)
    assert proc.returncode == 4 and "style" in data["stale"]


def test_at08_agent_review_is_never_labeled_human_approval(pilot_set, tmp_path):
    scores = write_scores(tmp_path / "ok.json", TEN)
    refused = approve(pilot_set, scores, "agent")
    assert refused.returncode == 4 and "not human approval" in refused.stderr
    assert not (pilot_set / "approvals.json").exists()
    assert approve(pilot_set, scores, "agent", "--unattended-authorized").returncode == 0
    data = json.loads((pilot_set / "approvals.json").read_text())
    assert data["approvals"][0]["reviewer_type"] == "agent"
    assert run_json("approvals.py", "check", "--set", pilot_set)[1]["reviewer_type"] == "agent"


def test_at08_approval_requires_every_master_to_exist(pilot_set, tmp_path):
    (pilot_set / "masters" / "valve.svg").unlink()
    scores = write_scores(tmp_path / "ok.json", TEN)
    refused = approve(pilot_set, scores)
    assert refused.returncode == 2 and "no master for 'valve'" in refused.stderr


def test_small_variant_change_makes_approval_stale(pilot_set, tmp_path):
    scores = write_scores(tmp_path / "ok.json", TEN)
    assert approve(pilot_set, scores).returncode == 0
    (pilot_set / "variants" / "small").mkdir(parents=True)
    (pilot_set / "variants" / "small" / "save.svg").write_text((pilot_set / "masters" / "save.svg").read_text())
    proc, data = run_json("approvals.py", "check", "--set", pilot_set)
    assert proc.returncode == 4 and data["stale"] == ["save"]
