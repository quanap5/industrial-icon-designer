#!/usr/bin/env python3
"""Stage 3 tooling: style-spec.json is authoritative; icon-style.md carries the explanation.

    style_spec.py init     --set DIR [--set-id ID]      write a provisional style-spec.json
    style_spec.py generate --set DIR                    create/refresh the parameter summary in icon-style.md
    style_spec.py check    --set DIR [--json]           fail (exit 4) when the two documents contradict
    style_spec.py hash     --set DIR                    print the style hash used by approvals
    style_spec.py finalize --set DIR                    check, then advance the run to SPEC_READY

Only the block between the parameter markers is machine-managed; the rest of icon-style.md
(rationale, shared geometry, exceptions, examples) is never overwritten.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import run_state
from common import (EXIT_INPUT, EXIT_OK, EXIT_VALIDATION, ToolError, atomic_write, canonical_hash, emit, load_json,
                    run_main, validate_schema, write_json)

START, END = "<!-- style-params:start -->", "<!-- style-params:end -->"
SCALARS = ["style_version", "grid", "stroke_width", "linecap", "linejoin", "padding", "preview_sizes_px",
           "default_export_sizes_px", "small_variant_sizes_px", "states", "palette_status"]

DEFAULT_SPEC = {
    "schema_version": "1.0", "style_version": "1.0.0", "grid": 24, "stroke_width": 1.5, "linecap": "round",
    "linejoin": "round", "padding": 2, "preview_sizes_px": [16, 20, 24, 32],
    "default_export_sizes_px": [16, 20, 24, 32],
    "themes": {"light": {"background": "#FFFFFF", "normal": "#334155", "disabled": "#94A3B8"},
               "dark": {"background": "#1E293B", "normal": "#E2E8F0", "disabled": "#64748B"}},
    "states": ["normal", "disabled"], "small_variant_sizes_px": [16],
    "palette_status": "provisional_requires_review",
}

TEMPLATE = """# Icon style: {set_id}

{start}
{end}

## Rationale

State why this grid, stroke and palette fit the product and its smallest render size.

## Shared geometry

List recurring parts (arrowheads, badges, gears) and their construction rules.

## Exceptions

Record icons that deviate from the parameters above, with the reason.

## Examples

Reference approved pilot icons here.
"""


PLACEHOLDERS = [
    "State why this grid, stroke and palette fit the product and its smallest render size.",
    "List recurring parts (arrowheads, badges, gears) and their construction rules.",
    "Record icons that deviate from the parameters above, with the reason.",
    "Reference approved pilot icons here.",
]


def spec_path(set_dir: Path) -> Path:
    return set_dir / "style-spec.json"


def md_path(set_dir: Path) -> Path:
    return set_dir / "icon-style.md"


def load_spec(set_dir: Path) -> dict:
    spec = load_json(spec_path(set_dir))
    validate_schema(spec, "style-spec", str(spec_path(set_dir)))
    return spec


def style_hash(spec: dict) -> str:
    return canonical_hash(spec)


GEOMETRY_KEYS = ["grid", "stroke_width", "linecap", "linejoin", "padding", "small_variant_sizes_px"]
STYLE_MODES = ("outline", "filled", "duotone")
DEFAULT_STYLE_MODE = "outline"
DEFAULT_DUOTONE_OPACITY = 0.3


def style_mode(spec: dict) -> str:
    """The drawing mode of the set; a spec written before modes existed is an outline set."""
    return spec.get("style_mode", DEFAULT_STYLE_MODE)


def duotone_opacity(spec: dict) -> float:
    return spec.get("duotone_secondary_opacity", DEFAULT_DUOTONE_OPACITY)


def mode_parameters(spec: dict) -> dict:
    """Mode fields that differ from the defaults. Empty for an outline set, so its hashes match the ones
    computed before modes existed."""
    out = {}
    if style_mode(spec) != DEFAULT_STYLE_MODE:
        out["style_mode"] = style_mode(spec)
    if style_mode(spec) == "duotone":
        out["duotone_secondary_opacity"] = duotone_opacity(spec)
    return out


def geometry_hash(spec: dict) -> str:
    """Hash of everything that changes drawn geometry; palette-only edits leave it unchanged. The drawing form
    and the duotone opacity count as geometry: changing them changes what is drawn, so earlier approvals no
    longer describe the icons."""
    return canonical_hash({**{k: spec[k] for k in GEOMETRY_KEYS}, **mode_parameters(spec)})


def palette_hash(spec: dict) -> str:
    return canonical_hash({"themes": spec["themes"], "palette_status": spec["palette_status"]})


def fmt(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def expected_rows(spec: dict) -> dict[str, str]:
    rows = {k: fmt(spec[k]) for k in SCALARS}
    rows.update({k: fmt(v) for k, v in mode_parameters(spec).items()})
    for theme, tokens in sorted(spec["themes"].items()):
        for token in ("background", "normal", "disabled"):
            rows[f"themes.{theme}.{token}"] = tokens[token].upper()
    return rows


def render_block(spec: dict) -> str:
    lines = [START, "| Parameter | Value |", "|---|---|"]
    lines += [f"| `{k}` | {v} |" for k, v in expected_rows(spec).items()]
    if spec["palette_status"] != "approved":
        lines.append("")
        lines.append("> Palette is provisional and not the official brand palette; it requires review.")
    lines.append(END)
    return "\n".join(lines)


def parse_block(text: str) -> dict[str, str]:
    m = re.search(re.escape(START) + r"(.*?)" + re.escape(END), text, re.S)
    if not m:
        raise ToolError(EXIT_VALIDATION, "parameter summary markers not found in icon-style.md; run generate")
    rows = {}
    for key, value in re.findall(r"^\| `([^`]+)` \| (.*?) \|\s*$", m.group(1), re.M):
        rows[key] = value.strip()
    return rows


def cmd_init(args, set_dir: Path) -> dict:
    p = spec_path(set_dir)
    if p.exists():
        raise ToolError(EXIT_INPUT, "style-spec.json already exists; edit it instead of re-initialising", str(p))
    spec = dict(DEFAULT_SPEC)
    spec["set_id"] = args.set_id or set_dir.resolve().name
    if args.style_mode:  # an explicit mode, even outline, opts the set into strict consistency errors
        spec["style_mode"] = args.style_mode
    validate_schema(spec, "style-spec", str(p))
    write_json(p, spec)
    return {"style_spec": str(p), "palette_status": spec["palette_status"]}


def cmd_generate(args, set_dir: Path) -> dict:
    spec = load_spec(set_dir)
    block = render_block(spec)
    p = md_path(set_dir)
    if p.exists():
        text = p.read_text(encoding="utf-8")
        if START in text and END in text:
            text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
    else:
        text = TEMPLATE.format(set_id=spec["set_id"], start=START, end=END).replace(f"{START}\n{END}", block)
    atomic_write(p, text.encode("utf-8"))
    return {"icon_style": str(p), "style_hash": style_hash(spec)}


def cmd_check(args, set_dir: Path) -> dict:
    spec = load_spec(set_dir)
    p = md_path(set_dir)
    if not p.exists():
        raise ToolError(EXIT_VALIDATION, "icon-style.md missing; run generate", str(p))
    actual = parse_block(p.read_text(encoding="utf-8"))
    expected = expected_rows(spec)
    problems = []
    for key, want in expected.items():
        have = actual.get(key)
        if have is None:
            problems.append({"parameter": key, "json": want, "markdown": None})
        elif have != want:
            problems.append({"parameter": key, "json": want, "markdown": have})
    for key in actual:
        if key not in expected:
            problems.append({"parameter": key, "json": None, "markdown": actual[key]})
    text = p.read_text(encoding="utf-8")
    import consistency  # deferred: consistency reads this module's mode helpers
    return {"consistent": not problems, "contradictions": problems,
            "unfilled_sections": [ph for ph in PLACEHOLDERS if ph in text],
            "consistency": consistency.spec_findings(spec)}


def cmd_finalize(args, set_dir: Path) -> dict:
    result = cmd_check(args, set_dir)
    if not result["consistent"]:
        raise ToolError(EXIT_VALIDATION, "icon-style.md contradicts style-spec.json: "
                        + ", ".join(p["parameter"] for p in result["contradictions"]))
    blocking = [f for f in result["consistency"] if f["severity"] == "error"]
    if blocking:
        raise ToolError(EXIT_VALIDATION, "style spec breaks consistency rules: " + " | ".join(
            f"[{f['rule']}] {f['message']} (suggested: {f['suggested']})" for f in blocking))
    if result["unfilled_sections"]:
        raise ToolError(EXIT_VALIDATION, "icon-style.md still contains template text; write the rationale, shared "
                        "geometry, exceptions and examples first: " + " | ".join(result["unfilled_sections"]))
    spec = load_spec(set_dir)
    run_state.advance(set_dir, spec["set_id"], "SPEC_READY", config_hash=style_hash(spec))
    return {"stage": "SPEC_READY", "style_hash": style_hash(spec)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "generate", "check", "hash", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("--set", dest="set_dir", required=True)
        p.add_argument("--json", action="store_true")
        if name == "init":
            p.add_argument("--set-id")
            p.add_argument("--style-mode", choices=STYLE_MODES)
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    if args.cmd == "hash":
        print(style_hash(load_spec(set_dir)))
        return EXIT_OK
    result = {"init": cmd_init, "generate": cmd_generate, "check": cmd_check, "finalize": cmd_finalize}[args.cmd](
        args, set_dir)
    emit(result, args.json, f"{args.cmd}: " + ", ".join(f"{k}={v}" for k, v in result.items()))
    if args.cmd == "check" and not result["consistent"]:
        for c in result["contradictions"]:
            print(f"contradiction: {c['parameter']}: json={c['json']} markdown={c['markdown']}", file=__import__("sys").stderr)
        return EXIT_VALIDATION
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
