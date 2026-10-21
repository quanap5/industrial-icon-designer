"""AT-03 (inventory), AT-05 (ambiguous), AT-21 (space/Unicode) and the inventory part of AT-19."""
from __future__ import annotations

import json
import os
import shutil

from conftest import FIXTURES, run_json, run_script
from common import sha256_file

TEN = {"save", "open-folder", "settings", "add", "alarm-list", "trend-chart", "pump", "valve",
       "device-connect", "network"}


def load(set_dir):
    return json.loads((set_dir / "inventory.json").read_text())


def test_at03_inventory_preserves_metadata_and_leaves_sources_untouched(tmp_path, refs10):
    before = {p.name: sha256_file(p) for p in refs10.iterdir()}
    set_dir = tmp_path / "set"
    proc, out = run_json("inventory_icons.py", "--input", refs10, "--set", set_dir)
    assert proc.returncode == 0, proc.stderr
    inv = load(set_dir)
    assert {i["id"] for i in inv["icons"]} == TEN
    assert inv["rejected"] == [] and inv["unresolved"] == []
    pump = next(i for i in inv["icons"] if i["id"] == "pump")
    assert pump["meaning"] == "Pump equipment"
    assert pump["functional_group"] == "devices-connectivity" and pump["semantic_role"] == "object"
    assert pump["usage_locations"] == ["device-list"] and pump["sizes_px"] == [16, 20, 24, 32]
    assert pump["references"][0]["sha256"] == before["pump.png"]
    connect = next(i for i in inv["icons"] if i["id"] == "device-connect")
    assert connect["semantic_role"] == "action", "action and state must stay distinct"
    assert {p.name: sha256_file(p) for p in refs10.iterdir()} == before
    assert (set_dir / "run-state.json").exists()


def test_inventory_prefers_svg_when_png_and_svg_exist(inventoried):
    valve = next(i for i in load(inventoried)["icons"] if i["id"] == "valve")
    assert [r["kind"] for r in valve["references"]] == ["svg", "png"]
    assert valve["source_path"].endswith("valve.svg")
    assert "SVG used for geometry" in valve["notes"]


def test_inventory_reads_csv_metadata(tmp_path, refs10):
    set_dir = tmp_path / "csv-set"
    proc = run_script("inventory_icons.py", "--input", refs10, "--metadata", FIXTURES / "metadata.csv",
                      "--set", set_dir)
    assert proc.returncode == 0, proc.stderr
    add = next(i for i in load(set_dir)["icons"] if i["id"] == "add")
    assert add["usage_locations"] == ["toolbar", "device-list", "web-actions"]
    assert add["sizes_px"] == [16, 20, 24, 32]


def test_at05_ambiguous_icon_needs_review_and_is_not_approved(tmp_path):
    set_dir = tmp_path / "amb"
    proc = run_script("inventory_icons.py", "--input", FIXTURES / "references",
                      "--metadata", FIXTURES / "metadata.json", "--set", set_dir)
    assert proc.returncode == 0, proc.stderr
    inv = load(set_dir)
    mystery = next(i for i in inv["icons"] if i["id"] == "mystery-glyph")
    assert mystery["status"] == "NEEDS_REVIEW"
    assert mystery["inferred"]["meaning"]["confidence"] == "low"
    assert "mystery-glyph" in inv["unresolved"]
    assert all(i["status"] == "INVENTORIED" for i in inv["icons"] if i["id"] != "mystery-glyph")


def test_at21_space_and_unicode_paths(tmp_path, refs10):
    odd = tmp_path / "références pünkt 图标"
    shutil.copytree(refs10, odd)
    set_dir = tmp_path / "ensemble d'icônes"
    proc = run_script("inventory_icons.py", "--input", odd, "--set", set_dir)
    assert proc.returncode == 0, proc.stderr
    assert len(load(set_dir)["icons"]) == 10


# ------------------------------------------------------------ hostile input

SCRIPT_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><script>alert(1)</script></svg>'
ENTITY_SVG = ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
              '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><text>&b;</text></svg>')
EXTERNAL_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                'viewBox="0 0 24 24"><use xlink:href="http://example.com/x.svg#a"/></svg>')
RASTER_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
              '<image href="data:image/png;base64,AAAA"/></svg>')


def reject_reasons(set_dir):
    return {r["path"].split("/")[-1]: r["reason"] for r in load(set_dir)["rejected"]}


def test_at19_hostile_inputs_are_rejected_with_per_file_reasons(tmp_path):
    src = tmp_path / "hostile"
    src.mkdir()
    (src / "script.svg").write_text(SCRIPT_SVG)
    (src / "entity.svg").write_text(ENTITY_SVG)
    (src / "external.svg").write_text(EXTERNAL_SVG)
    (src / "raster.svg").write_text(RASTER_SVG)
    (src / "broken.png").write_bytes(b"not a png")
    shutil.copy(FIXTURES / "references" / "add.png", src / "good.png")
    outside = tmp_path / "outside.png"
    shutil.copy(FIXTURES / "references" / "add.png", outside)
    os.symlink(outside, src / "escape.png")
    set_dir = tmp_path / "set"

    proc = run_script("inventory_icons.py", "--input", src, "--set", set_dir)
    assert proc.returncode == 4, "rejections must be reported through exit code 4"
    reasons = reject_reasons(set_dir)
    assert "forbidden element <script>" in reasons["script.svg"]
    assert "unsafe XML construct" in reasons["entity.svg"]
    assert "external href" in reasons["external.svg"]
    assert "embedded raster" in reasons["raster.svg"]
    assert "unreadable PNG" in reasons["broken.png"]
    assert "outside the input root" in reasons["escape.png"]
    assert [i["id"] for i in load(set_dir)["icons"]] == ["good"], "only safe inputs enter the inventory"
    assert not (tmp_path / "out-of-root.txt").exists()


def test_inventory_rejects_case_insensitive_id_collisions(tmp_path):
    src = tmp_path / "collide"
    src.mkdir()
    shutil.copy(FIXTURES / "references" / "add.png", src / "Add.png")
    (src / "sub").mkdir()
    shutil.copy(FIXTURES / "references" / "add.png", src / "sub" / "add.png")
    proc = run_script("inventory_icons.py", "--input", src, "--set", tmp_path / "set")
    assert proc.returncode == 4
    reasons = load(tmp_path / "set")["rejected"]
    assert len(reasons) == 1 and "collides" in reasons[0]["reason"]


def test_guardrails_report_limit_and_config_path(tmp_path):
    src = tmp_path / "big"
    src.mkdir()
    shutil.copy(FIXTURES / "references" / "add.png", src / "add.png")
    set_dir = tmp_path / "set"
    set_dir.mkdir()
    (set_dir / "guardrails.json").write_text(json.dumps({"max_input_bytes": 10}))
    proc = run_script("inventory_icons.py", "--input", src, "--set", set_dir)
    assert proc.returncode == 4
    reason = load(set_dir)["rejected"][0]["reason"]
    assert "max_input_bytes" in reason and "guardrails.json" in reason

    (set_dir / "guardrails.json").write_text(json.dumps({"max_icons_per_run": 0}))
    proc = run_script("inventory_icons.py", "--input", src, "--set", set_dir)
    assert proc.returncode == 2
    assert "max_icons_per_run" in proc.stderr and "guardrails.json" in proc.stderr


def test_doctor_validates_inventory_against_schema(inventoried):
    proc, data = run_json("doctor.py", "--set", inventoried)
    set_checks = [c for c in data["checks"] if c["name"] == "set"]
    assert {c["detail"] for c in set_checks} >= {"inventory.json valid", "run-state.json valid"}
    inv = json.loads((inventoried / "inventory.json").read_text())
    inv["icons"][0]["id"] = "Bad_ID"
    (inventoried / "inventory.json").write_text(json.dumps(inv))
    proc, data = run_json("doctor.py", "--set", inventoried)
    assert proc.returncode in (3, 4)
    assert any(c["name"] == "set" and c["status"] == "fail" and "icons/0/id" in c["detail"] for c in data["checks"])
