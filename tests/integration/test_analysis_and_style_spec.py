"""AT-06 (existing SVG analysis, redesign mode) and AT-07 (style outputs agree)."""
from __future__ import annotations

import json
import shutil

from conftest import FIXTURES, ROOT, run_json, run_script

import analysis


def read(set_dir, rel):
    return json.loads((set_dir / rel).read_text())


# ------------------------------------------------------------------ AT-06

def test_at06_baseline_audit_and_mode_recorded(inventoried):
    assert run_script("analysis.py", "brief", "--set", inventoried, "--mode", "redraw").returncode == 0
    assert run_script("analysis.py", "sample", "--set", inventoried).returncode == 0
    proc, out = run_json("analysis.py", "audit", "--set", inventoried, "--project-root", ROOT)
    assert proc.returncode == 0, proc.stderr
    assert out["baseline"] == "native-svg" and out["svg_references"] == 4

    baseline = read(inventoried, "reports/baseline-audit.json")
    lock = json.loads((ROOT / "dependencies.lock.json").read_text())
    assert baseline["commit"] == lock["upstream"]["commit"], "baseline must name the locked upstream revision"
    assert baseline["audit"]["summary"]["counts"].get("blocking", 0) > 0, "legacy SVGs are inconsistent"

    brief = read(inventoried, "brief.json")
    assert brief["redesign_mode"] == "redraw"
    assert len(brief["sample_ids"]) == 10 and "sample_exception" not in brief
    report = (inventoried / "reports" / "reference-analysis.md").read_text()
    assert "native SVG geometry" in report and "visual interpretation (PNG)" in report, \
        "PNG interpretations must be labeled as such"


def test_at06_finalize_requires_a_written_direction(inventoried):
    run_script("analysis.py", "brief", "--set", inventoried)
    run_script("analysis.py", "sample", "--set", inventoried)
    run_script("analysis.py", "audit", "--set", inventoried, "--project-root", ROOT)
    blocked = run_script("analysis.py", "finalize", "--set", inventoried)
    assert blocked.returncode == 2 and "pending marker" in blocked.stderr

    report = inventoried / "reports" / "reference-analysis.md"
    text = report.read_text().replace(analysis.PENDING_MARKER, "Redraw on a 24 grid with 1.5 strokes.")
    report.write_text(text)
    assert run_script("analysis.py", "finalize", "--set", inventoried).returncode == 0
    assert read(inventoried, "run-state.json")["stage"] == "REFERENCES_ANALYZED"


def test_reinterpret_needs_explicit_semantic_approval(inventoried):
    refused = run_script("analysis.py", "brief", "--set", inventoried, "--mode", "reinterpret")
    assert refused.returncode == 2
    assert "semantic approval" in refused.stderr and "clarification" in refused.stderr
    assert not (inventoried / "brief.json").exists()
    ok = run_script("analysis.py", "brief", "--set", inventoried, "--mode", "reinterpret", "--semantic-approval")
    assert ok.returncode == 0
    assert read(inventoried, "brief.json")["semantic_approval"] is True


def test_png_only_set_records_visual_interpretation_route(tmp_path, refs10):
    for svg in refs10.glob("*.svg"):
        svg.unlink()
    for name in ("save", "open-folder", "settings"):  # these had only SVG references
        shutil.copy(FIXTURES / "references" / "add.png", refs10 / f"{name}.png")
    set_dir = tmp_path / "png-only"
    assert run_script("inventory_icons.py", "--input", refs10, "--set", set_dir).returncode == 0
    run_script("analysis.py", "brief", "--set", set_dir)
    proc, out = run_json("analysis.py", "audit", "--set", set_dir, "--project-root", ROOT)
    assert out["baseline"] == "png-visual-interpretation" and out["svg_references"] == 0
    assert "visual interpretation" in (set_dir / "reports" / "reference-analysis.md").read_text()


def make_icons(count):
    groups = ["file-edit", "navigation-layout", "devices-connectivity", "alarms-events", "trends-reports",
              "users-settings"]
    return [{"id": f"icon-{n:02d}", "functional_group": groups[n % 6], "semantic_role": "action",
             "references": [{"kind": "png", "path": "missing.png"}]} for n in range(count)]


def test_sample_selection_bounds_and_group_coverage(tmp_path):
    ids, exception = analysis.select_sample(make_icons(30), tmp_path)
    assert 8 <= len(ids) <= 12 and exception is None
    covered = {i["functional_group"] for i in make_icons(30) if i["id"] in ids}
    assert len(covered) == 6, "every functional group is represented"
    ids, exception = analysis.select_sample(make_icons(5), tmp_path)
    assert len(ids) == 5 and "fewer than 8" in exception


# ------------------------------------------------------------------ AT-07

def make_style_set(tmp_path):
    set_dir = tmp_path / "style-set"
    set_dir.mkdir()
    assert run_script("style_spec.py", "init", "--set", set_dir, "--set-id", "scada-fixture").returncode == 0
    assert run_script("style_spec.py", "generate", "--set", set_dir).returncode == 0
    return set_dir


def test_at07_documents_agree_then_contradiction_is_detected(tmp_path):
    set_dir = make_style_set(tmp_path)
    ok, data = run_json("style_spec.py", "check", "--set", set_dir)
    assert ok.returncode == 0 and data["consistent"] is True

    md = set_dir / "icon-style.md"
    md.write_text(md.read_text().replace("| `stroke_width` | 1.5 |", "| `stroke_width` | 2 |"))
    bad, data = run_json("style_spec.py", "check", "--set", set_dir)
    assert bad.returncode == 4
    assert data["contradictions"] == [{"parameter": "stroke_width", "json": "1.5", "markdown": "2"}]
    assert "stroke_width" in bad.stderr


def test_at07_json_change_is_flagged_until_summary_regenerated(tmp_path):
    set_dir = make_style_set(tmp_path)
    md = set_dir / "icon-style.md"
    prose = md.read_text().replace("State why this grid", "We chose 1.5 strokes because X. State why this grid")
    md.write_text(prose)

    spec = json.loads((set_dir / "style-spec.json").read_text())
    spec["grid"] = 16
    spec["themes"]["dark"]["normal"] = "#CBD5E1"
    (set_dir / "style-spec.json").write_text(json.dumps(spec))
    stale, data = run_json("style_spec.py", "check", "--set", set_dir)
    assert stale.returncode == 4
    assert {c["parameter"] for c in data["contradictions"]} == {"grid", "themes.dark.normal"}

    assert run_script("style_spec.py", "generate", "--set", set_dir).returncode == 0
    assert run_json("style_spec.py", "check", "--set", set_dir)[0].returncode == 0
    assert "We chose 1.5 strokes because X." in md.read_text(), "hand-written rationale is preserved"


def test_style_spec_provisional_palette_is_labeled_and_init_never_overwrites(tmp_path):
    set_dir = make_style_set(tmp_path)
    assert "not the official brand palette" in (set_dir / "icon-style.md").read_text()
    again = run_script("style_spec.py", "init", "--set", set_dir)
    assert again.returncode == 2 and "already exists" in again.stderr


def fill_prose(set_dir):
    import style_spec
    md = set_dir / "icon-style.md"
    text = md.read_text()
    for n, placeholder in enumerate(style_spec.PLACEHOLDERS):
        text = text.replace(placeholder, f"Written section {n}.")
    md.write_text(text)


def test_finalize_refuses_template_text(tmp_path):
    set_dir = make_style_set(tmp_path)
    proc = run_script("style_spec.py", "finalize", "--set", set_dir)
    assert proc.returncode == 4 and "still contains template text" in proc.stderr
    assert not (set_dir / "run-state.json").exists()
    _, data = run_json("style_spec.py", "check", "--set", set_dir)
    assert data["consistent"] is True and len(data["unfilled_sections"]) == 4


def test_finalize_advances_only_when_consistent_and_hash_is_stable(tmp_path):
    set_dir = make_style_set(tmp_path)
    fill_prose(set_dir)
    first = run_script("style_spec.py", "hash", "--set", set_dir).stdout.strip()
    assert first == run_script("style_spec.py", "hash", "--set", set_dir).stdout.strip()
    md = set_dir / "icon-style.md"
    good = md.read_text()
    md.write_text(good.replace("| `padding` | 2 |", "| `padding` | 3 |"))
    assert run_script("style_spec.py", "finalize", "--set", set_dir).returncode == 4
    assert not (set_dir / "run-state.json").exists()
    md.write_text(good)
    proc, data = run_json("style_spec.py", "finalize", "--set", set_dir)
    assert proc.returncode == 0 and data["stage"] == "SPEC_READY" and data["style_hash"] == first
    assert json.loads((set_dir / "run-state.json").read_text())["stage"] == "SPEC_READY"


def test_changing_any_style_value_changes_the_hash(tmp_path):
    set_dir = make_style_set(tmp_path)
    before = run_script("style_spec.py", "hash", "--set", set_dir).stdout.strip()
    spec = json.loads((set_dir / "style-spec.json").read_text())
    spec["themes"]["light"]["normal"] = "#111827"
    (set_dir / "style-spec.json").write_text(json.dumps(spec))
    assert run_script("style_spec.py", "hash", "--set", set_dir).stdout.strip() != before
