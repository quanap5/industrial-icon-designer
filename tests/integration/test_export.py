"""AT-12..AT-16 and AT-20: export matrix, size overrides, post-export QA, web profiles, determinism, conflicts."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from conftest import ROOT, SCRIPTS, run_json, run_script

import export_assets

THEMES, STATES, SIZES = ("dark", "light"), ("disabled", "normal"), (16, 20, 24, 32)


def tree(path: Path) -> dict[str, str]:
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file()}


def manifest(set_dir):
    return {i["id"]: i for i in json.loads((set_dir / "manifest.json").read_text())["icons"]}


def state(set_dir):
    return json.loads((set_dir / "run-state.json").read_text())


def exported_png(set_dir):
    return sorted((set_dir / "exports" / "desktop").rglob("*.png"))


def post_export(set_dir):
    return run_json("validate_icons.py", "--set", set_dir, "--phase", "exported")


# ------------------------------------------------------------------ AT-12

def test_at12_full_matrix_is_160_pngs_plus_10_inline_svgs(exported):
    pngs = exported_png(exported)
    assert len(pngs) == 10 * 4 * 2 * 2
    assert len(list((exported / "exports" / "web").glob("*.svg"))) == 10
    assert not (exported / "exports" / "web" / "img").exists(), "resolved-color variants are opt-in and counted apart"
    for theme in THEMES:
        for st in STATES:
            for size in SIZES:
                assert len(list((exported / "exports" / "desktop" / theme / st / str(size)).glob("*.png"))) == 10
    icons = manifest(exported)
    assert sum(len(i["exports"]) for i in icons.values()) == 170
    assert state(exported)["stage"] == "EXPORTED"


def test_at12_pngs_are_transparent_rgba_at_exact_size(exported):
    for path in exported_png(exported)[:40]:
        size = int(path.parent.name)
        with Image.open(path) as im:
            assert im.size == (size, size) and im.mode == "RGBA"
            assert im.getchannel("A").getextrema()[0] == 0, "background is transparent"


def test_at12_each_size_is_rendered_directly_not_upscaled(exported):
    small = Image.open(exported / "exports/desktop/light/normal/16/pump.png")
    big = Image.open(exported / "exports/desktop/light/normal/32/pump.png")
    assert small.size == (16, 16) and big.size == (32, 32)
    assert big.resize((16, 16), Image.LANCZOS).tobytes() != small.tobytes(), "32px is not just a resized 16px"


def test_at12_dry_run_lists_changes_and_writes_nothing(exportable):
    before = tree(exportable)
    proc, out = run_json("export_assets.py", "--set", exportable, "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert out["dry_run"] is True and len(out["create"]) == 170 and out["conflicts"] == []
    assert out["planned"] == {"desktop-png": 160, "web-inline": 10}
    assert tree(exportable) == before and not (exportable / "exports").exists()


def test_post_export_qa_passes_and_reaches_assets_ready(exported):
    proc, report = post_export(exported)
    assert proc.returncode == 0, proc.stderr
    assert report["summary"] == {"checked": 10, "passed": 10, "failed": 0} and report["checked_files"] == 170
    assert state(exported)["stage"] == "ASSETS_READY"
    assert (exported / "reports" / "post-export-qa.json").exists()


# ------------------------------------------------------------------ AT-13

def test_at13_per_icon_sizes_follow_the_inventory(exportable):
    inv = json.loads((exportable / "inventory.json").read_text())
    for icon in inv["icons"]:
        if icon["id"] == "add":
            icon["sizes_px"] = [16, 24]
        if icon["id"] == "pump":
            icon["sizes_px"] = [32]
    (exportable / "inventory.json").write_text(json.dumps(inv))
    assert run_script("export_assets.py", "--set", exportable).returncode == 4, "drift must be applied first"
    assert run_script("invalidate.py", "detect", "--set", exportable, "--apply").returncode == 0
    proc, out = run_json("export_assets.py", "--set", exportable)
    assert proc.returncode == 0, proc.stderr
    assert len(exported_png(exportable)) == 8 * 16 + 2 * 4 + 1 * 4
    assert not list((exportable / "exports" / "desktop").rglob("20/add.png"))
    assert not list((exportable / "exports" / "desktop").rglob("16/pump.png")), "irrelevant sizes are not exported"
    assert len(list((exportable / "exports" / "desktop").rglob("32/pump.png"))) == 4


def test_at13_removed_sizes_are_cleaned_up_on_the_next_export(exported):
    inv = json.loads((exported / "inventory.json").read_text())
    next(i for i in inv["icons"] if i["id"] == "add")["sizes_px"] = [16, 24]
    (exported / "inventory.json").write_text(json.dumps(inv))
    run_script("invalidate.py", "detect", "--set", exported, "--apply")
    proc, out = run_json("export_assets.py", "--set", exported)
    assert proc.returncode == 0 and len(out["remove"]) == 8
    assert len(exported_png(exported)) == 160 - 8
    assert post_export(exported)[0].returncode == 0


# ------------------------------------------------------------------ AT-14

def tamper(set_dir, rel, new_bytes):
    """Replace an export and fix the manifest hash, so only the content checks can notice."""
    (set_dir / rel).write_bytes(new_bytes)
    data = json.loads((set_dir / "manifest.json").read_text())
    for icon in data["icons"]:
        for e in icon["exports"]:
            if e["path"] == rel:
                e["sha256"] = hashlib.sha256(new_bytes).hexdigest()
    (set_dir / "manifest.json").write_text(json.dumps(data))


def png_bytes(path: Path, edit):
    import io
    with Image.open(path) as im:
        im = im.convert("RGBA")
        edit(im)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()


def errors_for(set_dir, icon_id):
    proc, report = post_export(set_dir)
    return proc.returncode, report["icons"][icon_id]["errors"]


@pytest.mark.parametrize("name,edit,expected", [
    ("opaque-background", lambda im: im.paste((255, 255, 255, 255), (0, 0, *im.size)), "no transparent pixels"),
    ("wrong-palette", lambda im: im.putdata([(255, 0, 0, a) if a else (0, 0, 0, 0) for *_, a in im.getdata()]),
     "differs from the light/normal token"),
    ("clipped-edge", lambda im: im.putpixel((0, 5), (51, 65, 85, 255)), "touches the canvas edge"),
    ("empty", lambda im: im.putdata([(0, 0, 0, 0)] * (im.width * im.height)), "fully transparent"),
])
def test_at14_post_export_detects_bad_pngs(exported, name, edit, expected):
    rel = "exports/desktop/light/normal/24/pump.png"
    tamper(exported, rel, png_bytes(exported / rel, edit))
    code, errors = errors_for(exported, "pump")
    assert code == 4 and any(expected in e for e in errors), errors
    assert state(exported)["stage"] == "NEEDS_REVIEW" and "pump" in state(exported)["recovery_action"]


def test_at14_wrong_size_and_wrong_icon_content_are_detected(exported):
    rel = "exports/desktop/light/normal/24/pump.png"
    tamper(exported, rel, (exported / "exports/desktop/light/normal/24/valve.png").read_bytes())
    code, errors = errors_for(exported, "pump")
    assert code == 4 and any("pixels differ from a fresh render" in e for e in errors), "mapping check"
    shutil.copy(exported / "exports/desktop/light/normal/16/pump.png", exported / rel)
    tamper(exported, rel, (exported / "exports/desktop/light/normal/16/pump.png").read_bytes())
    assert any("expected 24x24" in e for e in errors_for(exported, "pump")[1])


def test_at14_missing_and_hand_edited_files_are_reported(exported):
    (exported / "exports/desktop/dark/disabled/16/save.png").unlink()
    (exported / "exports/web/network.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'/>")
    _, report = post_export(exported)
    assert any("missing export" in e for e in report["icons"]["save"]["errors"])
    assert any("changed after export" in e for e in report["icons"]["network"]["errors"])


def test_at14_stale_export_after_palette_change_is_flagged(exported):
    spec = json.loads((exported / "style-spec.json").read_text())
    spec["themes"]["light"]["normal"] = "#111827"
    (exported / "style-spec.json").write_text(json.dumps(spec))
    _, report = post_export(exported)
    assert any("stale export" in e for e in report["icons"]["pump"]["errors"])


# ------------------------------------------------------------------ AT-15

def test_at15_inline_profile_keeps_currentcolor_and_equals_the_master(exported):
    for icon_id in ("pump", "valve", "add"):
        inline = (exported / "exports" / "web" / f"{icon_id}.svg").read_bytes()
        assert inline == (exported / "masters" / f"{icon_id}.svg").read_bytes()
        assert b"currentColor" in inline


def test_at15_img_profile_has_resolved_colors_and_is_counted_separately(exportable):
    proc, out = run_json("export_assets.py", "--set", exportable, "--target", "web", "--web-img")
    assert proc.returncode == 0, proc.stderr
    assert out["planned"] == {"web-img": 40, "web-inline": 10}
    img = list((exportable / "exports" / "web" / "img").rglob("*.svg"))
    assert len(img) == 10 * 2 * 2 and not exported_png(exportable), "desktop was not requested"
    light = (exportable / "exports/web/img/light/normal/pump.svg").read_text()
    dark = (exportable / "exports/web/img/dark/disabled/pump.svg").read_text()
    assert "currentColor" not in light and "#334155" in light.upper()
    assert "#64748B" in dark.upper()
    inline = (exportable / "exports/web/pump.svg").read_text()
    assert "currentColor" in inline and inline != light
    assert post_export(exportable)[0].returncode == 4, "desktop outputs are still missing"


def test_at15_selected_scope_leaves_other_exports_alone(exported):
    before = tree(exported / "exports" / "desktop")
    proc, out = run_json("export_assets.py", "--set", exported, "--target", "web")
    assert proc.returncode == 0 and out["remove"] == []
    assert tree(exported / "exports" / "desktop") == before


# ------------------------------------------------------------------ AT-16

def test_at16_repeat_export_is_byte_identical_and_a_no_op(exported):
    before = tree(exported / "exports")
    refs_before = tree(exported.parent.parent / "references")
    proc, out = run_json("export_assets.py", "--set", exported)
    assert proc.returncode == 0
    assert len(out["unchanged"]) == 170 and out["create"] == [] and out["update"] == []
    assert tree(exported / "exports") == before
    assert tree(exported.parent.parent / "references") == refs_before, "original references are untouched"


def test_at16_two_independent_exports_produce_identical_bytes(exported, tmp_path, _exportable_template):
    other = tmp_path / "second" / "w"
    shutil.copytree(_exportable_template, other)
    other_set = other / "icon-work" / "scada-fixture"
    assert run_script("export_assets.py", "--set", other_set).returncode == 0
    assert tree(other_set / "exports") == tree(exported / "exports")


def test_at16_deleting_exports_and_rerunning_restores_identical_files(exported):
    before = tree(exported / "exports")
    shutil.rmtree(exported / "exports")
    assert run_script("export_assets.py", "--set", exported).returncode == 0
    assert tree(exported / "exports") == before


def test_payloads_carry_no_volatile_data(exported):
    text = (exported / "exports/web/pump.svg").read_text()
    assert "202" not in text and "generated" not in text.lower()
    assert b"tEXt" not in (exported / "exports/desktop/light/normal/16/pump.png").read_bytes()


# ------------------------------------------------------------------ AT-20

def test_at20_hand_edited_export_is_reported_and_nothing_changes(exported):
    target = exported / "exports/desktop/light/normal/24/pump.png"
    target.write_bytes(b"manual edit")
    before = tree(exported)
    proc, out = run_json("export_assets.py", "--set", exported)
    assert proc.returncode == 4
    assert "exports/desktop/light/normal/24/pump.png (export was changed by hand)" in proc.stderr
    assert tree(exported) == before, "no silent overwrite, no other change"


def test_at20_unmanaged_file_at_a_planned_path_is_a_conflict(exportable):
    clash = exportable / "exports/web/pump.svg"
    clash.parent.mkdir(parents=True)
    clash.write_text("mine")
    proc = run_script("export_assets.py", "--set", exportable)
    assert proc.returncode == 4 and "unmanaged file at a planned path" in proc.stderr
    assert clash.read_text() == "mine"


def test_at20_unknown_files_elsewhere_are_reported_not_deleted(exported):
    extra = exported / "exports" / "notes.txt"
    extra.write_text("keep me")
    proc, out = run_json("export_assets.py", "--set", exported)
    assert proc.returncode == 0 and out["unknown"] == ["exports/notes.txt"]
    assert extra.read_text() == "keep me"
    _, report = post_export(exported)
    assert report["unknown_files"] == ["exports/notes.txt"]


def test_at20_explicit_overwrite_moves_the_original_aside(exported):
    target = exported / "exports/desktop/light/normal/24/pump.png"
    good = hashlib.sha256(target.read_bytes()).hexdigest()
    target.write_bytes(b"manual edit")
    proc, out = run_json("export_assets.py", "--set", exported, "--resolve", "overwrite")
    assert proc.returncode == 0, proc.stderr
    assert hashlib.sha256(target.read_bytes()).hexdigest() == good
    kept = list((exported / "exports" / ".conflicts").rglob("pump.png.*"))
    assert len(kept) == 1 and kept[0].read_bytes() == b"manual edit"
    assert post_export(exported)[0].returncode == 0


def test_at20_changed_by_hand_and_no_longer_planned_is_a_conflict(exported):
    (exported / "exports/desktop/light/normal/20/add.png").write_bytes(b"hand")
    inv = json.loads((exported / "inventory.json").read_text())
    next(i for i in inv["icons"] if i["id"] == "add")["sizes_px"] = [16, 24, 32]
    (exported / "inventory.json").write_text(json.dumps(inv))
    run_script("invalidate.py", "detect", "--set", exported, "--apply")
    proc = run_script("export_assets.py", "--set", exported)
    assert proc.returncode == 4 and "no longer planned but changed by hand" in proc.stderr
    assert (exported / "exports/desktop/light/normal/20/add.png").read_bytes() == b"hand"


# ------------------------------------------------------- eligibility & safety

def test_only_eligible_icons_are_exported_and_rejected_ones_stay_out(exportable):
    assert run_script("manifest.py", "reject", "--set", exportable, "--ids", "pump", "--reviewer", "user").returncode == 0
    proc, out = run_json("export_assets.py", "--set", exportable)
    assert proc.returncode == 0, proc.stderr
    assert [s["id"] for s in out["skipped"]] == ["pump"] and "not export-eligible" in out["skipped"][0]["reason"]
    assert not list((exportable / "exports").rglob("pump*"))
    assert len(exported_png(exportable)) == 9 * 16
    assert state(exportable)["stage"] != "EXPORTED", "an incomplete set is not reported as exported"
    assert post_export(exportable)[0].returncode == 0, "eligible icons are fine"
    assert state(exportable)["stage"] != "ASSETS_READY"


def test_changing_a_pilot_icon_after_approval_closes_the_export_gate(exportable):
    master = exportable / "masters" / "pump.svg"
    master.write_text(master.read_text().replace("M5 21h12", "M5 20h12"))
    assert run_script("export_assets.py", "--set", exportable).returncode == 4, "drift must be processed first"
    assert run_script("invalidate.py", "detect", "--set", exportable, "--apply").returncode == 0
    proc = run_script("export_assets.py", "--set", exportable)
    assert proc.returncode == 4 and "pilot approval gate closed" in proc.stderr and "pump" in proc.stderr
    assert not (exportable / "exports").exists()


def test_export_is_blocked_while_style_drift_is_unprocessed(exportable):
    spec = json.loads((exportable / "style-spec.json").read_text())
    spec["themes"]["dark"]["normal"] = "#CBD5E1"
    (exportable / "style-spec.json").write_text(json.dumps(spec))
    proc = run_script("export_assets.py", "--set", exportable)
    assert proc.returncode == 4 and "drift detected (palette)" in proc.stderr
    assert not (exportable / "exports").exists()


def test_missing_renderer_exits_with_dependency_code(exportable):
    import os
    env = {**os.environ, "PATH": "/nonexistent"}
    proc = run_script("export_assets.py", "--set", exportable, env=env)
    assert proc.returncode == 3 and "resvg not found" in proc.stderr and "cargo install resvg" in proc.stderr


def test_interrupted_commit_is_recovered_through_the_journal(exportable):
    with pytest.raises(RuntimeError, match="simulated crash"):
        export_assets.export(exportable, _fail_after=25)
    assert (exportable / "exports" / ".journal.json").exists(), "recovery journal is retained"
    partial = len([p for p in (exportable / "exports").rglob("*") if p.is_file() and ".staging" not in p.parts])
    assert 0 < partial < 171
    proc, out = run_json("export_assets.py", "--set", exportable)
    assert proc.returncode == 0, proc.stderr
    assert out["recovered"]["recovered_operations"] == 170
    assert not (exportable / "exports" / ".journal.json").exists()
    assert not (exportable / "exports" / ".staging").exists()
    assert len(exported_png(exportable)) == 160
    assert post_export(exportable)[0].returncode == 0
    reference = tree(exportable / "exports")
    shutil.rmtree(exportable / "exports")
    run_script("export_assets.py", "--set", exportable)
    assert tree(exportable / "exports") == reference, "recovered files equal a clean export"


def test_export_makes_no_network_or_llm_calls():
    source = (SCRIPTS / "export_assets.py").read_text()
    for banned in ("anthropic", "openai", "urllib", "requests", "socket", "http.client"):
        assert banned not in source
