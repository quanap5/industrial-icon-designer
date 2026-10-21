#!/usr/bin/env python3
"""Stage 2 tooling: redesign mode, representative sample, baseline SVG audit, analysis report.

    analysis.py brief    --set DIR [--mode normalize|redraw|reinterpret] [--semantic-approval]
    analysis.py sample   --set DIR
    analysis.py audit    --set DIR [--project-root DIR]
    analysis.py finalize --set DIR

`finalize` refuses to advance while the proposed-direction section is still the pending marker,
so the report always contains a real direction before the set reaches REFERENCES_ANALYZED.
"""
from __future__ import annotations

import argparse
import re
from itertools import zip_longest
from pathlib import Path

import run_state
import upstream_adapter
from common import (EXIT_INPUT, EXIT_OK, ToolError, atomic_write, emit, load_json, run_main, validate_schema,
                    write_json)

SCHEMA_VERSION = "1.0"
PENDING_MARKER = "<!-- direction:pending -->"
DEFAULT_CONTEXTS = [
    ("desktop-toolbar", "desktop"), ("desktop-ribbon", "desktop"), ("desktop-menu", "desktop"),
    ("desktop-device-list", "desktop"), ("web-navigation", "web"), ("web-actions", "web"), ("web-list", "web"),
]
MAX_SAMPLE, MIN_SAMPLE = 12, 8


def read_inventory(set_dir: Path) -> dict:
    inv = load_json(set_dir / "inventory.json")
    validate_schema(inv, "inventory", str(set_dir / "inventory.json"))
    return inv


def load_brief(set_dir: Path, set_id: str) -> dict:
    p = set_dir / "brief.json"
    if p.exists():
        return load_json(p)
    return {"schema_version": SCHEMA_VERSION, "set_id": set_id, "redesign_mode": "redraw",
            "required_contexts": [{"id": c, "platform": p} for c, p in DEFAULT_CONTEXTS]}


def save_brief(set_dir: Path, brief: dict) -> None:
    validate_schema(brief, "brief", str(set_dir / "brief.json"))
    write_json(set_dir / "brief.json", brief)


def complexity(icon: dict, set_dir: Path) -> int:
    ref = icon["references"][0]
    path = (set_dir / ref["path"]).resolve()
    if ref["kind"] == "svg" and path.exists():
        return sum(len(d) for d in re.findall(r'\bd="([^"]*)"', path.read_text(encoding="utf-8", errors="ignore")))
    return path.stat().st_size if path.exists() else 0


def select_sample(icons: list[dict], set_dir: Path) -> tuple[list[str], str | None]:
    """8-12 representatives covering groups and roles; fewer than 8 icons: all, with a recorded exception."""
    ids = [i["id"] for i in icons]
    if len(icons) <= MAX_SAMPLE:
        exception = None
        if len(icons) < MIN_SAMPLE:
            exception = f"only {len(icons)} icons available (fewer than {MIN_SAMPLE}); all reviewed"
        return sorted(ids), exception
    by_group: dict[str, list[dict]] = {}
    for icon in icons:
        by_group.setdefault(icon["functional_group"], []).append(icon)
    queues = []
    for group in sorted(by_group):
        ordered = sorted(by_group[group], key=lambda i: (complexity(i, set_dir), i["id"]))
        spread, lo, hi = [], 0, len(ordered) - 1  # alternate simple and dense, keeping roles varied
        while lo <= hi:
            spread.append(ordered[lo])
            if lo != hi:
                spread.append(ordered[hi])
            lo, hi = lo + 1, hi - 1
        queues.append(spread)
    chosen: list[str] = []
    for row in zip_longest(*queues):
        for icon in row:
            if icon is not None and len(chosen) < MAX_SAMPLE:
                chosen.append(icon["id"])
    return sorted(chosen), None


def cmd_brief(args, set_dir: Path) -> dict:
    inv = read_inventory(set_dir)
    brief = load_brief(set_dir, inv["set_id"])
    if args.mode == "reinterpret" and not args.semantic_approval:
        raise ToolError(EXIT_INPUT, "reinterpret changes the visual metaphor and needs explicit semantic "
                        "approval (--semantic-approval); ask for clarification before choosing it")
    brief["redesign_mode"] = args.mode
    brief["semantic_approval"] = bool(args.semantic_approval)
    save_brief(set_dir, brief)
    return {"redesign_mode": args.mode, "brief": str(set_dir / "brief.json")}


def cmd_sample(args, set_dir: Path) -> dict:
    inv = read_inventory(set_dir)
    brief = load_brief(set_dir, inv["set_id"])
    ids, exception = select_sample(inv["icons"], set_dir)
    brief["sample_ids"] = ids
    if exception:
        brief["sample_exception"] = exception
    else:
        brief.pop("sample_exception", None)
    save_brief(set_dir, brief)
    return {"sample_ids": ids, "exception": exception}


def cmd_audit(args, set_dir: Path) -> dict:
    inv = read_inventory(set_dir)
    root = Path(args.project_root).resolve()
    svgs = []
    for icon in inv["icons"]:
        for ref in icon["references"]:
            if ref["kind"] == "svg":
                svgs.append((set_dir / ref["path"]).resolve())
    reports = set_dir / "reports"
    if svgs:
        lock = upstream_adapter.load_lock(root, Path(args.lock) if args.lock else None)
        audit = upstream_adapter.audit_svgs(svgs, root, lock)
        baseline = {"route": "native-svg", "tool": "icon-set-audit", "commit": lock["upstream"]["commit"],
                    "audit": audit}
    else:
        baseline = {"route": "png-visual-interpretation", "tool": None,
                    "note": "no SVG references; PNG references are interpreted visually and labeled as such"}
    write_json(reports / "baseline-audit.json", baseline)

    brief = load_brief(set_dir, inv["set_id"])
    sample = brief.get("sample_ids") or select_sample(inv["icons"], set_dir)[0]
    by_id = {i["id"]: i for i in inv["icons"]}
    lines = [f"# Reference analysis: {inv['set_id']}", "",
             f"Redesign mode: **{brief['redesign_mode']}**", "",
             f"## Sample ({len(sample)} of {len(inv['icons'])})", "",
             "| ID | Meaning | Group | Role | Reference | Interpretation |", "|---|---|---|---|---|---|"]
    for sid in sample:
        i = by_id[sid]
        kinds = "+".join(r["kind"] for r in i["references"])
        method = "native SVG geometry" if i["references"][0]["kind"] == "svg" else "visual interpretation (PNG)"
        lines.append(f"| {sid} | {i['meaning']} | {i['functional_group']} | {i['semantic_role']} | {kinds} | {method} |")
    if brief.get("sample_exception"):
        lines += ["", f"Sample exception: {brief['sample_exception']}"]
    lines += ["", "## Current inconsistencies", ""]
    if svgs:
        counts = baseline["audit"]["summary"]["counts"]
        lines.append(f"Baseline audit of {len(svgs)} SVG reference(s): "
                     + ", ".join(f"{n} {sev}" for sev, n in sorted(counts.items())) + ".")
        for name, items in sorted(baseline["audit"]["findings"].items()):
            for f in items[:2]:
                lines.append(f"- `{name}`: {f['message']}")
    else:
        lines.append("No SVG references. Inconsistencies in PNG references are visual interpretations and must be "
                     "confirmed during the pilot before/after review.")
    unresolved = inv.get("unresolved", [])
    if unresolved:
        lines += ["", "## Unresolved meanings", "", "Resolve before approval: " + ", ".join(unresolved)]
    lines += ["", "## Proposed direction", "", PENDING_MARKER,
              "Replace this marker with the proposed direction and its rationale.", ""]
    atomic_write(reports / "reference-analysis.md", "\n".join(lines).encode("utf-8"))
    return {"baseline": baseline["route"], "svg_references": len(svgs),
            "report": str(reports / "reference-analysis.md")}


def cmd_finalize(args, set_dir: Path) -> dict:
    inv = read_inventory(set_dir)
    report = set_dir / "reports" / "reference-analysis.md"
    if not report.exists():
        raise ToolError(EXIT_INPUT, "reference-analysis.md missing; run audit first", str(report))
    if PENDING_MARKER in report.read_text(encoding="utf-8"):
        raise ToolError(EXIT_INPUT, "proposed direction is still the pending marker; write it first", str(report))
    brief = load_brief(set_dir, inv["set_id"])
    if not brief.get("sample_ids"):
        raise ToolError(EXIT_INPUT, "no sample recorded; run sample first", str(set_dir / "brief.json"))
    run_state.advance(set_dir, inv["set_id"], "REFERENCES_ANALYZED")
    return {"stage": "REFERENCES_ANALYZED"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("brief", "sample", "audit", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("--set", dest="set_dir", required=True)
        p.add_argument("--project-root", default=".")
        p.add_argument("--lock")
        p.add_argument("--json", action="store_true")
        if name == "brief":
            p.add_argument("--mode", choices=["normalize", "redraw", "reinterpret"], default="redraw")
            p.add_argument("--semantic-approval", action="store_true")
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    result = {"brief": cmd_brief, "sample": cmd_sample, "audit": cmd_audit, "finalize": cmd_finalize}[args.cmd](
        args, set_dir)
    emit(result, args.json, f"{args.cmd}: " + ", ".join(f"{k}={v}" for k, v in result.items()))
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
