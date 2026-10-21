#!/usr/bin/env python3
"""Functional batch generation: plan 5-10 icon batches per group and checkpoint each one.

    batch.py plan   --set DIR [--json]                     open only with a valid pilot approval
    batch.py done   --set DIR --group G --ids a,b          validate masters, then record the checkpoint
    batch.py status --set DIR [--json]

Batches never mix functional groups. A group with fewer than 5 pending icons becomes one smaller
batch, flagged `undersized`. Icons whose meaning is unresolved (NEEDS_REVIEW) are blocked, never planned.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import approvals
import run_state
import validate_icons
from common import EXIT_INPUT, EXIT_OK, EXIT_VALIDATION, ToolError, emit, load_json, run_main

MIN_BATCH, MAX_BATCH = 5, 10


def chunk(ids: list[str]) -> list[list[str]]:
    """Split one group into batches of 5-10 as evenly as possible (a group below 5 stays whole)."""
    if len(ids) <= MAX_BATCH:
        return [ids]
    n = math.ceil(len(ids) / MAX_BATCH)
    base, extra = divmod(len(ids), n)
    out, i = [], 0
    for k in range(n):
        size = base + (1 if k < extra else 0)
        out.append(ids[i:i + size])
        i += size
    return out


def pending_by_group(set_dir: Path) -> tuple[dict[str, list[str]], list[str]]:
    inv = load_json(set_dir / "inventory.json")
    state = run_state.load(set_dir)
    gate = approvals.require_valid(set_dir, "pilot")
    done = {i for b in state["completed_batches"] for i in b["ids"]} | set(gate["scope"])
    groups: dict[str, list[str]] = {}
    blocked = []
    for icon in inv["icons"]:
        if icon["id"] in done:
            continue
        if icon["status"] == "NEEDS_REVIEW":
            blocked.append(icon["id"])
        else:
            groups.setdefault(icon["functional_group"], []).append(icon["id"])
    return {g: sorted(v) for g, v in sorted(groups.items())}, sorted(blocked)


def plan(set_dir: Path) -> dict:
    groups, blocked = pending_by_group(set_dir)
    state = run_state.load(set_dir)
    number = len(state["completed_batches"]) + 1
    batches = []
    for group, ids in groups.items():
        for part in chunk(ids):
            batches.append({"batch": number, "group": group, "ids": part, "undersized": len(part) < MIN_BATCH})
            number += 1
    set_id = state["set_id"]
    run_state.advance(set_dir, set_id, "GENERATING")
    run_state.set_pending(set_dir, [i for ids in groups.values() for i in ids])
    return {"batches": batches, "blocked_needs_review": blocked}


def done(set_dir: Path, group: str, ids: list[str], project_root: Path, lock: Path | None) -> dict:
    if not ids:
        raise ToolError(EXIT_INPUT, "no ids given")
    if len(set(ids)) != len(ids):
        raise ToolError(EXIT_INPUT, "duplicate ids in batch")
    if len(ids) > MAX_BATCH:
        raise ToolError(EXIT_INPUT, f"a batch holds at most {MAX_BATCH} icons")
    groups, _ = pending_by_group(set_dir)
    pending = groups.get(group, [])
    outside = sorted(set(ids) - set(pending))
    if outside:
        raise ToolError(EXIT_INPUT, f"not pending in group '{group}': {', '.join(outside)}")
    if len(ids) < MIN_BATCH and len(ids) != len(pending):
        raise ToolError(EXIT_INPUT, f"a batch needs {MIN_BATCH}-{MAX_BATCH} icons unless it finishes the group "
                        f"({len(pending)} pending in '{group}')")
    missing = [i for i in ids if not (set_dir / "masters" / f"{i}.svg").is_file()]
    if missing:
        raise ToolError(EXIT_INPUT, f"no master drawn for: {', '.join(missing)}")
    report = validate_icons.validate_source(set_dir, project_root, lock, ids)
    if report.get("blocked"):
        raise ToolError(3, f"source QA blocked: {report['blocked']}")
    failed = sorted(i for i, r in report["icons"].items() if r["status"] == "failed")
    if failed:
        raise ToolError(EXIT_VALIDATION, "source QA failed for: " + ", ".join(failed) + "; batch not recorded")
    state = run_state.record_batch(set_dir, group, ids)
    if not state["pending_ids"]:
        # the last checkpoint closes generation: QA every master once more so the run can advance
        final = validate_icons.validate_source(set_dir, project_root, lock, None)
        if final.get("blocked"):
            raise ToolError(3, f"final source QA blocked: {final['blocked']}")
        failing = sorted(i for i, r in final["icons"].items() if r["status"] == "failed")
        if failing:
            raise ToolError(EXIT_VALIDATION, "the batch was recorded, but final source QA failed for "
                            + ", ".join(failing) + "; fix them before generation can finish")
    return {"recorded_batch": state["completed_batches"][-1], "pending": len(state["pending_ids"])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "done", "status"):
        p = sub.add_parser(name)
        p.add_argument("--set", dest="set_dir", required=True)
        p.add_argument("--json", action="store_true")
        if name == "done":
            p.add_argument("--group", required=True)
            p.add_argument("--ids", required=True)
            p.add_argument("--project-root", default=".")
            p.add_argument("--lock")
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    if args.cmd == "plan":
        result = plan(set_dir)
    elif args.cmd == "done":
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
        result = done(set_dir, args.group, ids, Path(args.project_root).resolve(),
                      Path(args.lock) if args.lock else None)
    else:
        result = run_state.resume_plan(set_dir)
    emit(result, args.json, " ".join(f"{k}={v}" for k, v in result.items()))
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
