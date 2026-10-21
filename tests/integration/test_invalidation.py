"""AT-18: only affected outputs and reviews are invalidated; stale approvals are never accepted."""
from __future__ import annotations

import hashlib
import json

import pytest

from conftest import ROOT, approve_set, run_json, run_script

FAKE = hashlib.sha256(b"x").hexdigest()


def export_entry(kind, icon_id, theme="light", state="normal", size=16):
    path = f"exports/desktop/{theme}/{state}/{size}/{icon_id}.png" if kind == "desktop-png" \
        else f"exports/web/{icon_id}.svg"
    return {"kind": kind, "path": path, "sha256": FAKE, "source_sha256": FAKE, "config_sha256": FAKE,
            **({"theme": theme, "state": state, "size_px": size} if kind == "desktop-png" else {})}


@pytest.fixture
def approved(pilot_set, tmp_path):
    """Pilot approved, source QA passed, fake exports and an application record attached to every icon."""
    approve_set(pilot_set, tmp_path)
    assert run_script("validate_icons.py", "--set", pilot_set, "--phase", "source", "--project-root", ROOT).returncode == 0
    import manifest
    ids = [i["id"] for i in manifest.load(pilot_set)["icons"]]
    manifest.set_exports(pilot_set, {i: [export_entry("desktop-png", i), export_entry("web-inline", i)] for i in ids})
    (pilot_set / "reports").mkdir(exist_ok=True)
    (pilot_set / "reports" / "application-validation.json").write_text(json.dumps({
        "schema_version": "1.0", "set_id": "scada-fixture", "overall": "APPLICATION_VALIDATED", "contexts": [
            {"context": "desktop-toolbar", "platform": "desktop", "status": "passed", "reason": "checked",
             "environment": {"app": "demo"}, "icon_ids": ["add", "save"], "exported_hashes": {"add": FAKE},
             "evidence": "shots/toolbar.png"},
            {"context": "desktop-menu", "platform": "desktop", "status": "passed", "reason": "checked",
             "environment": {"app": "demo"}, "icon_ids": ["pump"], "exported_hashes": {"pump": FAKE},
             "evidence": "shots/menu.png"}]}))
    return pilot_set


def load_manifest(set_dir):
    return {i["id"]: i for i in json.loads((set_dir / "manifest.json").read_text())["icons"]}


def app_status(set_dir):
    data = json.loads((set_dir / "reports" / "application-validation.json").read_text())
    return {c["context"]: c["status"] for c in data["contexts"]}, data["overall"]


def test_baseline_has_no_drift(approved):
    proc, out = run_json("invalidate.py", "detect", "--set", approved)
    assert proc.returncode == 0 and out["changes"] == []
    assert all(i["status"] == "eligible" and len(i["exports"]) == 2 for i in load_manifest(approved).values())


def test_at18_palette_only_keeps_geometry_approval_but_resets_outputs(approved):
    before_hashes = {i["id"]: i["master_sha256"] for i in load_manifest(approved).values()}
    spec = json.loads((approved / "style-spec.json").read_text())
    spec["themes"]["dark"]["normal"] = "#CBD5E1"
    (approved / "style-spec.json").write_text(json.dumps(spec))

    assert run_script("approvals.py", "check", "--set", approved).returncode == 0, \
        "a palette change does not make the geometry approval stale"
    proc, out = run_json("invalidate.py", "detect", "--set", approved)
    assert out["changes"] == [{"change": "palette", "ids": None}]
    proc, out = run_json("invalidate.py", "detect", "--set", approved, "--apply")
    assert proc.returncode == 0
    icons = load_manifest(approved)
    assert all(i["exports"] == [] for i in icons.values())
    assert all(i["qa"]["visual"] == "approved" and i["qa"]["structural"] == "passed" for i in icons.values())
    assert all(i["qa"]["color_review"] == "pending" for i in icons.values())
    assert {i: e["master_sha256"] for i, e in icons.items()} == before_hashes, "geometry is untouched"
    contexts, overall = app_status(approved)
    assert set(contexts.values()) == {"not-tested"} and overall == "ASSETS_READY"
    assert run_json("invalidate.py", "detect", "--set", approved)[1]["changes"] == [], "drift is consumed once"


def test_at18_geometry_change_resets_only_that_icon(approved):
    master = approved / "masters" / "pump.svg"
    master.write_text(master.read_text().replace("M5 21h12", "M5 20h12"))
    proc, out = run_json("invalidate.py", "detect", "--set", approved)
    assert out["changes"] == [{"change": "geometry", "ids": ["pump"]}]
    stale = run_json("approvals.py", "check", "--set", approved)
    assert stale[0].returncode == 4 and stale[1]["stale"] == ["pump"], "stale approval rejected"

    run_json("invalidate.py", "detect", "--set", approved, "--apply")
    icons = load_manifest(approved)
    assert icons["pump"]["status"] == "pending" and icons["pump"]["exports"] == []
    assert icons["pump"]["qa"]["visual"] == "pending" and icons["pump"]["qa"]["structural"] == "pending"
    for other in ("add", "save", "valve"):
        assert icons[other]["status"] == "eligible" and len(icons[other]["exports"]) == 2
    contexts, _ = app_status(approved)
    assert contexts == {"desktop-toolbar": "passed", "desktop-menu": "not-tested"}


def test_at18_style_change_makes_pilot_approval_stale_and_resets_everything(approved):
    spec = json.loads((approved / "style-spec.json").read_text())
    spec["stroke_width"] = 2
    (approved / "style-spec.json").write_text(json.dumps(spec))
    stale = run_json("approvals.py", "check", "--set", approved)
    assert stale[0].returncode == 4 and "style" in stale[1]["stale"]
    run_json("invalidate.py", "detect", "--set", approved, "--apply")
    icons = load_manifest(approved)
    assert all(i["status"] == "pending" and i["exports"] == [] for i in icons.values())
    assert json.loads((approved / "run-state.json").read_text())["stage"] == "PILOT_READY"
    assert app_status(approved)[0] == {"desktop-toolbar": "not-tested", "desktop-menu": "not-tested"}
    # the old approval does not come back after sync
    run_script("manifest.py", "sync", "--set", approved)
    assert all(i["qa"]["visual"] == "pending" for i in load_manifest(approved).values())


def test_at18_reference_change_voids_review_even_though_hashes_match(approved):
    inv = json.loads((approved / "inventory.json").read_text())
    next(i for i in inv["icons"] if i["id"] == "network")["references"][0]["sha256"] = FAKE
    (approved / "inventory.json").write_text(json.dumps(inv))
    assert run_json("invalidate.py", "detect", "--set", approved)[1]["changes"] == \
        [{"change": "reference", "ids": ["network"]}]
    run_json("invalidate.py", "detect", "--set", approved, "--apply")
    icons = load_manifest(approved)
    assert icons["network"]["qa"]["visual"] == "pending" and icons["network"]["status"] == "pending"
    assert icons["pump"]["status"] == "eligible"
    run_script("manifest.py", "sync", "--set", approved)
    assert load_manifest(approved)["network"]["qa"]["visual"] == "pending", "void survives sync"


def test_at18_review_after_a_void_is_accepted_again(approved, tmp_path):
    run_json("invalidate.py", "apply", "--set", approved, "--change", "reference", "--ids", "network")
    assert load_manifest(approved)["network"]["status"] == "pending"
    approve_set(approved, tmp_path, kind="batch", ids=["network"])
    assert load_manifest(approved)["network"]["qa"]["visual"] == "approved"
    assert load_manifest(approved)["network"]["status"] == "eligible"


def test_at18_renderer_change_clears_only_raster_outputs(approved):
    manifest_path = approved / "manifest.json"
    data = json.loads(manifest_path.read_text())
    data["toolchain"]["renderer_version"] = "0.0.1"
    manifest_path.write_text(json.dumps(data))
    assert run_json("invalidate.py", "detect", "--set", approved)[1]["changes"] == [{"change": "renderer", "ids": None}]
    run_json("invalidate.py", "detect", "--set", approved, "--apply")
    icons = load_manifest(approved)
    assert all([e["kind"] for e in i["exports"]] == ["web-inline"] for i in icons.values())
    assert all(i["status"] == "eligible" for i in icons.values()), "review of geometry stays valid"


def test_at18_usage_change_resets_affected_icon_outputs(approved):
    inv = json.loads((approved / "inventory.json").read_text())
    next(i for i in inv["icons"] if i["id"] == "add")["sizes_px"] = [16, 24]
    (approved / "inventory.json").write_text(json.dumps(inv))
    assert run_json("invalidate.py", "detect", "--set", approved)[1]["changes"] == [{"change": "usage", "ids": ["add"]}]
    run_json("invalidate.py", "detect", "--set", approved, "--apply")
    icons = load_manifest(approved)
    assert icons["add"]["exports"] == [] and len(icons["pump"]["exports"]) == 2
    assert app_status(approved)[0]["desktop-toolbar"] == "not-tested"
    assert app_status(approved)[0]["desktop-menu"] == "passed"


def test_at18_history_is_appended_never_rewritten(approved):
    run_json("invalidate.py", "apply", "--set", approved, "--change", "usage", "--ids", "add", "--reason", "first")
    run_json("invalidate.py", "apply", "--set", approved, "--change", "usage", "--ids", "save", "--reason", "second")
    lines = (approved / "reports" / "invalidation-log.jsonl").read_text().splitlines()
    assert len(lines) == 2 and '"first"' in lines[0] and '"second"' in lines[1]


def test_apply_rejects_unknown_ids_and_changes(approved):
    bad = run_script("invalidate.py", "apply", "--set", approved, "--change", "usage", "--ids", "nope")
    assert bad.returncode == 2 and "no manifest entry for: nope" in bad.stderr
    assert run_script("invalidate.py", "apply", "--set", approved, "--change", "bogus").returncode == 2
