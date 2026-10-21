"""AT-26: the whole pipeline runs from a clean checkout without an application repo or private assets."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import ROOT, run_json

# a "clean checkout": only what ships with the project, none of docs/, plans/, logos/ or the dev environment
SHIPPED = ["skills", ".claude", "dependencies.lock.json", "tests/fixtures", "examples/build_demo.py",
           "examples/pilot-review.json"]


def tree(path: Path) -> dict[str, str]:
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file()}


def test_at26_clean_checkout_runs_the_synthetic_pipeline(tmp_path):
    checkout = tmp_path / "checkout"
    for rel in SHIPPED:
        src = ROOT / rel
        dst = checkout / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy(src, dst)
    assert not (checkout / "docs").exists() and not (checkout / "logos").exists()

    out = tmp_path / "scada-demo"
    proc = subprocess.run([sys.executable, str(checkout / "examples" / "build_demo.py"), "--out", str(out),
                           "--review", str(checkout / "examples" / "pilot-review.json")],
                          capture_output=True, text=True, check=False, cwd=checkout)
    assert proc.returncode == 0, proc.stderr + proc.stdout

    set_dir = out / "icon-work" / "scada-demo"
    state = json.loads((set_dir / "run-state.json").read_text())
    assert state["stage"] == "ASSETS_READY" and state["errors"] == []
    manifest = json.loads((set_dir / "manifest.json").read_text())
    assert [i["status"] for i in manifest["icons"]] == ["eligible"] * 10
    assert len(list((set_dir / "exports" / "desktop").rglob("*.png"))) == 160
    assert len(list((set_dir / "exports" / "web").glob("*.svg"))) == 10

    # honest statuses: synthetic, agent-reviewed, nothing tested in a real application
    approval = json.loads((set_dir / "approvals.json").read_text())["approvals"][0]
    assert approval["reviewer_type"] == "agent" and "not human approval" in approval["note"]
    app = json.loads((set_dir / "reports" / "application-validation.json").read_text())
    assert app["overall"] == "ASSETS_READY" and {c["status"] for c in app["contexts"]} == {"not-tested"}
    inventory = json.loads((set_dir / "inventory.json").read_text())
    assert all(i.get("fixture") for i in inventory["icons"]), "fixtures stay labeled as fixtures"

    # the same toolchain says the set is healthy and nothing has drifted
    doctor = subprocess.run([sys.executable, str(checkout / "skills" / "industrial-icon-designer" / "scripts" / "doctor.py"),
                             "--set", str(set_dir), "--project-root", str(checkout), "--json"],
                            capture_output=True, text=True, check=False, cwd=checkout)
    assert doctor.returncode == 0, doctor.stdout
    drift = subprocess.run([sys.executable, str(checkout / "skills" / "industrial-icon-designer" / "scripts" / "invalidate.py"),
                            "detect", "--set", str(set_dir), "--json"], capture_output=True, text=True, check=False)
    assert json.loads(drift.stdout)["changes"] == []

    # timings are logged apart from the assets
    names = [json.loads(line)["name"] for line in (set_dir / "reports" / "timing-log.jsonl").read_text().splitlines()]
    assert names == ["preview-render", "qa-source", "export", "qa-exported"]

    # reproducible: the committed example equals a fresh build, byte for byte
    committed = ROOT / "examples" / "scada-demo" / "icon-work" / "scada-demo"
    for part in ("masters", "variants", "exports", "style-spec.json", "icon-style.md", "manifest.json", "inventory.json"):
        a, b = committed / part, set_dir / part
        assert (tree(a) == tree(b)) if a.is_dir() else (a.read_bytes() == b.read_bytes()), part


def test_committed_demo_set_is_healthy_and_labeled_synthetic():
    set_dir = ROOT / "examples" / "scada-demo" / "icon-work" / "scada-demo"
    proc, data = run_json("doctor.py", "--set", set_dir, "--project-root", ROOT)
    assert proc.returncode == 0 and data["ok"]
    assert "synthetic" in (ROOT / "examples" / "scada-demo" / "README.md").read_text().lower()
    assert "not human approval" in (set_dir / "approvals.json").read_text()
