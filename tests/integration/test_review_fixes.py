"""Regression tests for the defects an independent review found: markup smuggling, honest application status,
gates on approvals and palette, removed icons, symlinked directories, exit codes, and smaller hardening."""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURES, ROOT, SCRIPTS, approve_set, restrict_pilot, run_json, run_script, write_scores

import app_validation

HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">')


def validate(set_dir, *extra):
    return run_json("validate_icons.py", "--set", set_dir, "--phase", "source", "--project-root", ROOT, *extra)


def tree(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


# ----------------------------------------------------------------- C1 markup smuggling

@pytest.mark.parametrize("payload", [
    "<!--><script>alert(1)</script>-->",
    "<?x ><img src=x onerror=alert(1)>?>",
    "<![CDATA[<script>alert(1)</script>]]>",
    "<!-- generator comment -->",
])
def test_c1_masters_with_comments_pis_or_cdata_are_rejected(pilot_set, payload):
    (pilot_set / "masters" / "pump.svg").write_text(HEAD + payload + "<path d='M4 12h16'/></svg>")
    proc, report = validate(pilot_set)
    assert proc.returncode == 4
    assert any("comments, processing instructions and CDATA" in e for e in report["icons"]["pump"]["errors"])
    assert report["icons"]["save"]["status"] == "passed"


def test_c1_rejected_master_never_reaches_preview_or_exports(pilot_set):
    (pilot_set / "masters" / "pump.svg").write_text(HEAD + "<!--><script>alert(1)</script>--><path d='M4 12h16'/></svg>")
    assert run_script("render_preview.py", "--set", pilot_set).returncode == 0
    pages = "".join((pilot_set / "preview" / name).read_text() for name in
                    ("index.html", "contexts/web.html", "contexts/desktop.html"))
    assert "<script" not in pages and "alert(1)" not in pages


def test_c1_a_leading_xml_declaration_is_still_fine_in_a_master(pilot_set):
    text = (pilot_set / "masters" / "pump.svg").read_text()
    (pilot_set / "masters" / "pump.svg").write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + text)
    proc, report = validate(pilot_set)
    assert report["icons"]["pump"]["status"] == "passed", report["icons"]["pump"]["errors"]


def test_c1_references_may_carry_comments_because_they_are_only_rasterized(tmp_path):
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "marker.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                                     "<!-- exported by a tool --><circle cx='12' cy='12' r='6'/></svg>")
    proc = run_script("inventory_icons.py", "--input", refs, "--set", tmp_path / "set")
    assert proc.returncode == 0, proc.stderr
    assert [i["id"] for i in json.loads((tmp_path / "set" / "inventory.json").read_text())["icons"]] == ["marker"]


# ----------------------------------------------------------------- C2 / H1 honest application status

def contexts_passed(set_dir):
    for ctx in app_validation.required(set_dir):
        ids = app_validation.expected_icons(set_dir, ctx["id"]) or ["add"]
        env = ["framework=DevExpress 15.1.11"] if ctx["platform"] == "desktop" else ["browser=Chrome 130"]
        args = ["app_validation.py", "record", "--set", set_dir, "--context", ctx["id"], "--status", "passed",
                "--reason", "checked", "--env", *env, "--icons", ",".join(ids), "--evidence", "e.png",
                "--themes", "dark,light", "--states", "disabled,normal"]
        if ctx["platform"] == "desktop":
            args += ["--scaling", "100,125,150,200"]
        assert run_script(*args).returncode == 0


@pytest.fixture
def ready(exported):
    assert run_script("app_validation.py", "init", "--set", exported).returncode == 0
    return exported


def test_c2_removing_every_context_never_validates_the_application(ready):
    for ctx in [c["id"] for c in app_validation.required(ready)]:
        assert run_script("app_validation.py", "profile", "--set", ready, "--remove", ctx, "--reason", "no app").returncode == 0
    proc, out = run_json("app_validation.py", "evaluate", "--set", ready)
    assert out["application_validated"] is False and out["overall"] == "ASSETS_READY"
    assert out["required_contexts"] == 0 and "no required context remains" in out["message"]
    assert json.loads((ready / "run-state.json").read_text())["stage"] != "APPLICATION_VALIDATED"


def test_h1_pending_changes_prevent_the_validated_claim(ready):
    contexts_passed(ready)
    assert run_json("app_validation.py", "evaluate", "--set", ready)[1]["application_validated"] is True
    spec = json.loads((ready / "style-spec.json").read_text())
    spec["themes"]["light"]["normal"] = "#111827"
    (ready / "style-spec.json").write_text(json.dumps(spec))
    out = run_json("app_validation.py", "evaluate", "--set", ready)[1]
    assert out["application_validated"] is False and out["pending_changes"] == ["palette"]
    assert "unprocessed changes (palette)" in out["message"]


# ----------------------------------------------------------------- H2 unresolved meaning

def mark_needs_review(set_dir, icon_id):
    inv = json.loads((set_dir / "inventory.json").read_text())
    next(i for i in inv["icons"] if i["id"] == icon_id)["status"] = "NEEDS_REVIEW"
    (set_dir / "inventory.json").write_text(json.dumps(inv))


def test_h2_icons_with_unresolved_meaning_cannot_be_approved(pilot_set, tmp_path):
    mark_needs_review(pilot_set, "valve")
    scores = write_scores(tmp_path / "s.json", ["valve"])
    for reviewer, extra in (("user", []), ("agent", ["--unattended-authorized"])):
        proc = run_script("approvals.py", "record", "--set", pilot_set, "--type", "batch", "--reviewer", reviewer,
                          "--ids", "valve", *extra)
        assert proc.returncode == 4 and "unresolved meaning (NEEDS_REVIEW)" in proc.stderr
    assert not (pilot_set / "approvals.json").exists()


def test_h2_an_earlier_approval_does_not_survive_a_new_review_flag(exportable):
    mark_needs_review(exportable, "valve")
    run_script("manifest.py", "sync", "--set", exportable)
    valve = next(i for i in json.loads((exportable / "manifest.json").read_text())["icons"] if i["id"] == "valve")
    assert valve["status"] == "pending" and valve["qa"]["visual"] == "pending"
    out = run_json("export_assets.py", "--set", exportable)[1]
    assert [s["id"] for s in out["skipped"]] == ["valve"]
    assert not list((exportable / "exports").rglob("valve*"))


# ----------------------------------------------------------------- H3 / M5 pilot gate

def test_h3_export_needs_a_current_pilot_approval_even_with_batch_approvals(exportable, tmp_path):
    spec = json.loads((exportable / "style-spec.json").read_text())
    spec["stroke_width"] = 2
    (exportable / "style-spec.json").write_text(json.dumps(spec))
    assert run_script("invalidate.py", "detect", "--set", exportable, "--apply").returncode == 0
    ids = [i["id"] for i in json.loads((exportable / "inventory.json").read_text())["icons"]]
    approve_set(exportable, tmp_path, kind="batch", ids=ids)
    proc = run_script("export_assets.py", "--set", exportable)
    assert proc.returncode == 4 and "pilot approval gate closed" in proc.stderr and "stale" in proc.stderr
    assert not (exportable / "exports").exists()


def test_m5_pilot_approval_must_cover_the_whole_sample(pilot_set, tmp_path):
    ids = json.loads((pilot_set / "brief.json").read_text())["sample_ids"]
    scores = write_scores(tmp_path / "s.json", ids[:1])
    assert run_script("approvals.py", "record", "--set", pilot_set, "--type", "pilot", "--reviewer", "user",
                      "--ids", ids[0], "--scores-file", scores).returncode == 0
    proc, out = run_json("approvals.py", "check", "--set", pilot_set)
    assert proc.returncode == 4 and "does not cover the pilot sample" in out["reason"]
    assert run_script("batch.py", "plan", "--set", pilot_set).returncode == 4


# ----------------------------------------------------------------- H4 palette gate

def test_h4_a_changed_palette_blocks_export_until_it_is_approved(exported, tmp_path):
    spec = json.loads((exported / "style-spec.json").read_text())
    spec["themes"]["light"]["normal"] = "#1F2937"
    (exported / "style-spec.json").write_text(json.dumps(spec))
    assert run_script("invalidate.py", "detect", "--set", exported, "--apply").returncode == 0
    blocked = run_script("export_assets.py", "--set", exported)
    assert blocked.returncode == 4 and "palette changed and has not been reviewed" in blocked.stderr
    approve = run_script("approvals.py", "record", "--set", exported, "--type", "palette", "--reviewer", "user",
                         "--ids", "all")
    assert approve.returncode == 0, approve.stderr
    proc, out = run_json("export_assets.py", "--set", exported)
    assert proc.returncode == 0, proc.stderr
    assert len(out["create"]) + len(out["update"]) == 40, "only the light-theme PNGs are re-rendered"
    assert run_script("validate_icons.py", "--set", exported, "--phase", "exported").returncode == 0
    icons = json.loads((exported / "manifest.json").read_text())["icons"]
    assert all("color_review" not in i["qa"] for i in icons)


def test_h4_a_later_palette_change_needs_a_new_approval(exported):
    def change(color):
        spec = json.loads((exported / "style-spec.json").read_text())
        spec["themes"]["dark"]["normal"] = color
        (exported / "style-spec.json").write_text(json.dumps(spec))
        run_script("invalidate.py", "detect", "--set", exported, "--apply")
    change("#CBD5E1")
    assert run_script("approvals.py", "record", "--set", exported, "--type", "palette", "--reviewer", "user",
                      "--ids", "all").returncode == 0
    assert run_script("export_assets.py", "--set", exported).returncode == 0
    change("#BFDBFE")
    assert run_script("export_assets.py", "--set", exported).returncode == 4


# ----------------------------------------------------------------- M1 removed icons

def remove_pilot_icon(set_dir, tmp_path, icon_id):
    """Delete an icon's master, process the change, and approve the pilot again for the remaining sample."""
    (set_dir / "masters" / f"{icon_id}.svg").unlink()
    proc, out = run_json("invalidate.py", "detect", "--set", set_dir, "--apply")
    assert proc.returncode == 0, proc.stderr
    brief = json.loads((set_dir / "brief.json").read_text())
    brief["sample_ids"] = [i for i in brief["sample_ids"] if i != icon_id]
    (set_dir / "brief.json").write_text(json.dumps(brief))
    approve_set(set_dir, tmp_path, kind="pilot", ids=brief["sample_ids"])


def test_m1_deleting_a_master_does_not_orphan_its_exports(exported, tmp_path):
    assert len(list((exported / "exports").rglob("pump*"))) == 17
    remove_pilot_icon(exported, tmp_path, "pump")
    proc, out = run_json("export_assets.py", "--set", exported)
    assert proc.returncode == 0, proc.stderr
    assert len(out["remove"]) == 17 and out["unknown"] == []
    assert not list((exported / "exports").rglob("pump*"))
    assert "orphaned_exports" not in json.loads((exported / "manifest.json").read_text())


def test_m1_hand_edited_files_of_a_removed_icon_are_a_conflict(exported, tmp_path):
    (exported / "exports/web/pump.svg").write_text("hand edited")
    remove_pilot_icon(exported, tmp_path, "pump")
    proc = run_script("export_assets.py", "--set", exported)
    assert proc.returncode == 4 and "changed by hand" in proc.stderr
    assert (exported / "exports/web/pump.svg").read_text() == "hand edited"


def test_m1_removing_a_pilot_icon_without_approving_again_closes_the_gate(exported):
    (exported / "masters" / "pump.svg").unlink()
    proc = run_script("export_assets.py", "--set", exported)
    assert proc.returncode == 4  # drift first, then the closed pilot gate once drift is processed
    run_script("invalidate.py", "detect", "--set", exported, "--apply")
    proc = run_script("export_assets.py", "--set", exported)
    assert proc.returncode == 4 and "pilot approval gate closed" in proc.stderr


# ----------------------------------------------------------------- M2 symlinked directories

def test_m2_symlinked_exports_directory_is_refused(exportable, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    os.symlink(outside, exportable / "exports")
    proc = run_script("export_assets.py", "--set", exportable)
    assert proc.returncode == 2 and "resolves outside the set directory" in proc.stderr
    assert list(outside.iterdir()) == []


def test_m2_symlinked_masters_directory_is_refused(pilot_set, tmp_path):
    outside = tmp_path / "outside-masters"
    shutil.move(str(pilot_set / "masters"), outside)
    os.symlink(outside, pilot_set / "masters")
    proc = run_script("validate_icons.py", "--set", pilot_set, "--phase", "source", "--project-root", ROOT)
    assert proc.returncode == 2 and "resolves outside the set directory" in proc.stderr
    assert run_script("render_preview.py", "--set", pilot_set).returncode == 2


# ----------------------------------------------------------------- M3 exit codes

def test_m3_doctor_reports_a_missing_dependency_with_exit_3(tmp_path):
    code = (f"import sys, runpy; sys.path.insert(0, {str(SCRIPTS)!r}); sys.modules['defusedxml'] = None; "
            f"sys.argv = ['doctor.py', '--json', '--project-root', {str(tmp_path)!r}]; "
            f"runpy.run_path({str(SCRIPTS / 'doctor.py')!r}, run_name='__main__')")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert proc.returncode == 3, proc.stderr
    data = json.loads(proc.stdout)
    assert any(c["name"] == "packages" and c["status"] == "fail" and "defusedxml" in c["detail"] for c in data["checks"])


@pytest.mark.parametrize("error,code", [("OSError('disk full')", 5), ("ValueError('bad')", 2),
                                        ("KeyError('x')", 2), ("ImportError('nope')", 3)])
def test_m3_unexpected_failures_map_to_documented_exit_codes(error, code):
    snippet = f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); import common; common.run_main(lambda: (_ for _ in ()).throw({error}))"
    proc = subprocess.run([sys.executable, "-c", snippet], capture_output=True, text=True, check=False)
    assert proc.returncode == code and "Traceback" not in proc.stderr


# ----------------------------------------------------------------- M4 final QA

def test_m4_batch_done_fails_when_final_source_qa_fails(pilot_set, tmp_path):
    restrict_pilot(pilot_set, ["add", "pump", "trend-chart"])
    approve_set(pilot_set, tmp_path)
    plan = run_json("batch.py", "plan", "--set", pilot_set)[1]["batches"]
    for b in plan[:-1]:
        for i in b["ids"]:
            shutil.copy(FIXTURES / "masters" / f"{i}.svg", pilot_set / "masters" / f"{i}.svg")
        assert run_script("batch.py", "done", "--set", pilot_set, "--group", b["group"], "--ids", ",".join(b["ids"]),
                          "--project-root", ROOT).returncode == 0
    broken = plan[0]["ids"][0]  # a master from an already recorded batch breaks later
    (pilot_set / "masters" / f"{broken}.svg").write_text(HEAD + "</svg>")
    last = plan[-1]
    for i in last["ids"]:
        shutil.copy(FIXTURES / "masters" / f"{i}.svg", pilot_set / "masters" / f"{i}.svg")
    proc = run_script("batch.py", "done", "--set", pilot_set, "--group", last["group"], "--ids", ",".join(last["ids"]),
                      "--project-root", ROOT)
    assert proc.returncode == 4 and f"final source QA failed for {broken}" in proc.stderr


# ----------------------------------------------------------------- L1..L5

def test_l1_an_unlisted_file_in_an_upstream_skill_blocks_it(project_root):
    (project_root / ".claude/skills/icon-set-generator/scripts/json.py").write_text("raise SystemExit('shadowed')")
    proc, data = run_json("doctor.py", "--project-root", project_root)
    assert proc.returncode == 3
    assert any("unlisted file scripts/json.py" in c["detail"] for c in data["checks"] if c["name"] == "upstream")
    assert "pilot" in data["blocked_phases"]


def test_l2_rubric_scores_must_be_finite_and_between_one_and_five(pilot_set, tmp_path):
    ids = json.loads((pilot_set / "brief.json").read_text())["sample_ids"]
    for bad in ("NaN", "6", "Infinity", "true"):
        path = tmp_path / "bad.json"
        row = {c: 5 for c in ("meaning", "clarity_16", "balance", "consistency", "contrast")}
        row["meaning"] = "__BAD__"
        path.write_text(json.dumps({i: row for i in ids}).replace('"__BAD__"', bad))
        proc = run_script("approvals.py", "record", "--set", pilot_set, "--type", "pilot", "--reviewer", "user",
                          "--scores-file", path)
        assert proc.returncode == 4 and "below 4 on meaning" in proc.stderr, bad


def test_l3_dry_run_changes_nothing_in_the_set(exportable):
    before = tree(exportable)
    proc, out = run_json("export_assets.py", "--set", exportable, "--dry-run")
    assert proc.returncode == 0 and out["dry_run"] is True
    assert tree(exportable) == before


def test_l4_web_only_export_needs_no_renderer_and_does_not_complete_the_export(exportable):
    env = {**os.environ, "PATH": "/nonexistent"}
    proc = run_script("export_assets.py", "--set", exportable, "--target", "web", env=env)
    assert proc.returncode == 0, proc.stderr
    assert len(list((exportable / "exports" / "web").glob("*.svg"))) == 10
    assert json.loads((exportable / "run-state.json").read_text())["stage"] != "EXPORTED"


def test_l5_a_second_export_is_refused_while_one_is_running(exportable):
    fd = os.open(exportable / ".export.lock", os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        proc = run_script("export_assets.py", "--set", exportable)
        assert proc.returncode == 2 and "another export is running" in proc.stderr
        assert not (exportable / "exports").exists()
    finally:
        os.close(fd)
    assert run_script("export_assets.py", "--set", exportable, "--dry-run").returncode == 0
