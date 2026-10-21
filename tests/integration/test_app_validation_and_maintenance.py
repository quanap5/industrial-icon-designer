"""AT-22 (Desktop validation), AT-23 (Web validation), AT-24 (no application access), AT-25 (maintenance)."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from conftest import FIXTURES, ROOT, approve_set, run_json, run_script

import app_validation

DESKTOP = ["desktop-toolbar", "desktop-ribbon", "desktop-menu", "desktop-device-list"]
WEB = ["web-navigation", "web-actions", "web-list"]


def tree(path: Path) -> dict[str, str]:
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file()}


@pytest.fixture
def ready(exported):
    """All ten icons exported and post-export QA passed (ASSETS_READY); application records initialised."""
    assert run_script("validate_icons.py", "--set", exported, "--phase", "exported").returncode == 0
    assert run_script("app_validation.py", "init", "--set", exported).returncode == 0
    return exported


def record(set_dir, ctx, status="passed", icons=None, **override):
    platform = "desktop" if ctx.startswith("desktop") else "web"
    ids = icons or app_validation.expected_icons(set_dir, ctx) or ["add"]
    env = ["framework=DevExpress 15.1.11", "control=RibbonControl"] if platform == "desktop" else ["browser=Chrome 130"]
    args = ["app_validation.py", "record", "--set", set_dir, "--context", ctx, "--status", status,
            "--reason", "checked in the real application", "--env", *env, "--icons", ",".join(ids),
            "--evidence", f"evidence/{ctx}.png", "--themes", "dark,light", "--states", "disabled,normal"]
    if platform == "desktop":
        args += ["--scaling", "100,125,150,200"]
    for key, value in override.items():
        idx = args.index(f"--{key}")
        if value is None:  # drop the flag together with its value
            del args[idx:idx + 2]
        else:
            args[idx + 1] = value
    return run_script(*args)


def evaluate(set_dir, *extra):
    return run_json("app_validation.py", "evaluate", "--set", set_dir, *extra)


def stage(set_dir):
    return json.loads((set_dir / "run-state.json").read_text())["stage"]


# ------------------------------------------------------------------ AT-24

def test_at24_without_application_access_the_set_is_assets_ready(ready):
    proc, out = evaluate(ready)
    assert proc.returncode == 0
    assert out["overall"] == "ASSETS_READY" and out["application_validated"] is False
    assert len(out["not_tested"]) == 7 and out["failed"] == []
    assert "APPLICATION_VALIDATED is not claimed" in out["message"]
    assert stage(ready) == "ASSETS_READY"
    data = json.loads((ready / "reports" / "application-validation.json").read_text())
    assert {c["status"] for c in data["contexts"]} == {"not-tested"} and data["overall"] == "ASSETS_READY"


def test_at24_a_simulation_is_never_recorded_as_a_test(ready):
    proc = run_script("app_validation.py", "record", "--set", ready, "--context", "web-navigation",
                      "--status", "passed", "--reason", "looked at preview", "--simulation")
    assert proc.returncode == 2 and "simulation is not the actual application" in proc.stderr
    assert evaluate(ready)[1]["application_validated"] is False


def test_at24_checklist_lists_every_required_context(ready):
    proc, out = run_json("app_validation.py", "checklist", "--set", ready)
    text = Path(out["checklist"]).read_text()
    for ctx in DESKTOP + WEB:
        assert f"## {ctx}" in text
    assert "100%, 125%, 150%, 200%" in text and "browser and version" in text.lower()
    assert "simulation or preview does not count" in text


# ------------------------------------------------------------------ AT-22

@pytest.mark.parametrize("override,message", [
    ({"scaling": "100,125"}, "display scaling 100,125,150,200"),
    ({"themes": "light"}, "every theme"),
    ({"states": "normal"}, "every supported state"),
    ({"evidence": None}, "evidence"),
])
def test_at22_desktop_pass_needs_full_coverage(ready, override, message):
    proc = record(ready, "desktop-toolbar", **override)
    assert proc.returncode == 2 and message in proc.stderr
    assert evaluate(ready)[1]["overall"] == "ASSETS_READY"


def test_at22_desktop_needs_framework_and_exported_icons(ready):
    proc = run_script("app_validation.py", "record", "--set", ready, "--context", "desktop-menu", "--status",
                      "passed", "--reason", "ok", "--env", "app=demo", "--icons", "save,network,open-folder",
                      "--evidence", "x", "--themes", "dark,light", "--states", "disabled,normal",
                      "--scaling", "100,125,150,200")
    assert proc.returncode == 2 and "environment key 'framework'" in proc.stderr
    bad = record(ready, "desktop-menu", icons=["ghost"])
    assert bad.returncode == 2 and "must be exported for this platform" in bad.stderr


def test_at22_failed_context_needs_review_and_partial_coverage_is_not_a_pass(ready):
    assert record(ready, "desktop-ribbon", "failed").returncode == 0
    out = evaluate(ready)[1]
    assert out["overall"] == "NEEDS_REVIEW" and out["failed"] == ["desktop-ribbon"]
    # a pass that skips an icon used in the context does not hold
    assert record(ready, "desktop-toolbar", icons=["save", "add"]).returncode == 0
    row = next(r for r in evaluate(ready)[1]["contexts"] if r["context"] == "desktop-toolbar")
    assert row["status"] == "not-tested" and "never tested" in row["reason"]


def test_at22_all_required_contexts_passing_validates_the_application(ready):
    for ctx in DESKTOP + WEB:
        assert record(ready, ctx).returncode == 0, ctx
    proc, out = evaluate(ready)
    assert out["overall"] == "APPLICATION_VALIDATED" and out["application_validated"] is True
    assert stage(ready) == "APPLICATION_VALIDATED"
    assert evaluate(ready, "--complete")[0].returncode == 0 and stage(ready) == "COMPLETE"


# ------------------------------------------------------------------ AT-23

def test_at23_web_pass_needs_browser_and_states(ready):
    proc = run_script("app_validation.py", "record", "--set", ready, "--context", "web-navigation", "--status",
                      "passed", "--reason", "ok", "--env", "os=Windows", "--icons", "settings",
                      "--evidence", "x", "--themes", "dark,light", "--states", "disabled,normal")
    assert proc.returncode == 2 and "environment key 'browser'" in proc.stderr
    assert record(ready, "web-navigation").returncode == 0
    data = json.loads((ready / "reports" / "application-validation.json").read_text())
    web = next(c for c in data["contexts"] if c["context"] == "web-navigation")
    assert web["environment"] == {"browser": "Chrome 130"} and web["themes"] == ["dark", "light"]
    assert "scaling_percent" not in web, "display scaling is a Desktop requirement"


def test_at23_stale_evidence_returns_to_not_tested(ready):
    for ctx in WEB:
        assert record(ready, ctx).returncode == 0
    manifest = json.loads((ready / "manifest.json").read_text())
    icon = next(i for i in manifest["icons"] if i["id"] == "network")
    next(e for e in icon["exports"] if e["kind"] == "web-inline")["sha256"] = "0" * 64
    (ready / "manifest.json").write_text(json.dumps(manifest))
    rows = {r["context"]: r for r in evaluate(ready)[1]["contexts"]}
    assert rows["web-navigation"]["status"] == "not-tested" and "stale evidence" in rows["web-navigation"]["reason"]
    assert rows["web-actions"]["status"] == "passed", "unaffected contexts stay valid"


def test_removing_a_context_needs_a_reason_and_is_never_counted_as_passed(ready):
    assert run_script("app_validation.py", "profile", "--set", ready, "--remove", "web-list").returncode == 2
    proc = run_script("app_validation.py", "profile", "--set", ready, "--remove", "web-list",
                      "--reason", "the product has no list view")
    assert proc.returncode == 0
    out = evaluate(ready)[1]
    assert out["required_contexts"] == 6 and "web-list" not in [r["context"] for r in out["contexts"]]
    brief = json.loads((ready / "brief.json").read_text())
    assert next(c for c in brief["required_contexts"] if c["id"] == "web-list")["removed_reason"]


# ------------------------------------------------------------------ AT-25

NEW_MASTER = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M5 13a6 6 0 1 0 12 0a6 6 0 0 0-12 0zM11 7V4h9M5 21h12M9 11h4v4H9z"/></svg>\n')


def dup(set_dir, new_id, meaning, *extra):
    return run_json("duplicate_check.py", "--set", set_dir, "--id", new_id, "--meaning", meaning, *extra)


def test_at25_duplicate_meaning_is_detected_before_adding(ready):
    proc, out = dup(ready, "Pump", "Anything")
    assert proc.returncode == 4 and out["duplicates"][0]["reason"].startswith("same id")
    proc, out = dup(ready, "water-pump", "Pump equipment", "--group", "devices-connectivity")
    assert proc.returncode == 4 and out["duplicates"][0]["id"] == "pump"
    assert dup(ready, "pump-stop", "Stop selected pump", "--group", "devices-connectivity", "--role", "action")[0] \
        .returncode == 0
    proc, out = dup(ready, "device-connected", "Device connected", "--role", "state")
    assert proc.returncode == 0, "an action and its resulting state are different icons"


def test_at25_extending_a_set_regenerates_only_what_is_new(ready, tmp_path):
    refs = ready.parent.parent / "references"
    assert record(ready, "desktop-device-list").returncode == 0
    row = next(r for r in evaluate(ready)[1]["contexts"] if r["context"] == "desktop-device-list")
    assert row["status"] == "passed"
    before = tree(ready / "exports")
    old_masters = tree(ready / "masters")

    # 1. a new icon is described and re-inventoried (progress is kept)
    meta = json.loads((refs / "metadata.json").read_text())
    meta["icons"].append({"id": "pump-stop", "meaning": "Stop selected pump", "usage_locations": ["toolbar", "device-list"],
                          "sizes_px": [16, 20, 24, 32], "functional_group": "devices-connectivity",
                          "semantic_role": "action", "notes": "synthetic fixture"})
    (refs / "metadata.json").write_text(json.dumps(meta))
    shutil.copy(FIXTURES / "references" / "pump.png", refs / "pump-stop.png")
    proc = run_script("inventory_icons.py", "--input", refs, "--set", ready)
    assert proc.returncode == 0, proc.stderr
    state = json.loads((ready / "run-state.json").read_text())
    assert state["pending_ids"] == ["pump-stop"], "finished icons are not forgotten"

    # 2. draw, checkpoint, review
    (ready / "masters" / "pump-stop.svg").write_text(NEW_MASTER)
    plan = run_json("batch.py", "plan", "--set", ready)[1]
    assert plan["batches"] == [{"batch": 1, "group": "devices-connectivity", "ids": ["pump-stop"], "undersized": True}]
    done = run_script("batch.py", "done", "--set", ready, "--group", "devices-connectivity", "--ids", "pump-stop",
                      "--project-root", ROOT)
    assert done.returncode == 0, done.stderr
    approve_set(ready, tmp_path, kind="batch", ids=["pump-stop"])

    # 3. only the new outputs are created
    proc, out = run_json("export_assets.py", "--set", ready)
    assert proc.returncode == 0, proc.stderr
    assert len(out["create"]) == 17 and len(out["unchanged"]) == 170 and out["update"] == [] and out["remove"] == []
    after = tree(ready / "exports")
    assert {k: v for k, v in after.items() if k in before} == before, "existing exports are byte-identical"
    assert tree(ready / "masters").items() >= old_masters.items(), "existing masters untouched"
    assert len(after) - len(before) == 17
    assert run_script("validate_icons.py", "--set", ready, "--phase", "exported").returncode == 0

    # 4. version and changelog
    proc, out = run_json("manifest.py", "bump", "--set", ready, "--part", "minor", "--note", "Add pump-stop",
                         "--ids", "pump-stop")
    assert out["version"] == "1.1.0"
    changelog = (ready / "CHANGELOG.md").read_text()
    assert "## 1.1.0" in changelog and "Add pump-stop" in changelog and "pump-stop" in changelog
    assert json.loads((ready / "manifest.json").read_text())["asset_set_version"] == "1.1.0"

    # 5. the Desktop device-list evidence no longer covers the new icon
    row = next(r for r in evaluate(ready)[1]["contexts"] if r["context"] == "desktop-device-list")
    assert row["status"] == "not-tested" and "pump-stop" in row["reason"]


def test_at25_bump_requires_a_note_and_rejects_unknown_part(ready):
    assert run_script("manifest.py", "bump", "--set", ready, "--part", "minor").returncode == 2
    assert run_script("manifest.py", "bump", "--set", ready, "--part", "huge", "--note", "x").returncode == 2
