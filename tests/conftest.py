from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "industrial-icon-designer" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))


def run_script(name: str, *args, cwd: Path | None = None, input: str | None = None, env: dict | None = None):
    """Run a package script with the test interpreter; arguments are never shell-interpolated."""
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], cwd=cwd, input=input, env=env,
                          capture_output=True, text=True, check=False)


def run_json(name: str, *args, cwd: Path | None = None):
    proc = run_script(name, *args, "--json", cwd=cwd)
    try:
        return proc, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc, None


@pytest.fixture
def refs10(tmp_path) -> Path:
    """The ten synthetic reference icons plus metadata, without the ambiguous glyph."""
    dst = tmp_path / "references"
    shutil.copytree(FIXTURES / "references", dst)
    (dst / "mystery-glyph.png").unlink()
    shutil.copy(FIXTURES / "metadata.json", dst / "metadata.json")
    return dst


def _build_inventoried(root: Path) -> Path:
    refs = root / "references"
    shutil.copytree(FIXTURES / "references", refs)
    (refs / "mystery-glyph.png").unlink()
    shutil.copy(FIXTURES / "metadata.json", refs / "metadata.json")
    set_dir = root / "icon-work" / "scada-fixture"
    proc = run_script("inventory_icons.py", "--input", refs, "--set", set_dir, "--set-id", "scada-fixture")
    assert proc.returncode == 0, proc.stderr
    return set_dir


@pytest.fixture(scope="session")
def _inventoried_template(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("inventoried-template")
    _build_inventoried(root)
    return root


@pytest.fixture
def inventoried(tmp_path, _inventoried_template) -> Path:
    """A set directory with inventory.json and run-state.json for the ten fixture icons (private copy)."""
    root = tmp_path / "w"
    shutil.copytree(_inventoried_template, root)
    return root / "icon-work" / "scada-fixture"


GOOD_SCORES = {"meaning": 5, "clarity_16": 4, "balance": 4, "consistency": 5, "contrast": 4,
               "semantic_defect": False}


def write_scores(path: Path, ids, **override) -> Path:
    path.write_text(json.dumps({i: {**GOOD_SCORES, **override} for i in ids}))
    return path


def approve_set(set_dir: Path, tmp_path: Path, kind: str = "pilot", ids=None, reviewer: str = "user"):
    """Record an approval for `ids` (default: the pilot sample) with passing rubric scores."""
    if ids is None:
        ids = json.loads((set_dir / "brief.json").read_text())["sample_ids"]
    scores = write_scores(tmp_path / f"scores-{kind}.json", ids)
    extra = ["--unattended-authorized"] if reviewer == "agent" else []
    proc = run_script("approvals.py", "record", "--set", set_dir, "--type", kind, "--reviewer", reviewer,
                      "--ids", ",".join(ids), "--scores-file", scores, *extra)
    assert proc.returncode == 0, proc.stderr
    return ids


def restrict_pilot(set_dir: Path, pilot_ids):
    """Keep masters only for the pilot icons and narrow the sample, so the rest is still to be generated."""
    brief = json.loads((set_dir / "brief.json").read_text())
    brief["sample_ids"] = sorted(pilot_ids)
    (set_dir / "brief.json").write_text(json.dumps(brief))
    for master in (set_dir / "masters").glob("*.svg"):
        if master.stem not in pilot_ids:
            master.unlink()


@pytest.fixture(scope="session")
def _pilot_template(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("pilot-template")
    s = _build_inventoried(root)
    for args in (("analysis.py", "brief", "--set", s), ("analysis.py", "sample", "--set", s),
                 ("style_spec.py", "init", "--set", s, "--set-id", "scada-fixture"),
                 ("style_spec.py", "generate", "--set", s)):
        proc = run_script(*args)
        assert proc.returncode == 0, proc.stderr
    shutil.copytree(FIXTURES / "masters", s / "masters")
    return root


@pytest.fixture
def pilot_set(tmp_path, _pilot_template) -> Path:
    """Set with brief, sample, a generated style spec/summary and the ten redrawn masters (private copy)."""
    root = tmp_path / "w"
    shutil.copytree(_pilot_template, root)
    return root / "icon-work" / "scada-fixture"


def _clone_root(src_root: Path, dst_root: Path) -> Path:
    shutil.copytree(src_root, dst_root)
    return dst_root / "icon-work" / "scada-fixture"


@pytest.fixture(scope="session")
def _exportable_template(tmp_path_factory, _pilot_template) -> Path:
    """Pilot approved by the user, source QA passed: every icon is export-eligible."""
    root = tmp_path_factory.mktemp("exportable-template") / "w"
    s = _clone_root(_pilot_template, root)
    approve_set(s, root.parent, kind="pilot")
    proc = run_script("validate_icons.py", "--set", s, "--phase", "source", "--project-root", ROOT)
    assert proc.returncode == 0, proc.stderr
    return root


@pytest.fixture
def exportable(tmp_path, _exportable_template) -> Path:
    return _clone_root(_exportable_template, tmp_path / "w")


@pytest.fixture(scope="session")
def _exported_template(tmp_path_factory, _exportable_template) -> Path:
    root = tmp_path_factory.mktemp("exported-template") / "w"
    s = _clone_root(_exportable_template, root)
    proc = run_script("export_assets.py", "--set", s)
    assert proc.returncode == 0, proc.stderr
    return root


@pytest.fixture
def exported(tmp_path, _exported_template) -> Path:
    """Eligible set with the default export (160 PNG + 10 inline SVG) already written (private copy)."""
    return _clone_root(_exported_template, tmp_path / "w")


@pytest.fixture
def project_root(tmp_path) -> Path:
    """A throwaway project root with the real lock and installed upstream skills copied in."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(ROOT / "dependencies.lock.json", root / "dependencies.lock.json")
    shutil.copytree(ROOT / ".claude" / "skills" / "icon-set-audit", root / ".claude" / "skills" / "icon-set-audit")
    shutil.copytree(ROOT / ".claude" / "skills" / "icon-set-extend", root / ".claude" / "skills" / "icon-set-extend")
    shutil.copytree(ROOT / ".claude" / "skills" / "icon-set-generator",
                    root / ".claude" / "skills" / "icon-set-generator")
    return root
