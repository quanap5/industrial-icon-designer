#!/usr/bin/env python3
"""Approval records bound to the style hash and the exact asset hashes.

    approvals.py record --set DIR --type pilot --reviewer user [--ids a,b] [--scores-file FILE] [--note TEXT]
    approvals.py check  --set DIR --type pilot [--json]

The recorded "style hash" is the geometry hash (grid, stroke, caps, joins, padding, small-variant sizes),
so a palette-only change does not void a geometry approval; the palette hash is stored separately and
guards `palette` approvals. A stale approval (style or asset changed since it was recorded) is never accepted.
Agent review is recorded as `agent` and only with --unattended-authorized, which the user must
have explicitly granted; it is never labeled human approval. Pilot approval also needs rubric
scores of at least 4 on every criterion and no semantic defect.
"""
from __future__ import annotations

import argparse
import datetime
import math
from pathlib import Path

import manifest as manifest_mod
import run_state
import style_spec
from common import (EXIT_INPUT, EXIT_OK, EXIT_VALIDATION, ToolError, emit, load_json, run_main, sha256_file,
                    validate_schema, write_json)

CRITERIA = ["meaning", "clarity_16", "balance", "consistency", "contrast"]
MIN_SCORE = 4
SCHEMA_VERSION = "1.0"


def path_for(set_dir: Path) -> Path:
    return Path(set_dir) / "approvals.json"


def load_all(set_dir: Path) -> dict:
    p = path_for(set_dir)
    if not p.exists():
        spec = style_spec.load_spec(set_dir)
        return {"schema_version": SCHEMA_VERSION, "set_id": spec["set_id"], "approvals": []}
    data = load_json(p)
    validate_schema(data, "approvals", str(p))
    return data


def asset_hashes(set_dir: Path, ids: list[str]) -> dict[str, str]:
    """One combined hash per icon over its master and small variant (if any)."""
    out = {}
    for icon_id in ids:
        digest = manifest_mod.combined_asset_hash(set_dir, icon_id)
        if digest is None:
            raise ToolError(EXIT_INPUT, f"no master for '{icon_id}'; draw it before approval",
                            str(Path(set_dir) / "masters" / f"{icon_id}.svg"))
        out[icon_id] = digest
    return out


def scope_ids(set_dir: Path, ids_arg: str | None) -> list[str]:
    if ids_arg == "all":
        inv = load_json(Path(set_dir) / "inventory.json")["icons"]
        return sorted(i["id"] for i in inv if (Path(set_dir) / "masters" / f"{i['id']}.svg").is_file())
    if ids_arg and ids_arg != "pilot":
        return sorted({i.strip() for i in ids_arg.split(",") if i.strip()})
    brief = load_json(Path(set_dir) / "brief.json")
    ids = brief.get("sample_ids")
    if not ids:
        raise ToolError(EXIT_INPUT, "no sample in brief.json; run analysis.py sample or pass --ids")
    return sorted(ids)


def check_scores(path: Path | None, ids: list[str]) -> dict:
    if path is None:
        raise ToolError(EXIT_VALIDATION, "pilot approval needs rubric scores (--scores-file); "
                        "every criterion must be at least 4 with no semantic defect")
    scores = load_json(path)
    problems = []
    for icon_id in ids:
        s = scores.get(icon_id)
        if s is None:
            problems.append(f"{icon_id}: no scores")
            continue
        low = [c for c in CRITERIA if not isinstance(s.get(c), (int, float)) or isinstance(s.get(c), bool)
               or not math.isfinite(s[c]) or not 1 <= s[c] <= 5 or s[c] < MIN_SCORE]
        if low:
            problems.append(f"{icon_id}: below {MIN_SCORE} on {', '.join(low)}")
        if s.get("semantic_defect", False):
            problems.append(f"{icon_id}: semantic defect reported")
    if problems:
        raise ToolError(EXIT_VALIDATION, "rubric not satisfied: " + "; ".join(problems))
    return scores


def record(set_dir: Path, kind: str, reviewer: str, ids: list[str], note: str | None,
           scores_file: Path | None, unattended_authorized: bool) -> dict:
    if reviewer == "agent" and not unattended_authorized:
        raise ToolError(EXIT_VALIDATION, "agent review is not human approval; ask the user to approve, or pass "
                        "--unattended-authorized only if the user explicitly authorized unattended operation")
    spec = style_spec.load_spec(set_dir)
    unresolved = sorted(i["id"] for i in load_json(Path(set_dir) / "inventory.json")["icons"]
                        if i["id"] in ids and i["status"] == "NEEDS_REVIEW")
    if unresolved:
        raise ToolError(EXIT_VALIDATION, "unresolved meaning (NEEDS_REVIEW) cannot be approved: "
                        + ", ".join(unresolved) + "; settle what the icon means first")
    entry = {"type": kind, "reviewer_type": reviewer,
             "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             "scope": ids, "style_hash": style_spec.geometry_hash(spec), "palette_hash": style_spec.palette_hash(spec),
             "asset_hashes": asset_hashes(set_dir, ids)}
    if kind == "pilot":
        entry["scores"] = check_scores(scores_file, ids)
    if note:
        entry["note"] = note
    data = load_all(set_dir)
    data["approvals"].append(entry)
    validate_schema(data, "approvals", str(path_for(set_dir)))
    write_json(path_for(set_dir), data)
    if kind == "pilot":
        run_state.advance(set_dir, spec["set_id"], "PILOT_APPROVED")
    if kind in ("pilot", "batch", "palette"):
        manifest_mod.sync(set_dir)  # visual approval is derived from approvals, bound to current hashes
    return entry


def evaluate(set_dir: Path, kind: str) -> dict:
    """Is there a current, non-stale approval of this type? Never accepts stale hashes."""
    spec = style_spec.load_spec(set_dir)
    current_style = style_spec.geometry_hash(spec)
    data = load_all(set_dir)
    candidates = [a for a in data["approvals"] if a["type"] == kind]
    if not candidates:
        return {"valid": False, "reason": f"no {kind} approval recorded", "stale": []}
    latest = candidates[-1]
    if kind == "pilot":  # the approval must cover the whole pilot sample, not just a few icons
        brief_path = Path(set_dir) / "brief.json"
        sample = set(load_json(brief_path).get("sample_ids") or []) if brief_path.exists() else set()
        uncovered = sorted(sample - set(latest["scope"]))
        if uncovered:
            return {"valid": False, "stale": [], "reviewer_type": latest["reviewer_type"],
                    "reason": "pilot approval does not cover the pilot sample: " + ", ".join(uncovered)}
    stale = []
    if latest["style_hash"] != current_style:
        stale.append("style")
    if kind == "palette" and latest.get("palette_hash") != style_spec.palette_hash(spec):
        stale.append("palette")
    try:
        now = asset_hashes(set_dir, latest["scope"])
    except ToolError as exc:
        return {"valid": False, "reason": exc.message, "stale": ["missing-asset"]}
    stale += [i for i, h in latest["asset_hashes"].items() if now.get(i) != h]
    if stale:
        return {"valid": False, "reason": "approval is stale: " + ", ".join(stale) + " changed since approval",
                "stale": stale, "reviewer_type": latest["reviewer_type"]}
    return {"valid": True, "reason": "current", "stale": [], "reviewer_type": latest["reviewer_type"],
            "scope": latest["scope"]}


def require_valid(set_dir: Path, kind: str = "pilot") -> dict:
    result = evaluate(set_dir, kind)
    if not result["valid"]:
        raise ToolError(EXIT_VALIDATION, f"{kind} approval gate closed: {result['reason']}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--set", dest="set_dir", required=True)
    rec.add_argument("--type", dest="kind", choices=["pilot", "batch", "palette", "style-change"], required=True)
    rec.add_argument("--reviewer", choices=["user", "agent"], required=True)
    rec.add_argument("--ids", help="comma-separated ids, `all` (every icon with a master); default is the pilot sample")
    rec.add_argument("--scores-file")
    rec.add_argument("--note")
    rec.add_argument("--unattended-authorized", action="store_true")
    rec.add_argument("--json", action="store_true")
    chk = sub.add_parser("check")
    chk.add_argument("--set", dest="set_dir", required=True)
    chk.add_argument("--type", dest="kind", default="pilot")
    chk.add_argument("--json", action="store_true")
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    if args.cmd == "record":
        entry = record(set_dir, args.kind, args.reviewer, scope_ids(set_dir, args.ids), args.note,
                       Path(args.scores_file) if args.scores_file else None, args.unattended_authorized)
        emit({"recorded": args.kind, "reviewer_type": entry["reviewer_type"], "scope": entry["scope"]}, args.json,
             f"recorded {args.kind} approval ({entry['reviewer_type']}) for {len(entry['scope'])} icons")
        return EXIT_OK
    result = evaluate(set_dir, args.kind)
    emit(result, args.json, ("valid" if result["valid"] else "closed") + f": {result['reason']}")
    return EXIT_OK if result["valid"] else EXIT_VALIDATION


if __name__ == "__main__":
    run_main(main)
