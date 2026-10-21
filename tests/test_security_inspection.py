"""SEC-03, SEC-07, SEC-08, FR-IF-05, FR-DEP-06: checks by inspection of the shipped code and artifacts."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((ROOT / "skills" / "industrial-icon-designer" / "scripts").glob("*.py"))
NETWORK = re.compile(r"^\s*(?:import|from)\s+(socket|urllib\S*|requests|http\S*|ftplib|smtplib|anthropic|openai|httpx|aiohttp)\b",
                     re.M)


def test_scripts_use_no_network_or_llm_libraries():
    offenders = {p.name: NETWORK.findall(p.read_text()) for p in SCRIPTS if NETWORK.search(p.read_text())}
    assert offenders == {}, "ordinary runs are offline; only setup_upstream.py may reach the network, through git"


def test_subprocesses_use_argument_arrays_never_a_shell():
    for p in SCRIPTS:
        text = p.read_text()
        assert "shell=True" not in text and "os.system" not in text and "os.popen" not in text, p.name


def test_only_setup_upstream_talks_to_git_and_only_to_read_or_clone():
    for p in SCRIPTS:
        if p.name != "setup_upstream.py":
            assert '"git"' not in p.read_text(), f"{p.name} must not run git"
    setup = (ROOT / "skills/industrial-icon-designer/scripts/setup_upstream.py").read_text()
    used = set(re.findall(r'\bgit\(repo,\s*"([\w-]+)"', setup)) | set(re.findall(r'\["git",\s*"([a-z][\w-]*)"', setup))
    assert used == {"remote", "rev-parse", "clone"}, f"unexpected git subcommands: {used}"


def test_scripts_never_touch_global_claude_settings_or_install_packages():
    installer = re.compile(r"subprocess\.(?:run|Popen|call)\(\s*\[\s*[\"'](?:pip3?|npm|npx|cargo|uv|apt|apt-get|brew)[\"']")
    for p in SCRIPTS:
        text = p.read_text()
        assert "settings.json" not in text and ".claude/settings" not in text, p.name
        assert not installer.search(text), f"{p.name} must not install packages"


def test_setup_is_the_only_writer_of_the_lock_and_is_explicit():
    writers = [p.name for p in SCRIPTS if "write_json(Path(args.lock)" in p.read_text()]
    assert writers == ["setup_upstream.py"]
    docstring = " ".join((ROOT / "skills/industrial-icon-designer/scripts/setup_upstream.py").read_text().split())
    assert "never runs during ordinary generation" in docstring


SECRET = re.compile(r"(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (?:RSA |EC )?PRIVATE KEY|api[_-]?key\s*[:=]\s*\S+|"
                    r"password\s*[:=]\s*\S+|ghp_[A-Za-z0-9]{20,})", re.I)


def test_no_secrets_or_private_transcripts_in_shipped_artifacts():
    roots = [ROOT / "skills", ROOT / "examples", ROOT / "tests" / "fixtures", ROOT / "dependencies.lock.json"]
    hits = []
    for base in roots:
        files = [base] if base.is_file() else [f for f in base.rglob("*") if f.is_file() and f.suffix in
                                                {".py", ".md", ".json", ".svg", ".html", ".jsonl", ".csv", ".txt"}]
        for f in files:
            if SECRET.search(f.read_text(errors="ignore")):
                hits.append(str(f.relative_to(ROOT)))
    assert hits == []


def test_skill_states_the_data_and_permission_boundaries():
    skill = (ROOT / "skills/industrial-icon-designer/SKILL.md").read_text()
    for phrase in ("configured model service", "Do not send assets to any other service",
                   "Do not change global Claude settings", "commit, push or publish"):
        assert phrase in skill
