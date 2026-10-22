"""The `logs` skill and progress.py: a read-only, stdlib-only view of where a work set is in the workflow."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, SCRIPTS, approve_set, run_json, run_script

import progress
import run_state

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def show(set_dir, *args, env=None):
    proc = run_script("progress.py", "--set", set_dir, "--color", "never", *args, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def model(set_dir):
    proc, data = run_json("progress.py", "--set", set_dir, "--format", "json")
    assert proc.returncode == 0, proc.stderr
    return data


def tree(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


# ------------------------------------------------------------------ stage model

def test_every_stage_is_mapped_and_progress_never_goes_backward():
    assert set(run_state.NORMAL_STAGES) == set(progress.STAGE_TABLE)
    dones = [progress.STAGE_TABLE[s][0] for s in run_state.NORMAL_STAGES]
    assert dones == sorted(dones) and dones[0] == 0 and dones[-1] == len(progress.STEPS)
    assert len(progress.GATES) == len(progress.STEPS) - 1
    assert set(run_state.EXCEPTIONAL) == progress.EXCEPTIONAL


def test_state_after_inventory(inventoried):
    m = model(inventoried)
    assert m["stage"] == "INVENTORIED" and m["done_steps"] == 1 and m["current_step"] == 2
    assert m["state"] == "running" and m["steps"][0]["status"] == "done"
    assert m["steps"][0]["detail"] == "10 icons, 0 need review"
    assert [s["status"] for s in m["steps"]] == ["done", "current"] + ["pending"] * 6
    assert m["steps"][1]["state"] == "running"


def test_waiting_for_the_pilot_approval(pilot_set):
    assert run_script("render_preview.py", "--set", pilot_set).returncode == 0
    m = model(pilot_set)
    assert m["stage"] == "PILOT_READY" and m["current_step"] == 4 and m["state"] == "waiting"
    text = show(pilot_set)
    assert "WAITING FOR YOU" in text and "previews ready, waiting for approval" in text
    assert "approve the pilot" in text.lower()


def test_pilot_approved_moves_to_generate_and_is_labeled_by_who_approved(exportable):
    m = model(exportable)
    assert m["stage"] == "PILOT_APPROVED" and m["current_step"] == 5 and m["state"] == "running"
    pilot = m["steps"][3]
    assert pilot["status"] == "done" and "approved by user" in pilot["detail"] and "min score 4/5" in pilot["detail"]
    assert pilot["gate"]["status"] == "ok"
    assert "YOU ARE HERE" in show(exportable)


def test_an_agent_approval_is_never_shown_as_human(pilot_set, tmp_path):
    approve_set(pilot_set, tmp_path, reviewer="agent")
    detail = model(pilot_set)["steps"][3]["detail"]
    assert "approved by agent (not human)" in detail


def test_export_then_assets_ready_then_waiting_for_application_tests(exported):
    m = model(exported)
    assert m["stage"] == "EXPORTED" and m["current_step"] == 6
    assert m["steps"][5]["status"] == "current" and m["steps"][4]["detail"].endswith("10/10 eligible")
    assert run_script("validate_icons.py", "--set", exported, "--phase", "exported").returncode == 0
    m = model(exported)
    assert m["stage"] == "ASSETS_READY" and m["current_step"] == 7 and m["state"] == "waiting"
    assert m["steps"][5]["detail"] == "160 PNG + 10 SVG, QA 10/10"
    assert run_script("app_validation.py", "init", "--set", exported).returncode == 0
    assert "7 contexts: 7 not-tested" in model(exported)["steps"][6]["detail"]
    assert "not-tested" in show(exported) and "WAITING FOR YOU" in show(exported)


def test_a_failure_stops_the_current_step_and_shows_the_recovery(exportable):
    (exportable / "masters" / "pump.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'/>")
    assert run_script("validate_icons.py", "--set", exportable, "--phase", "source",
                      "--project-root", ROOT).returncode == 4
    m = model(exportable)
    assert m["stage"] == "NEEDS_REVIEW" and m["state"] == "failed" and m["current_step"] == 5
    text = show(exportable)
    assert "STOPPED HERE" in text and "[!]" not in text and "✖" in text
    assert "fix pump" in text and "pump:" in text, "the errors and the recovery action are shown"


def test_a_complete_set_has_no_current_step(exportable):
    state = json.loads((exportable / "run-state.json").read_text())
    state.update(stage="COMPLETE", last_valid_stage="COMPLETE")
    (exportable / "run-state.json").write_text(json.dumps(state))
    m = model(exportable)
    assert m["state"] == "complete" and m["current_step"] is None and m["done_steps"] == 8
    assert all(s["status"] == "done" for s in m["steps"])
    line = run_script("progress.py", "--set", exportable, "--format", "line", "--color", "never").stdout
    assert "8/8" in line and "complete" in line


def test_a_stale_pilot_approval_is_flagged(exportable):
    master = exportable / "masters" / "pump.svg"
    master.write_text(master.read_text().replace("M5 21h12", "M5 20h12"))
    m = model(exportable)
    assert "STALE" in m["steps"][3]["detail"]
    assert m["steps"][3]["gate"]["status"] == "warn" and "pump" in m["steps"][3]["gate"]["note"]
    assert "⚠" in show(exportable)
    assert "pending changes: geometry" in m["steps"][7]["detail"]


# ------------------------------------------------------------------ output forms

def test_json_has_the_documented_shape(exported):
    m = model(exported)
    assert {"set_id", "stage", "last_valid_stage", "state", "current_step", "done_steps", "total_steps", "steps",
            "next", "errors", "pending_changes"} <= set(m)
    assert m["total_steps"] == 8 and [s["name"] for s in m["steps"]] == progress.STEPS
    for s in m["steps"]:
        assert {"n", "name", "status", "detail", "files"} <= set(s)
        for rel in s["files"]:
            assert (exported / rel).exists(), rel
    assert all("gate" in s for s in m["steps"][:7]) and "gate" not in m["steps"][7]


def test_vertical_layout_has_edges_between_steps_and_one_marker(exportable):
    text = show(exportable)
    assert text.count("YOU ARE HERE") == 1
    assert text.count("●") == 4 and text.count("◉") == 1 and text.count("○") == 3
    assert text.count("gate ✔") == 4, "one passed gate per finished step boundary"
    assert "┃" in text and "┊" in text, "solid edges behind, dotted edges ahead"
    assert re.search(r"stage PILOT_APPROVED", text)


def test_no_color_unless_asked_and_always_means_always(exported):
    plain = run_script("progress.py", "--set", exported).stdout  # not a tty: auto means plain
    assert "\x1b" not in plain
    colored = run_script("progress.py", "--set", exported, "--color", "always").stdout
    assert "\x1b[32m" in colored and "\x1b[0m" in colored
    assert ANSI.sub("", colored) == plain, "color changes nothing but color"
    forced = run_script("progress.py", "--set", exported, env={**os.environ, "FORCE_COLOR": "1"}).stdout
    assert "\x1b[32m" in forced
    muted = run_script("progress.py", "--set", exported, env={**os.environ, "FORCE_COLOR": "1", "NO_COLOR": "1"}).stdout
    assert "\x1b" not in muted, "NO_COLOR wins over auto detection"


def with_state(set_dir, stage, last=None):
    state = json.loads((set_dir / "run-state.json").read_text())
    state.update(stage=stage, last_valid_stage=last or stage)
    (set_dir / "run-state.json").write_text(json.dumps(state))


def test_state_colors_follow_the_legend(exportable):
    running = run_script("progress.py", "--set", exportable, "--color", "always").stdout
    assert "\x1b[1;36m" in running and "\x1b[32m" in running and "\x1b[90m" in running  # cyan here, green done, gray todo
    with_state(exportable, "PILOT_READY")
    assert "\x1b[1;33m" in run_script("progress.py", "--set", exportable, "--color", "always").stdout
    with_state(exportable, "NEEDS_REVIEW", "PILOT_APPROVED")
    assert "\x1b[1;31m" in run_script("progress.py", "--set", exportable, "--color", "always").stdout


def test_ascii_mode_uses_plain_symbols_only(exportable):
    text = show(exportable, "--ascii")
    assert text.isascii() and "[x]" in text and "[>]" in text and "[ ]" in text and "<--" in text
    line = run_script("progress.py", "--set", exportable, "--format", "line", "--ascii", "--color", "never").stdout
    assert line.isascii() and "#" in line and "-" in line


def test_lines_are_clipped_to_the_requested_width(exported):
    for width in (40, 60):
        for line in show(exported, "--width", str(width)).splitlines():
            assert len(line) <= width, (width, line)


def test_the_one_line_form_names_the_step_and_what_it_is_doing(exported):
    done = run_script("progress.py", "--set", exported, "--format", "line", "--color", "never").stdout
    assert done.startswith("▰") and "5/8" in done and "▶ Export" in done
    with_state(exported, "PILOT_APPROVED")
    line = run_script("progress.py", "--set", exported, "--format", "line", "--color", "never").stdout.strip()
    assert "4/8" in line and "▶ Generate" in line
    with_state(exported, "ASSETS_READY")
    assert "6/8" in run_script("progress.py", "--set", exported, "--format", "line", "--color", "never").stdout


# ------------------------------------------------------------------ finding the set, status line, safety

def test_without_a_set_it_picks_the_newest_and_says_so(tmp_path, exported):
    project = tmp_path / "project"
    for name in ("old-set", "new-set"):
        shutil.copytree(exported, project / "icon-work" / name)
    with_state(project / "icon-work" / "new-set", "INVENTORIED")
    old = project / "icon-work" / "old-set" / "run-state.json"
    os.utime(old, (1_000_000, 1_000_000))
    proc = run_script("progress.py", "--color", "never", cwd=project)
    assert proc.returncode == 0, proc.stderr
    assert "showing the newest of 2 sets" in proc.stdout and "INVENTORIED" in proc.stdout


def test_a_missing_set_is_an_input_error_but_the_status_line_stays_silent(tmp_path):
    proc = run_script("progress.py", cwd=tmp_path)
    assert proc.returncode == 2 and "no work set found" in proc.stderr
    silent = run_script("progress.py", "--from-stdin", cwd=tmp_path, input=json.dumps({"workspace": {"current_dir": str(tmp_path)}}))
    assert silent.returncode == 0 and silent.stdout == "" and silent.stderr == ""
    garbage = run_script("progress.py", "--from-stdin", cwd=tmp_path, input="not json")
    assert garbage.returncode == 0 and garbage.stdout == ""


def test_status_line_mode_reads_the_project_directory_from_stdin(tmp_path, exportable):
    project = exportable.parent.parent
    payload = json.dumps({"workspace": {"current_dir": str(project), "project_dir": str(project)}})
    proc = run_script("progress.py", "--from-stdin", "--color", "never", cwd=tmp_path, input=payload)
    assert proc.returncode == 0 and "▶ Generate" in proc.stdout and proc.stdout.count("\n") == 1


def test_it_is_read_only_in_every_format(exported):
    before = tree(exported)
    for args in (["--format", "vertical"], ["--format", "line"], ["--format", "json"], ["--ascii"]):
        assert run_script("progress.py", "--set", exported, *args).returncode == 0
    run_script("progress.py", "--from-stdin", input=json.dumps({"workspace": {"current_dir": str(exported.parent.parent)}}))
    assert tree(exported) == before


def test_broken_files_degrade_to_unknown_instead_of_crashing(exported):
    (exported / "manifest.json").write_text("{ not json")
    (exported / "approvals.json").write_text("")
    proc = run_script("progress.py", "--set", exported, "--color", "never")
    assert proc.returncode == 0, proc.stderr
    assert "not approved yet" in proc.stdout
    (exported / "run-state.json").write_text("{}")
    bad = run_script("progress.py", "--set", exported)
    assert bad.returncode == 2 and "run-state.json" in bad.stderr


def test_it_runs_without_any_third_party_package(exported):
    code = ("import sys, runpy; sys.path.insert(0, %r); "
            "[sys.modules.__setitem__(m, None) for m in ('PIL', 'jsonschema', 'defusedxml')]; "
            "sys.argv = ['progress.py', '--set', %r, '--format', 'line', '--color', 'never']; "
            "runpy.run_path(%r, run_name='__main__')" % (str(SCRIPTS), str(exported), str(SCRIPTS / "progress.py")))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert "Export" in proc.stdout


# ------------------------------------------------------------------ the skill itself

def test_logs_skill_is_a_thin_read_only_skill_that_points_at_the_script():
    skill = ROOT / "skills" / "logs" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    front = re.match(r"---\n(.*?)\n---\n", text, re.S).group(1)
    assert re.search(r"^name: logs$", front, re.M)
    desc = re.search(r"^description: (.+)$", front, re.M).group(1)
    assert len(desc) < 1024 and "Read-only" in desc and "which step" in desc
    for needle in ("progress.py", "Never modify a file", "${CLAUDE_PLUGIN_ROOT}", "fenced code block", "ASSETS_READY",
                   "--from-stdin", "--format json"):
        assert needle in text, needle
    assert len(text.splitlines()) < 60
    assert not re.search(r"/home/\w+|/mnt/[a-z]/", text)
    assert not re.search(r"\b(approvals\.py record|export_assets\.py|batch\.py)\b", text), "this skill never runs generators"
