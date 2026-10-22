"""The repository is a Claude Code plugin and marketplace: manifests, self-containment, and an install simulation."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURES, ROOT

PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
HAS_GIT = (ROOT / ".git").exists() and shutil.which("git") is not None


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
                         capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if (ROOT / f).exists()]


def test_manifests_are_consistent_with_each_other():
    plugin, market = load(PLUGIN), load(MARKET)
    assert plugin["name"] == "qk" and plugin["license"] == "MIT"
    entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
    assert market["renames"] == {"industrial-icon-designer": "qk"}, "existing installs of the old name migrate"
    assert "industrial-icon-designer" not in [p["name"] for p in market["plugins"]]
    assert entry["name"] == plugin["name"], "entry name and manifest name must match"
    assert entry["source"] == ".", "the repository root is the plugin"
    assert "version" not in entry, "version is set once, in plugin.json"
    assert re.fullmatch(r"\d+\.\d+\.\d+", plugin["version"])
    assert market["name"] == "quanap5-plugins" and market["owner"]["name"]
    assert plugin["repository"].endswith("quanap5/industrial-icon-designer")


def test_versions_agree_across_plugin_pyproject_and_changelog():
    version = load(PLUGIN)["version"]
    assert f'version = "{version}"' in (ROOT / "pyproject.toml").read_text()
    first_heading = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGELOG.md").read_text(), re.M).group(1)
    assert first_heading == version


def test_the_skill_sits_where_a_plugin_loads_it():
    skill = ROOT / "skills" / "industrial-icon-designer" / "SKILL.md"
    assert skill.is_file()
    assert re.search(r"^name: industrial-icon-designer$", skill.read_text(), re.M)


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_claude_plugin_validate_passes():
    proc = subprocess.run(["claude", "plugin", "validate", str(ROOT)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Validation passed" in proc.stdout + proc.stderr


def test_skill_documents_both_paths_and_the_explicit_setup():
    text = (ROOT / "skills/industrial-icon-designer/SKILL.md").read_text()
    for needle in ("${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PLUGIN_DATA}", "--project-root", "uv venv --python 3.11",
                   "requirements.lock", "cargo install resvg", "ask the user first"):
        assert needle in text, needle
    assert not re.search(r"/home/\w+|/mnt/[a-z]/", text)


def test_readme_gives_the_install_lines_and_the_private_repo_requirements():
    text = (ROOT / "README.md").read_text()
    for needle in ("/plugin marketplace add quanap5/industrial-icon-designer",
                   "/plugin install qk@quanap5-plugins",
                   "--marketplace quanap5/industrial-icon-designer", "/qk:industrial-icon-designer", "/qk:logs", "read access", "gh auth setup-git",
                   "CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1"):
        assert needle in text, needle


@pytest.mark.skipif(not HAS_GIT, reason="needs the git checkout")
def test_locked_upstream_skills_ship_with_the_repository():
    files = set(tracked_files())
    lock = load(ROOT / "dependencies.lock.json")
    for name, entry in lock["upstream"]["skills"].items():
        for rel in entry["files"]:
            assert f".claude/skills/{name}/{rel}" in files, f"{name}/{rel} would not be in the plugin"
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", ".claude/skills/icon-set-audit/SKILL.md"],
                             check=False).returncode
    assert ignored == 1, "vendored upstream files must not be git-ignored"


@pytest.mark.skipif(not HAS_GIT, reason="needs the git checkout")
def test_install_simulation_runs_from_a_plugin_cache_with_another_project_as_cwd(tmp_path):
    cache = tmp_path / "plugin-cache" / "industrial-icon-designer"
    for rel in tracked_files():
        src = ROOT / rel
        dst = cache / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            continue  # the checkout-only convenience link is not needed in a cache
        shutil.copy2(src, dst)
    assert (cache / ".claude-plugin" / "plugin.json").is_file()

    project = tmp_path / "users project"
    refs = project / "references"
    shutil.copytree(FIXTURES / "references", refs)
    (refs / "mystery-glyph.png").unlink()
    shutil.copy(FIXTURES / "metadata.json", refs / "metadata.json")
    scripts = cache / "skills" / "industrial-icon-designer" / "scripts"

    def run(script, *args):
        return subprocess.run([sys.executable, str(scripts / script), *map(str, args)], cwd=project,
                              capture_output=True, text=True, check=False)

    doctor = run("doctor.py", "--project-root", cache, "--json")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    checks = {(c["name"], c["status"]) for c in json.loads(doctor.stdout)["checks"]}
    assert ("upstream", "ok") in checks and ("skill-discovery", "ok") in checks
    assert ("upstream", "fail") not in checks

    set_dir = project / "icon-work" / "demo"
    assert run("inventory_icons.py", "--input", refs, "--set", set_dir).returncode == 0
    assert run("analysis.py", "brief", "--set", set_dir).returncode == 0
    audit = run("analysis.py", "audit", "--set", set_dir, "--project-root", cache)
    assert audit.returncode == 0, audit.stderr
    baseline = json.loads((set_dir / "reports" / "baseline-audit.json").read_text())
    assert baseline["route"] == "native-svg", "the locked upstream audit ran from the plugin cache"
    assert not (cache / "icon-work").exists(), "outputs go to the user's project, never the plugin directory"

    (cache / ".claude/skills/icon-set-audit/SKILL.md").write_text("tampered")
    blocked = run("doctor.py", "--project-root", cache, "--json")
    assert blocked.returncode == 3, "a modified upstream file blocks the plugin's affected phases"
