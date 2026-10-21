#!/usr/bin/env python3
"""Capability and dependency check. Reads state, installs nothing.

    python doctor.py --json
    python doctor.py --set ./icon-work/scada --json [--lock dependencies.lock.json]

Exit codes: 0 ok, 2 input/configuration, 3 dependency problem, 4 invalid set artifact.
"""
from __future__ import annotations

import argparse
import importlib
import shutil
from importlib import metadata
import subprocess
import sys
from pathlib import Path

import upstream_adapter
from common import (EXIT_DEPENDENCY, EXIT_OK, EXIT_VALIDATION, PACKAGE_DIR, ToolError, emit, load_json,
                    resvg_version, run_main, sha256_file, validate_schema)

# artifact file -> schema name
SET_ARTIFACTS = {
    "brief.json": "brief",
    "inventory.json": "inventory",
    "style-spec.json": "style-spec",
    "manifest.json": "manifest",
    "run-state.json": "run-state",
    "approvals.json": "approvals",
    "reports/application-validation.json": "application-validation",
}

# which phases a failed check blocks
BLOCKS = {
    "python": ["all"],
    "packages": ["all"],
    "renderer": ["pilot", "export"],
    "upstream": ["pilot", "generate", "extend", "audit"],
}


def check(name: str, status: str, detail: str, **extra) -> dict:
    return {"name": name, "status": status, "detail": detail, **extra}


def check_python() -> dict:
    ok = sys.version_info >= (3, 11)
    return check("python", "ok" if ok else "fail", f"Python {sys.version.split()[0]} (need >=3.11)")


def check_packages() -> list[dict]:
    out = []
    for mod, label in (("PIL", "Pillow"), ("jsonschema", "jsonschema"), ("defusedxml", "defusedxml")):
        try:
            importlib.import_module(mod)
            try:
                version = metadata.version(label)
            except metadata.PackageNotFoundError:
                version = "present"
            out.append(check("packages", "ok", f"{label} {version}", package=label))
        except ImportError:
            out.append(check("packages", "fail", f"{label} missing; install from requirements.lock", package=label))
    return out


def check_renderer(lock: dict | None) -> dict:
    try:
        version = resvg_version()
    except ToolError as exc:
        return check("renderer", "fail", exc.message)
    pinned = (lock or {}).get("renderer", {}).get("version")
    if pinned and pinned != version:
        return check("renderer", "fail", f"resvg {version} differs from locked {pinned}; "
                     "raster outputs and visual checks are invalidated", renderer="resvg", version=version)
    return check("renderer", "ok", f"resvg {version}" + (" (matches lock)" if pinned else " (no lock recorded)"),
                 renderer="resvg", version=version)


def find_skill_dirs(lock: dict, project_root: Path) -> list[Path]:
    candidates = []
    declared = lock.get("install_dir")
    if declared:
        candidates.append(project_root / declared)
    candidates += [project_root / ".claude" / "skills", Path.home() / ".claude" / "skills"]
    return candidates


def check_upstream(lock: dict | None, project_root: Path) -> list[dict]:
    if not lock:
        return [check("upstream", "fail", "dependencies.lock.json not found; run setup_upstream.py explicitly")]
    up = lock.get("upstream", {})
    out = []
    for name, entry in up.get("skills", {}).items():
        located = None
        for base in find_skill_dirs(lock, project_root):
            if (base / name / "SKILL.md").is_file():
                located = base / name
                break
        if located is None:
            out.append(check("upstream", "fail", f"{name} not installed", skill=name))
            continue
        changed = [rel for rel, digest in entry["files"].items()
                   if not (located / rel).is_file() or sha256_file(located / rel) != digest]
        extra = upstream_adapter.unlisted_files(located, entry)
        if extra and not changed:
            out.append(check("upstream", "fail", f"{name}: unlisted file {extra[0]} is not covered by the lock; "
                             "remove it or rerun setup explicitly", skill=name))
            continue
        if changed:
            out.append(check("upstream", "fail",
                             f"{name}: {len(changed)} file(s) differ from the lock ({changed[0]}); "
                             "no silent substitution, rerun setup explicitly", skill=name))
        else:
            out.append(check("upstream", "ok", f"{name} matches lock at {up.get('commit', '?')[:12]}", skill=name))
    return out


def check_discovery(project_root: Path) -> dict:
    skill_md = PACKAGE_DIR / "SKILL.md"
    if not skill_md.is_file():
        return check("skill-discovery", "fail", "SKILL.md missing in package")
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\nname: industrial-icon-designer\n" not in text:
        return check("skill-discovery", "fail", "SKILL.md frontmatter missing name: industrial-icon-designer")
    for base in (project_root / ".claude" / "skills", Path.home() / ".claude" / "skills"):
        installed = base / "industrial-icon-designer"
        if installed.exists():
            return check("skill-discovery", "ok", f"installed at {installed}")
    return check("skill-discovery", "warn", "package valid but not installed under .claude/skills; "
                 "link or copy skills/industrial-icon-designer to enable discovery")


def check_claude_version() -> dict:
    exe = shutil.which("claude")
    if not exe:
        return check("claude-code", "warn", "claude CLI not on PATH; version not recorded")
    proc = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
    return check("claude-code", "ok", (proc.stdout or proc.stderr).strip())


def check_set(set_dir: Path) -> list[dict]:
    out = []
    if not set_dir.is_dir():
        return [check("set", "fail", f"set directory not found: {set_dir}")]
    for rel, schema in SET_ARTIFACTS.items():
        path = set_dir / rel
        if not path.exists():
            continue
        try:
            validate_schema(load_json(path), schema, str(path))
            out.append(check("set", "ok", f"{rel} valid"))
        except ToolError as exc:
            out.append(check("set", "fail", str(exc)))
    if not out:
        out.append(check("set", "ok", "empty set directory"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="set_dir")
    ap.add_argument("--lock", default="dependencies.lock.json")
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    lock_path = Path(args.lock)
    if not lock_path.is_absolute():
        lock_path = root / lock_path
    lock = load_json(lock_path) if lock_path.exists() else None

    checks = [check_python(), *check_packages(), check_renderer(lock), *check_upstream(lock, root),
              check_discovery(root), check_claude_version()]
    if args.set_dir:
        checks += check_set(Path(args.set_dir))

    blocked = sorted({p for c in checks if c["status"] == "fail" for p in BLOCKS.get(c["name"], [])})
    set_failed = any(c["name"] == "set" and c["status"] == "fail" for c in checks)
    dep_failed = any(c["status"] == "fail" and c["name"] in BLOCKS for c in checks)

    result = {"ok": not (dep_failed or set_failed), "blocked_phases": blocked, "checks": checks}
    emit(result, args.json)
    if not args.json:
        for c in checks:
            print(f"[{c['status']:>4}] {c['name']}: {c['detail']}")
        if blocked:
            print("blocked phases:", ", ".join(blocked))
    if dep_failed:
        return EXIT_DEPENDENCY
    if set_failed:
        return EXIT_VALIDATION
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
