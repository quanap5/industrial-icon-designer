"""AT-11 (invalid or clipped source), the structural part of AT-19, manifest eligibility."""
from __future__ import annotations

import json
import os
import shutil

import pytest

from conftest import ROOT, approve_set, run_json, run_script

SVG_HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' \
           'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'


def validate(set_dir, *extra):
    return run_json("validate_icons.py", "--set", set_dir, "--phase", "source", "--project-root", ROOT, *extra)


def manifest(set_dir):
    return {i["id"]: i for i in json.loads((set_dir / "manifest.json").read_text())["icons"]}


def test_clean_masters_pass_source_qa(pilot_set):
    proc, report = validate(pilot_set)
    assert proc.returncode == 0, proc.stderr
    assert report["summary"] == {"checked": 10, "passed": 10, "failed": 0}
    assert report["contrast"]["passes"] is True and report["blocked"] is None
    icons = manifest(pilot_set)
    assert all(i["qa"]["structural"] == "passed" and i["status"] == "pending" for i in icons.values()), \
        "structurally fine but not yet visually approved"


BROKEN = {
    "script": (SVG_HEAD + "<path d='M4 12h16'/><script>alert(1)</script></svg>", "forbidden element <script>"),
    "raster": (SVG_HEAD + "<image href='data:image/png;base64,AAAA'/></svg>", "embedded raster"),
    "fixed-color": (SVG_HEAD + "<path d='M4 12h16' stroke='#ff0000'/></svg>", "fixed stroke color"),
    "inline-style": (SVG_HEAD + "<path d='M4 12h16' style='stroke:#00f'/></svg>", "inline style sets fill/stroke"),
    "empty": (SVG_HEAD + "</svg>", "empty geometry"),
    "wrong-viewbox": (SVG_HEAD.replace("0 0 24 24", "0 0 32 32") + "<path d='M4 12h16'/></svg>", "viewBox must be"),
    "sized": (SVG_HEAD.replace("<svg ", '<svg width="24" height="24" ') + "<path d='M4 12h16'/></svg>",
              "width attribute set"),
    "clipped": (SVG_HEAD + "<path d='M-6 12h36'/></svg>", "consistency:"),
    "entity": ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "x">]>' + SVG_HEAD + "<path d='M4 12h16'/></svg>",
               "unsafe XML construct"),
    "external-ref": (SVG_HEAD + "<use href='http://example.com/a.svg#x'/></svg>", "external href"),
    "malformed": ("<svg><path", "not well-formed"),
}


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_at11_invalid_master_fails_with_affected_id_and_is_not_eligible(pilot_set, tmp_path, name):
    text, expected = BROKEN[name]
    (pilot_set / "masters" / "pump.svg").write_text(text)
    approve_set(pilot_set, tmp_path, ids=[i for i in json.loads((pilot_set / "brief.json").read_text())["sample_ids"]
                                          if i != "pump"])
    proc, report = validate(pilot_set)
    assert proc.returncode == 4, proc.stderr
    pump = report["icons"]["pump"]
    assert pump["status"] == "failed" and any(expected in e for e in pump["errors"]), pump["errors"]
    assert f"error: pump:" in proc.stderr, "the affected id appears in the diagnostics"
    assert report["icons"]["save"]["status"] == "passed", "other icons are unaffected"
    pump_entry = manifest(pilot_set)["pump"]
    assert pump_entry["qa"]["structural"] == "failed" and pump_entry["status"] == "rejected"
    state = json.loads((pilot_set / "run-state.json").read_text())
    assert state["stage"] == "NEEDS_REVIEW" and "pump" in state["recovery_action"]
    assert state["last_valid_stage"] != "NEEDS_REVIEW", "the last valid stage is preserved"


def test_orphan_master_without_inventory_entry_is_rejected(pilot_set):
    shutil.copy(pilot_set / "masters" / "pump.svg", pilot_set / "masters" / "ghost.svg")
    proc, report = validate(pilot_set)
    assert proc.returncode == 4
    assert any("no inventory entry" in e for e in report["icons"]["ghost"]["errors"])


def test_at19_master_symlink_outside_the_set_is_rejected(pilot_set, tmp_path):
    outside = tmp_path / "outside.svg"
    shutil.copy(pilot_set / "masters" / "pump.svg", outside)
    (pilot_set / "masters" / "pump.svg").unlink()
    os.symlink(outside, pilot_set / "masters" / "pump.svg")
    proc, report = validate(pilot_set)
    assert proc.returncode == 4
    assert any("outside the set directory" in e for e in report["icons"]["pump"]["errors"])


def test_failed_icon_recovers_when_fixed(pilot_set):
    good = (pilot_set / "masters" / "pump.svg").read_text()
    (pilot_set / "masters" / "pump.svg").write_text(SVG_HEAD + "</svg>")
    assert validate(pilot_set)[0].returncode == 4
    (pilot_set / "masters" / "pump.svg").write_text(good)
    proc, report = validate(pilot_set)
    assert proc.returncode == 0 and report["summary"]["failed"] == 0
    assert manifest(pilot_set)["pump"]["qa"]["structural"] == "passed"


def test_blocked_dependency_stops_the_check_and_nothing_becomes_eligible(pilot_set, project_root, tmp_path):
    gen = project_root / ".claude" / "skills" / "icon-set-generator" / "SKILL.md"
    gen.write_text(gen.read_text() + "\n<!-- changed -->\n")
    approve_set(pilot_set, tmp_path)
    proc, report = run_json("validate_icons.py", "--set", pilot_set, "--phase", "source",
                            "--project-root", project_root)
    assert proc.returncode == 3 and "differ from the lock" in report["blocked"]
    assert all(i["status"] != "eligible" for i in manifest(pilot_set).values())
    assert all(i["qa"]["structural"] != "passed" for i in manifest(pilot_set).values())


def test_eligibility_needs_structural_pass_and_current_visual_approval(pilot_set, tmp_path):
    ids = approve_set(pilot_set, tmp_path)
    before = manifest(pilot_set)
    assert all(i["qa"]["visual"] == "approved" and i["status"] == "pending" for i in before.values())
    assert validate(pilot_set)[0].returncode == 0
    after = manifest(pilot_set)
    assert all(after[i]["status"] == "eligible" for i in ids)
    assert after["pump"]["qa"]["reviewer_type"] == "user"

    master = pilot_set / "masters" / "pump.svg"
    master.write_text(master.read_text().replace("M5 21h12", "M5 20h12"))
    proc = run_script("manifest.py", "sync", "--set", pilot_set)
    assert proc.returncode == 0
    changed = manifest(pilot_set)["pump"]
    assert changed["status"] == "pending" and changed["qa"]["visual"] == "pending"
    assert changed["qa"]["structural"] == "pending" and changed["exports"] == []
    log = (pilot_set / "reports" / "invalidation-log.jsonl").read_text()
    assert '"kind": "geometry"' in log and "pump" in log


def test_rejected_visual_review_blocks_eligibility_until_the_asset_changes(pilot_set, tmp_path):
    approve_set(pilot_set, tmp_path)
    assert validate(pilot_set)[0].returncode == 0
    assert run_script("manifest.py", "reject", "--set", pilot_set, "--ids", "valve", "--reviewer", "user").returncode == 0
    assert manifest(pilot_set)["valve"]["status"] == "rejected"
    run_script("manifest.py", "sync", "--set", pilot_set)
    assert manifest(pilot_set)["valve"]["status"] == "rejected", "sync does not resurrect a rejected review"
    valve = pilot_set / "masters" / "valve.svg"
    valve.write_text(valve.read_text().replace("M8 5h8", "M9 5h6"))
    run_script("manifest.py", "sync", "--set", pilot_set)
    assert manifest(pilot_set)["valve"]["status"] == "pending"
