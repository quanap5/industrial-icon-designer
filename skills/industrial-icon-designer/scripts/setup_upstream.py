#!/usr/bin/env python3
"""Explicit setup step: install the three upstream icon-set skills and write the lock file.

This is the only script that writes upstream material. It never runs during ordinary
generation. It verifies the repository origin of a local git clone, copies the instruction
and script files of the three skills into a skills directory, and records the commit SHA
and per-file SHA-256 values in dependencies.lock.json.

    python setup_upstream.py --source /path/to/clone --dest .claude/skills --lock dependencies.lock.json
    python setup_upstream.py --clone /empty/dir --dest .claude/skills --lock dependencies.lock.json
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from common import (EXIT_DEPENDENCY, EXIT_INPUT, ToolError, eprint, resvg_version, run_main, sha256_file,
                    write_json)

ORIGIN = "https://github.com/shadcn-labs/skills"
SKILLS = ("icon-set-generator", "icon-set-extend", "icon-set-audit")
COPY_DIRS = ("references", "scripts")


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ToolError(EXIT_DEPENDENCY, f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def normalize(url: str) -> str:
    url = url.strip().removesuffix(".git").rstrip("/")
    return url.replace("git@github.com:", "https://github.com/")


def collect(skill_src: Path) -> list[Path]:
    files = [skill_src / "SKILL.md"]
    for d in COPY_DIRS:
        base = skill_src / d
        if base.is_dir():
            files += sorted(p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--source", help="existing git clone of shadcn-labs/skills")
    src.add_argument("--clone", help="empty directory to clone into (needs network)")
    ap.add_argument("--dest", default=".claude/skills", help="skills directory to install into")
    ap.add_argument("--lock", default="dependencies.lock.json")
    ap.add_argument("--install-method", default="verified git clone copied by setup_upstream.py")
    args = ap.parse_args()

    if args.clone:
        clone_dir = Path(args.clone)
        if clone_dir.exists() and any(clone_dir.iterdir()):
            raise ToolError(EXIT_INPUT, "clone directory must be empty", str(clone_dir))
        clone_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(["git", "clone", "--depth", "1", ORIGIN + ".git", str(clone_dir)],
                              capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise ToolError(EXIT_DEPENDENCY, f"clone failed: {proc.stderr.strip()}")
        repo = clone_dir
    else:
        repo = Path(args.source)

    if not (repo / ".git").exists():
        raise ToolError(EXIT_INPUT, "not a git clone", str(repo))
    origin = normalize(git(repo, "remote", "get-url", "origin"))
    if origin != ORIGIN:
        raise ToolError(EXIT_DEPENDENCY, f"origin mismatch: expected {ORIGIN}, got {origin}")
    commit = git(repo, "rev-parse", "HEAD")

    dest = Path(args.dest)
    entries = {}
    for name in SKILLS:
        skill_src = repo / "skills" / name
        if not (skill_src / "SKILL.md").is_file():
            raise ToolError(EXIT_DEPENDENCY, f"{name}: SKILL.md missing at commit {commit[:12]}", str(skill_src))
        files = {}
        for f in collect(skill_src):
            rel = f.relative_to(skill_src).as_posix()
            out = dest / name / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, out)
            files[rel] = sha256_file(out)
        entries[name] = {"path": f"skills/{name}", "files": files}
        eprint(f"installed {name}: {len(files)} files")

    license_file = repo / "LICENSE"
    lock = {
        "schema_version": "1.0",
        "upstream": {
            "repository": ORIGIN,
            "commit": commit,
            "license": "MIT",
            "license_sha256": sha256_file(license_file) if license_file.exists() else None,
            "install_method": args.install_method,
            "skills": entries,
        },
        "renderer": {"name": "resvg", "version": resvg_version()},
        "install_dir": dest.as_posix(),
    }
    write_json(Path(args.lock), lock)
    eprint(f"lock written: {args.lock} (commit {commit[:12]})")
    return 0


if __name__ == "__main__":
    run_main(main)
