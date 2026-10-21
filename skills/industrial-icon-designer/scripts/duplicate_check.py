#!/usr/bin/env python3
"""Check a proposed icon for a duplicate meaning before it is added to an existing set.

    duplicate_check.py --set DIR --id NEW-ID --meaning "Open historical trend view" [--group G] [--role R]

An exact id or meaning match, or a near-identical meaning in the same functional group, is a
duplicate (exit 4). Similar but distinct meanings are listed as warnings. An action and a state
(`device-connect` versus `device-connected`) are different meanings by design.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import EXIT_OK, EXIT_VALIDATION, emit, kebab_id, load_json, run_main

STOP = {"a", "an", "the", "to", "of", "and", "or", "for", "in", "on", "open", "show", "view", "current", "selected"}
DUPLICATE_AT, SIMILAR_AT = 0.8, 0.5


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


def check(set_dir: Path, new_id: str, meaning: str, group: str | None, role: str | None) -> dict:
    inv = load_json(Path(set_dir) / "inventory.json")["icons"]
    nid = kebab_id(new_id)
    duplicates, similar = [], []
    for icon in inv:
        if icon["id"].lower() == nid:
            duplicates.append({"id": icon["id"], "reason": "same id (case-insensitive)", "score": 1.0})
            continue
        score = similarity(meaning, icon["meaning"])
        same_group = group is None or icon["functional_group"] == group
        same_role = role is None or icon["semantic_role"] == role
        if role is not None and not same_role:
            continue  # an action and a state of the same thing are different icons
        if score == 1.0 or (score >= DUPLICATE_AT and same_group):
            duplicates.append({"id": icon["id"], "reason": f"same meaning as '{icon['meaning']}'", "score": round(score, 2)})
        elif score >= SIMILAR_AT:
            similar.append({"id": icon["id"], "reason": f"similar to '{icon['meaning']}'", "score": round(score, 2)})
    return {"id": nid, "duplicates": duplicates, "similar": similar, "ok": not duplicates}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="set_dir", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--meaning", required=True)
    ap.add_argument("--group")
    ap.add_argument("--role", choices=["action", "state", "object", "navigation"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = check(Path(args.set_dir), args.id, args.meaning, args.group, args.role)
    emit(result, args.json, ("duplicate meaning: " + ", ".join(d["id"] for d in result["duplicates"])) if not result["ok"]
         else "no duplicate meaning" + (f" ({len(result['similar'])} similar)" if result["similar"] else ""))
    return EXIT_OK if result["ok"] else EXIT_VALIDATION


if __name__ == "__main__":
    run_main(main)
