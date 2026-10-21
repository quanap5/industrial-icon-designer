"""Adapter between the personal contracts and the locked upstream icon-set skills.

Upstream is used only through the interfaces found by inspecting the locked revision:

    audit_icons.py <dir> [--spec FILE] [--json]
    validate_icons.py <dir> [--spec FILE] [--json] [--focus a,b]
    infer_spec.py <dir> [--write] [--out-dir DIR] [--json]

Every call first verifies the installed files against dependencies.lock.json; a mismatch or a
missing skill raises ToolError(EXIT_DEPENDENCY) and the affected phase stays blocked. Nothing here
installs or updates anything.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import EXIT_DEPENDENCY, EXIT_VALIDATION, ToolError, load_json, sha256_file

DEFAULT_CORNER_RADIUS = 2
DEFAULT_MIN_GAP = 4.5


def unlisted_files(root: Path, entry: dict) -> list[str]:
    """Files present in the installed skill that the lock does not know about (they would run unverified)."""
    known = set(entry["files"])
    extra = []
    for base in ("scripts", "references"):
        if (root / base).is_dir():
            for f in sorted((root / base).rglob("*")):
                rel = f.relative_to(root).as_posix()
                if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc" and rel not in known:
                    extra.append(rel)
    return extra


def locate_skill(name: str, project_root: Path, lock: dict) -> Path:
    """Find the installed skill and prove it matches the lock."""
    entry = lock.get("upstream", {}).get("skills", {}).get(name)
    if entry is None:
        raise ToolError(EXIT_DEPENDENCY, f"{name} is not part of the dependency lock")
    bases = [project_root / lock.get("install_dir", ".claude/skills"), project_root / ".claude" / "skills",
             Path.home() / ".claude" / "skills"]
    for base in bases:
        if (base / name / "SKILL.md").is_file():
            root = base / name
            bad = [rel for rel, digest in entry["files"].items()
                   if not (root / rel).is_file() or sha256_file(root / rel) != digest]
            if bad:
                raise ToolError(EXIT_DEPENDENCY, f"{name}: installed files differ from the lock ({bad[0]}); "
                                "phase blocked, rerun setup_upstream.py explicitly")
            extra = unlisted_files(root, entry)
            if extra:
                raise ToolError(EXIT_DEPENDENCY, f"{name}: unlisted file {extra[0]} is not covered by the lock; "
                                "phase blocked, remove it or rerun setup_upstream.py explicitly")
            return root
    raise ToolError(EXIT_DEPENDENCY, f"{name} is not installed; run setup_upstream.py explicitly")


def load_lock(project_root: Path, lock_path: Path | None = None) -> dict:
    path = lock_path or (project_root / "dependencies.lock.json")
    if not Path(path).exists():
        raise ToolError(EXIT_DEPENDENCY, "dependencies.lock.json not found; run setup_upstream.py explicitly")
    return load_json(path)


def to_upstream_spec(style: dict) -> dict:
    """Translate style-spec.json into the upstream style-spec.json shape (no personal fields leak)."""
    return {
        "preset": "custom", "grid": style["grid"], "strokeWidth": style["stroke_width"],
        "padding": style["padding"], "strokeLinecap": style["linecap"], "strokeLinejoin": style["linejoin"],
        "cornerRadius": DEFAULT_CORNER_RADIUS, "minGap": DEFAULT_MIN_GAP, "icons": [],
    }


def stage_svgs(svg_files: list[Path], into: Path) -> Path:
    into.mkdir(parents=True, exist_ok=True)
    for f in svg_files:
        shutil.copyfile(f, into / f.name)
    return into


def run_upstream(skill: str, script: str, directory: Path, project_root: Path, lock: dict,
                 spec: dict | None = None, extra: list[str] | None = None) -> dict:
    """Run one upstream script on a directory and return its parsed --json output."""
    root = locate_skill(skill, project_root, lock)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, "-I", str(root / "scripts" / script), str(Path(directory).resolve())]  # -I: no cwd/script-dir imports
        if spec is not None:
            spec_path = Path(tmp) / "style-spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            cmd += ["--spec", str(spec_path)]
        cmd += ["--json", *(extra or [])]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=tmp)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise ToolError(EXIT_VALIDATION, f"{skill}/{script} produced no JSON (exit {proc.returncode}): "
                        f"{proc.stderr.strip()[:300]}")


def audit_svgs(svg_files: list[Path], project_root: Path, lock: dict, style: dict | None = None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        staged = stage_svgs(svg_files, Path(tmp) / "icons")
        return run_upstream("icon-set-audit", "audit_icons.py", staged, project_root, lock,
                            to_upstream_spec(style) if style else None)


def validate_masters(masters_dir: Path, project_root: Path, lock: dict, style: dict,
                     focus: list[str] | None = None) -> dict:
    extra = ["--focus", ",".join(focus)] if focus else None
    return run_upstream("icon-set-generator", "validate_icons.py", masters_dir, project_root, lock,
                        to_upstream_spec(style), extra)


def infer_style(masters_dir: Path, project_root: Path, lock: dict) -> dict:
    """Recover the specification of an existing set (used before extending it)."""
    return run_upstream("icon-set-extend", "infer_spec.py", masters_dir, project_root, lock)
