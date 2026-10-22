#!/usr/bin/env python3
"""Declare the filled variant of an outline icon in the inventory.

    variants.py add --set DIR --base ICON-ID [--json]

The variant is its own inventory entry (`<base>-filled`, role `state`, meaning "<base meaning> (selected)")
so drawing, approval, export and invalidation treat it like any icon. It shares the base's references and
sizes, records `variant_of` / `variant_kind`, and is judged as a filled icon whatever the set's style mode.
Exit codes: 0 added, 2 bad input, 4 the variant duplicates something.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path

import duplicate_check
from common import (EXIT_INPUT, EXIT_OK, EXIT_VALIDATION, ToolError, emit, load_json, run_main, validate_schema,
                    write_json)

SUFFIX = "-filled"


def add_filled_variant(set_dir: Path, base_id: str) -> dict:
    path = Path(set_dir) / "inventory.json"
    inv = load_json(path)
    base = next((i for i in inv["icons"] if i["id"] == base_id), None)
    if base is None:
        raise ToolError(EXIT_INPUT, f"{base_id} is not in the inventory", str(path))
    if base.get("variant_of"):
        raise ToolError(EXIT_INPUT, f"{base_id} is itself a variant; add the variant to its base")
    new_id = base_id + SUFFIX
    meaning = f"{base['meaning']} (selected)"
    check = duplicate_check.check(set_dir, new_id, meaning, base["functional_group"], "state", base_id)
    if not check["ok"]:
        raise ToolError(EXIT_VALIDATION, "variant duplicates an existing icon: "
                        + ", ".join(d["id"] for d in check["duplicates"]))
    entry = copy.deepcopy(base)
    entry.update({"id": new_id, "meaning": meaning, "semantic_role": "state", "variant_of": base_id,
                  "variant_kind": "filled"})
    inv["icons"] = sorted(inv["icons"] + [entry], key=lambda i: i["id"])
    validate_schema(inv, "inventory", str(path))
    write_json(path, inv)
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("--set", dest="set_dir", required=True)
    add.add_argument("--base", required=True)
    add.add_argument("--json", action="store_true")
    args = ap.parse_args()
    entry = add_filled_variant(Path(args.set_dir), args.base)
    emit({"added": entry["id"], "variant_of": entry["variant_of"]}, args.json,
         f"added {entry['id']} as the filled variant of {entry['variant_of']}")
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
