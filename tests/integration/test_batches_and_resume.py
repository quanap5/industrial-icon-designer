"""AT-10 (batch generation) and AT-17 (interrupt and resume)."""
from __future__ import annotations

import json
import shutil

import pytest

from conftest import FIXTURES, ROOT, approve_set, restrict_pilot, run_json, run_script

import batch

PILOT = ["add", "pump", "trend-chart"]


@pytest.fixture
def staged(pilot_set, tmp_path):
    """Pilot approved for three icons; the other seven still have to be generated."""
    restrict_pilot(pilot_set, PILOT)
    approve_set(pilot_set, tmp_path)
    return pilot_set


def draw(set_dir, *ids):
    for i in ids:
        shutil.copy(FIXTURES / "masters" / f"{i}.svg", set_dir / "masters" / f"{i}.svg")


def state(set_dir):
    return json.loads((set_dir / "run-state.json").read_text())


# ---------------------------------------------------------------- chunking

@pytest.mark.parametrize("count,sizes", [(3, [3]), (5, [5]), (10, [10]), (11, [6, 5]), (12, [6, 6]),
                                         (20, [10, 10]), (23, [8, 8, 7])])
def test_chunking_keeps_batches_between_five_and_ten(count, sizes):
    parts = batch.chunk([f"i{n:02d}" for n in range(count)])
    assert [len(p) for p in parts] == sizes


# ---------------------------------------------------------------- AT-10

def test_at10_generation_is_closed_without_a_valid_pilot_approval(pilot_set):
    proc = run_script("batch.py", "plan", "--set", pilot_set)
    assert proc.returncode == 4 and "approval gate closed" in proc.stderr


def test_at10_plan_groups_pending_icons_by_function(staged):
    proc, plan = run_json("batch.py", "plan", "--set", staged)
    assert proc.returncode == 0, proc.stderr
    groups = {b["group"]: b["ids"] for b in plan["batches"]}
    assert groups == {"alarms-events": ["alarm-list"], "devices-connectivity": ["device-connect", "network", "valve"],
                      "file-edit": ["open-folder", "save"], "users-settings": ["settings"]}
    assert all(b["undersized"] for b in plan["batches"]), "each group is below five"
    assert [b["batch"] for b in plan["batches"]] == [1, 2, 3, 4]
    assert state(staged)["stage"] == "GENERATING"
    assert sorted(state(staged)["pending_ids"]) == sorted(i for ids in groups.values() for i in ids)


def test_at10_unresolved_meaning_is_blocked_not_planned(staged):
    inv = json.loads((staged / "inventory.json").read_text())
    next(i for i in inv["icons"] if i["id"] == "valve")["status"] = "NEEDS_REVIEW"
    (staged / "inventory.json").write_text(json.dumps(inv))
    plan = run_json("batch.py", "plan", "--set", staged)[1]
    assert plan["blocked_needs_review"] == ["valve"]
    assert all("valve" not in b["ids"] for b in plan["batches"])


def test_at10_batch_checkpoint_is_recorded_only_after_validation(staged):
    run_script("batch.py", "plan", "--set", staged)
    draw(staged, "open-folder", "save")
    proc, out = run_json("batch.py", "done", "--set", staged, "--group", "file-edit",
                         "--ids", "open-folder,save", "--project-root", ROOT)
    assert proc.returncode == 0, proc.stderr
    assert out["recorded_batch"]["ids"] == ["open-folder", "save"] and out["recorded_batch"]["group"] == "file-edit"
    s = state(staged)
    assert [b["ids"] for b in s["completed_batches"]] == [["open-folder", "save"]]
    assert "save" not in s["pending_ids"] and "network" in s["pending_ids"]


@pytest.mark.parametrize("args,message", [
    (("--group", "file-edit", "--ids", "valve"), "not pending in group 'file-edit'"),
    (("--group", "file-edit", "--ids", "save,save"), "duplicate ids"),
    (("--group", "file-edit", "--ids", "save"), "needs 5-10 icons unless it finishes the group"),
    (("--group", "file-edit", "--ids", "open-folder,save"), "no master drawn for"),
])
def test_at10_done_rejects_wrong_batches(staged, args, message):
    run_script("batch.py", "plan", "--set", staged)
    proc = run_script("batch.py", "done", "--set", staged, *args, "--project-root", ROOT)
    assert proc.returncode == 2 and message in proc.stderr
    assert state(staged)["completed_batches"] == []


def test_at10_failing_master_blocks_the_checkpoint(staged):
    run_script("batch.py", "plan", "--set", staged)
    draw(staged, "open-folder", "save")
    (staged / "masters" / "save.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'/>")
    proc = run_script("batch.py", "done", "--set", staged, "--group", "file-edit", "--ids", "open-folder,save",
                      "--project-root", ROOT)
    assert proc.returncode == 4 and "save" in proc.stderr and "batch not recorded" in proc.stderr
    assert state(staged)["completed_batches"] == []


def test_at10_full_generation_reaches_source_qa_passed(staged, tmp_path):
    plan = run_json("batch.py", "plan", "--set", staged)[1]
    for b in plan["batches"]:
        draw(staged, *b["ids"])
        proc = run_script("batch.py", "done", "--set", staged, "--group", b["group"], "--ids", ",".join(b["ids"]),
                          "--project-root", ROOT)
        assert proc.returncode == 0, proc.stderr
    s = state(staged)
    assert s["pending_ids"] == [] and len(s["completed_batches"]) == 4
    assert s["stage"] == "SOURCE_QA_PASSED"
    approve_set(staged, tmp_path, kind="batch", ids=[i for b in plan["batches"] for i in b["ids"]])
    all_ids = sorted(i["id"] for i in json.loads((staged / "inventory.json").read_text())["icons"])
    status = json.loads(run_script("manifest.py", "status", "--set", staged, "--json").stdout)
    assert status["eligible"] == all_ids, "every icon is structurally valid and visually approved"


# ---------------------------------------------------------------- AT-17

def test_at17_resume_keeps_approved_work_and_continues_pending(staged):
    run_script("batch.py", "plan", "--set", staged)
    draw(staged, "open-folder", "save")
    run_script("batch.py", "done", "--set", staged, "--group", "file-edit", "--ids", "open-folder,save",
               "--project-root", ROOT)
    before = {p.name: p.read_bytes() for p in (staged / "masters").glob("*.svg")}
    # interruption: a fresh process resumes from run-state.json alone
    proc, plan = run_json("batch.py", "status", "--set", staged)
    assert proc.returncode == 0
    assert plan["keep"] == ["open-folder", "save"]
    assert plan["regenerate"] == ["alarm-list", "device-connect", "network", "settings", "valve"]
    replanned = run_json("batch.py", "plan", "--set", staged)[1]
    planned = {i for b in replanned["batches"] for i in b["ids"]}
    assert planned == set(plan["regenerate"]) and not planned & set(plan["keep"])
    assert {p.name: p.read_bytes() for p in (staged / "masters").glob("*.svg")} == before, "nothing was regenerated"
    assert [b["batch"] for b in replanned["batches"]][0] == 2, "numbering continues after the checkpoint"


def test_at17_exceptional_state_preserves_the_last_valid_stage(staged):
    run_script("batch.py", "plan", "--set", staged)
    draw(staged, "open-folder", "save")
    (staged / "masters" / "save.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'/>")
    run_script("validate_icons.py", "--set", staged, "--phase", "source", "--project-root", ROOT)
    s = state(staged)
    assert s["stage"] == "NEEDS_REVIEW" and s["last_valid_stage"] == "GENERATING"
    assert "rerun validate_icons.py" in s["recovery_action"]
    assert any(e["id"] == "save" or "save" in e["id"] for e in s["errors"]), "failures are listed, never dropped"
    resume = run_json("batch.py", "status", "--set", staged)[1]
    assert resume["recovery_action"] and resume["last_valid_stage"] == "GENERATING"
