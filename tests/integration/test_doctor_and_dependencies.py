"""AT-01 (bootstrap/doctor) and AT-02 (missing, wrong-origin or changed dependency)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from conftest import ROOT, SCRIPTS, run_json, run_script


def test_at01_doctor_runs_in_repo_without_references():
    proc, data = run_json("doctor.py", "--project-root", ROOT, "--lock", ROOT / "dependencies.lock.json")
    assert proc.returncode == 0, proc.stderr
    assert data["ok"] is True
    names = {c["name"] for c in data["checks"]}
    assert {"python", "packages", "renderer", "upstream", "skill-discovery"} <= names
    renderer = next(c for c in data["checks"] if c["name"] == "renderer")
    assert renderer["version"], "renderer version must be reported"
    assert data["blocked_phases"] == []


def test_at01_doctor_works_in_greenfield_directory(tmp_path):
    # no lock, no set, no references: still produces a readable report and names blocked phases
    proc, data = run_json("doctor.py", "--project-root", tmp_path, "--lock", tmp_path / "none.lock.json")
    assert data is not None, proc.stderr
    assert proc.returncode == 3
    assert "pilot" in data["blocked_phases"]
    assert any(c["name"] == "python" and c["status"] == "ok" for c in data["checks"])


def test_at02_changed_dependency_is_blocked_not_substituted(project_root):
    audit = project_root / ".claude" / "skills" / "icon-set-audit" / "SKILL.md"
    audit.write_text(audit.read_text() + "\n<!-- tampered -->\n")
    proc, data = run_json("doctor.py", "--project-root", project_root)
    assert proc.returncode == 3
    detail = next(c["detail"] for c in data["checks"] if c.get("skill") == "icon-set-audit")
    assert "differ from the lock" in detail and "no silent substitution" in detail
    assert {"pilot", "generate", "extend", "audit"} <= set(data["blocked_phases"])
    assert "export" not in data["blocked_phases"], "independent phases keep working"


def test_at02_missing_dependency_is_blocked(project_root):
    import shutil
    shutil.rmtree(project_root / ".claude" / "skills" / "icon-set-extend")
    proc, data = run_json("doctor.py", "--project-root", project_root)
    assert proc.returncode == 3
    assert any(c.get("skill") == "icon-set-extend" and "not installed" in c["detail"] for c in data["checks"])


def test_at02_wrong_origin_is_rejected(tmp_path):
    fake = tmp_path / "fake-clone"
    fake.mkdir()
    subprocess.run(["git", "init", "-q", str(fake)], check=True)
    subprocess.run(["git", "-C", str(fake), "remote", "add", "origin", "https://github.com/someone-else/skills.git"],
                   check=True)
    proc = run_script("setup_upstream.py", "--source", fake, "--dest", tmp_path / "skills",
                      "--lock", tmp_path / "lock.json")
    assert proc.returncode == 3
    assert "origin mismatch" in proc.stderr
    assert not (tmp_path / "lock.json").exists(), "no lock may be written for a wrong origin"


def test_lock_records_commit_hashes_and_renderer():
    lock = json.loads((ROOT / "dependencies.lock.json").read_text())
    up = lock["upstream"]
    assert re.fullmatch(r"[0-9a-f]{40}", up["commit"])
    assert up["repository"] == "https://github.com/shadcn-labs/skills"
    assert set(up["skills"]) == {"icon-set-generator", "icon-set-extend", "icon-set-audit"}
    for entry in up["skills"].values():
        assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in entry["files"].values())
    assert lock["renderer"]["name"] == "resvg" and lock["renderer"]["version"]


def test_nfr06_no_developer_absolute_paths_in_package():
    offenders = []
    for path in (ROOT / "skills" / "industrial-icon-designer").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".md", ".json"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"/home/\w+|/mnt/[a-z]/|C:\\\\Users", text):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
