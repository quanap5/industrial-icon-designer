#!/usr/bin/env python3
"""Show where a work set is in the workflow: a vertical step timeline, a one-line form, or JSON. Read-only.

    progress.py [--set DIR] [--format vertical|line|json] [--color auto|always|never] [--ascii] [--width N]
    progress.py --from-stdin --format line --color always      (a Claude Code status line command)

Everything is derived from files the other scripts already write (run-state, inventory, brief, style spec,
approvals, manifest, QA and application reports), so it stays correct after the context is compacted or a
new session starts. It writes nothing, installs nothing and uses only the standard library, so it also runs
with a plain python3. Without --set it uses the newest set under ./icon-work.

Colors: green = done, cyan = the step in progress, yellow = waiting for you, red = stopped, gray = not yet.
Exit codes: 0 ok, 2 no set found (never in --from-stdin mode, which prints nothing instead).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import invalidate
import manifest as manifest_mod
import style_spec
from common import EXIT_INPUT, EXIT_OK, ToolError, run_main

STEPS = ["Inventory", "Analyze", "Spec", "Pilot", "Generate", "Export", "Validate", "Maintain"]
GATES = ["meanings resolved", "direction written", "style documents agree", "pilot approval bound to hashes",
         "source QA and approvals", "post-export QA", "application contexts"]

# last valid stage -> (steps done, what the next step is doing)
STAGE_TABLE = {
    "NEW": (0, "running"), "INVENTORIED": (1, "running"), "REFERENCES_ANALYZED": (2, "running"),
    "SPEC_READY": (3, "running"), "PILOT_READY": (3, "waiting"), "PILOT_APPROVED": (4, "running"),
    "GENERATING": (4, "running"), "SOURCE_QA_PASSED": (5, "running"), "EXPORTED": (5, "running"),
    "POST_EXPORT_QA_PASSED": (5, "running"), "ASSETS_READY": (6, "waiting"),
    "APPLICATION_VALIDATED": (7, "running"), "COMPLETE": (8, "complete"),
}
EXCEPTIONAL = {"BLOCKED", "NEEDS_REVIEW", "FAILED"}
NEXT = {
    "NEW": "inventory_icons.py --input <refs> --set <set>",
    "INVENTORIED": "analysis.py brief, sample, audit, then finalize",
    "REFERENCES_ANALYZED": "style_spec.py init, generate, then finalize",
    "SPEC_READY": "redraw the sample, then render_preview.py",
    "PILOT_READY": "ask the user to approve the pilot (approvals.py --type pilot)",
    "PILOT_APPROVED": "batch.py plan",
    "GENERATING": "draw the planned batches, then batch.py done",
    "SOURCE_QA_PASSED": "approve the generated icons, then export_assets.py --dry-run",
    "EXPORTED": "validate_icons.py --phase exported",
    "POST_EXPORT_QA_PASSED": "export the remaining eligible icons",
    "ASSETS_READY": "test in the real application (app_validation.py checklist)",
    "APPLICATION_VALIDATED": "maintain or extend (duplicate_check.py)",
    "COMPLETE": "nothing is pending",
}


# ------------------------------------------------------------------------------------------------ reading
def rj(path: Path):
    """Read JSON without ever raising: a broken or missing file simply shows as unknown."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def exists(set_dir: Path, *rels: str) -> list[str]:
    return [r for r in rels if (set_dir / r).exists()]


def find_set(base: Path) -> tuple[Path, int]:
    """The set directory to show and how many others were found. Newest run-state wins."""
    found = []
    if (base / "run-state.json").is_file():
        found.append(base)
    found += [p.parent for p in sorted((base / "icon-work").glob("*/run-state.json"))]
    if not found:
        raise ToolError(EXIT_INPUT, f"no work set found under {base} (looked for run-state.json and icon-work/*/); "
                        "pass --set DIR")
    found.sort(key=lambda p: (p / "run-state.json").stat().st_mtime, reverse=True)
    return found[0], len(found) - 1


# ------------------------------------------------------------------------------------------------- model
def pilot_verdict(set_dir: Path, latest: dict, spec: dict, brief: dict) -> dict:
    """Is the newest pilot approval still current? The same test as approvals.evaluate, written so it needs no
    schema library: the geometry hash, every approved file's hash, and coverage of the pilot sample."""
    stale: list[str] = []
    uncovered = sorted(set(brief.get("sample_ids") or []) - set(latest.get("scope", [])))
    if uncovered:
        return {"valid": False, "reason": "does not cover the pilot sample: " + ", ".join(uncovered)}
    try:
        if spec and latest.get("style_hash") != style_spec.geometry_hash(spec):
            stale.append("style")
    except KeyError:
        pass
    for icon_id, digest in latest.get("asset_hashes", {}).items():
        if manifest_mod.combined_asset_hash(set_dir, icon_id) != digest:
            stale.append(icon_id)
    if stale:
        return {"valid": False, "reason": "stale: " + ", ".join(stale) + " changed since approval"}
    return {"valid": True, "reason": ""}


def step_details(set_dir: Path, state: dict, stage: str) -> list[dict]:
    inv = rj(set_dir / "inventory.json") or {}
    brief = rj(set_dir / "brief.json") or {}
    spec = rj(set_dir / "style-spec.json") or {}
    manifest = rj(set_dir / "manifest.json") or {}
    audit = rj(set_dir / "reports" / "baseline-audit.json") or {}
    post = rj(set_dir / "reports" / "post-export-qa.json") or {}
    appval = rj(set_dir / "reports" / "application-validation.json") or {}
    icons = inv.get("icons", [])
    out: list[dict] = []

    # 1 Inventory
    d = f"{len(icons)} icons, {len(inv.get('unresolved', []))} need review" if inv else "not started"
    if inv.get("rejected"):
        d += f", {len(inv['rejected'])} rejected"
    out.append({"detail": d, "files": exists(set_dir, "inventory.json")})

    # 2 Analyze
    if brief:
        bits = [str(brief.get("redesign_mode", "?"))]
        if brief.get("sample_ids"):
            bits.append(f"sample {len(brief['sample_ids'])}/{len(icons) or '?'}")
        if audit.get("route") == "native-svg":
            blocking = audit.get("audit", {}).get("summary", {}).get("counts", {}).get("blocking", 0)
            bits.append(f"{blocking} blocking in old SVGs")
        elif audit.get("route"):
            bits.append("PNG visual interpretation")
        d = ", ".join(bits)
    else:
        d = "not started"
    out.append({"detail": d, "files": exists(set_dir, "brief.json", "reports/reference-analysis.md",
                                             "reports/baseline-audit.json")})

    # 3 Spec
    if spec:
        palette = "approved" if spec.get("palette_status") == "approved" else "provisional"
        d = f"grid {spec.get('grid')}, stroke {spec.get('stroke_width')}, palette {palette}"
    else:
        d = "not started"
    out.append({"detail": d, "files": exists(set_dir, "style-spec.json", "icon-style.md")})

    # 4 Pilot
    gate_state, gate_note = "pending", ""
    approvals_doc = rj(set_dir / "approvals.json") or {}
    pilots = [a for a in approvals_doc.get("approvals", []) if a.get("type") == "pilot"]
    if pilots:
        latest = pilots[-1]
        scores = [v for s in latest.get("scores", {}).values() for k, v in s.items() if isinstance(v, (int, float))
                  and not isinstance(v, bool)]
        who = latest.get("reviewer_type", "?")
        d = f"approved by {who}" + (" (not human)" if who == "agent" else "")
        if scores:
            d += f", min score {min(scores):g}/5"
        d += f", {len(latest.get('scope', []))} icons"
        verdict = pilot_verdict(set_dir, latest, spec, brief)
        if verdict["valid"]:
            gate_state = "ok"
        else:
            gate_state, gate_note = "warn", verdict["reason"]
            d += " - STALE"
    elif stage == "PILOT_READY":
        d = "previews ready, waiting for approval"
    else:
        d = "not approved yet"
    out.append({"detail": d, "files": exists(set_dir, "approvals.json", "preview/index.html", "reports/contrast.json"),
                "gate_state": gate_state, "gate_note": gate_note})

    # 5 Generate
    mi = manifest.get("icons", [])
    if mi or state.get("completed_batches") or state.get("pending_ids"):
        eligible = sum(1 for i in mi if i.get("status") == "eligible")
        drawn = {i["id"] for i in mi} | set(pilots[-1].get("scope", []) if pilots else [])
        to_draw = [i for i in state.get("pending_ids", []) if i not in drawn]
        d = (f"{len(state.get('completed_batches', []))} batches done, {len(to_draw)} to draw, "
             f"{eligible}/{len(icons) or len(mi)} eligible")
    else:
        d = "not started"
    out.append({"detail": d, "files": exists(set_dir, "manifest.json", "masters", "reports/pre-export-qa.json")})

    # 6 Export
    kinds: dict[str, int] = {}
    for i in mi:
        for e in i.get("exports", []):
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    if kinds:
        d = f"{kinds.get('desktop-png', 0)} PNG + {kinds.get('web-inline', 0)} SVG"
        if kinds.get("web-img"):
            d += f" + {kinds['web-img']} img SVG"
        summary = post.get("summary")
        d += f", QA {summary['passed']}/{summary['checked']}" if summary else ", QA pending"
    else:
        d = "nothing exported yet"
    out.append({"detail": d, "files": exists(set_dir, "exports", "reports/post-export-qa.json")})

    # 7 Validate (application)
    contexts = appval.get("contexts", [])
    if contexts:
        counts: dict[str, int] = {}
        for c in contexts:
            counts[c["status"]] = counts.get(c["status"], 0) + 1
        d = f"{len(contexts)} contexts: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
    else:
        d = "no application record yet"
    out.append({"detail": d, "files": exists(set_dir, "reports/application-validation.json",
                                             "reports/application-validation-checklist.md")})

    # 8 Maintain
    version = manifest.get("asset_set_version")
    log = set_dir / "reports" / "invalidation-log.jsonl"
    logged = len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0
    d = f"set v{version}, {logged} change(s) logged" if version else "no manifest yet"
    out.append({"detail": d, "files": exists(set_dir, "CHANGELOG.md", "reports/invalidation-log.jsonl")})
    return out


def build_model(set_dir: Path, with_drift: bool = True) -> dict:
    state = rj(set_dir / "run-state.json")
    if not isinstance(state, dict) or "stage" not in state:
        raise ToolError(EXIT_INPUT, "run-state.json is missing or unreadable", str(set_dir / "run-state.json"))
    stage = state["stage"]
    last = state.get("last_valid_stage", stage)
    notes: list[str] = []
    basis = last if stage in EXCEPTIONAL else stage
    if basis not in STAGE_TABLE:
        notes.append(f"unknown stage '{basis}'; shown as NEW")
        basis = "NEW"
    done, kind = STAGE_TABLE[basis]
    if stage in EXCEPTIONAL:
        kind = "failed"
    complete = kind == "complete"
    current = None if complete else min(done, len(STEPS) - 1)
    details = step_details(set_dir, state, stage)
    drift: list[str] = []
    if with_drift:
        try:
            drift = [c["change"] for c in invalidate.detect(set_dir)["changes"]]
        except (ToolError, OSError, KeyError, ValueError, ImportError):
            drift = []  # needs the schema library; without it the pending-changes note is simply left out
    steps = []
    for i, name in enumerate(STEPS):
        status = "done" if i < done else ("current" if i == current else "pending")
        d = details[i]
        step = {"n": i + 1, "name": name, "status": status, "detail": d["detail"], "files": d["files"]}
        if status == "current":
            step["state"] = kind
        if i < len(GATES):
            if status == "done":
                gs, note = d.get("gate_state", "ok"), d.get("gate_note", "")
                gs = "ok" if gs == "pending" else gs
            else:
                gs, note = "pending", ""
            step["gate"] = {"label": GATES[i], "status": gs, "note": note}
        steps.append(step)
    if drift:
        steps[-1]["detail"] += ", pending changes: " + ", ".join(drift)
    nxt = state.get("recovery_action") if kind == "failed" and state.get("recovery_action") else NEXT[basis]
    return {"set_id": state.get("set_id", set_dir.name), "set_dir": str(set_dir), "stage": stage,
            "last_valid_stage": last, "state": kind, "current_step": None if current is None else current + 1,
            "done_steps": done, "total_steps": len(STEPS), "steps": steps, "next": nxt,
            "errors": state.get("errors", [])[-3:], "recovery_action": state.get("recovery_action"),
            "pending_changes": drift, "notes": notes}


# --------------------------------------------------------------------------------------------- rendering
class Style:
    COLORS = {"green": "32", "cyan": "36", "yellow": "33", "red": "31", "gray": "90", "bold": "1"}

    def __init__(self, color: bool, unicode_ok: bool):
        self.color, self.u = color, unicode_ok
        g = (lambda uni, asc: uni if unicode_ok else asc)
        self.done, self.here, self.todo, self.stop = g("●", "[x]"), g("◉", "[>]"), g("○", "[ ]"), g("✖", "[!]")
        self.solid, self.dotted, self.branch = g("┃", "|"), g("┊", ":"), g("╰", "`-")
        self.full, self.empty = g("▰", "#"), g("▱", "-")
        self.ok, self.warn, self.arrow = g("✔", "ok"), g("⚠", "!"), g("◀", "<--")

    def paint(self, name: str, text: str, bold: bool = False) -> str:
        if not self.color:
            return text
        codes = ([self.COLORS["bold"]] if bold else []) + [self.COLORS[name]]
        return f"\033[{';'.join(codes)}m{text}\033[0m"


STATE_COLOR = {"running": "cyan", "waiting": "yellow", "failed": "red"}
STATE_NOTE = {"running": "YOU ARE HERE", "waiting": "WAITING FOR YOU", "failed": "STOPPED HERE"}


def clip(text: str, room: int, st: Style) -> str:
    if room <= 3 or len(text) <= room:
        return text
    return text[: room - (1 if st.u else 3)] + ("…" if st.u else "...")


def cells_for(width: int) -> int:
    """Characters per step in the progress bar, so the header fits narrow terminals."""
    return 4 if width >= 64 else 2 if width >= 48 else 1


def bar(model: dict, st: Style, cells: int = 4) -> str:
    out = ""
    for i in range(model["total_steps"]):
        if i < model["done_steps"]:
            out += st.paint("green", st.full * cells)
        elif i == (model["current_step"] or 0) - 1:
            out += st.paint(STATE_COLOR.get(model["state"], "green"), st.full * cells)
        else:
            out += st.paint("gray", st.empty * cells)
    return out


def render_vertical(model: dict, st: Style, width: int, others: int = 0) -> str:
    cells = cells_for(width)
    tail_room = width - (1 + model["total_steps"] * cells + 1)
    tail = clip(f"{model['done_steps']}/{model['total_steps']} steps  stage {model['stage']}", tail_room, st)
    lines = [st.paint("bold", " INDUSTRIAL ICON DESIGNER", bold=True) + "  "
             + st.paint("gray", clip(model["set_id"], width - 28, st)),
             f" {bar(model, st, cells)} " + st.paint("gray", tail)]
    if others:
        lines.append(" " + st.paint("gray", f"showing the newest of {others + 1} sets; use --set to choose"))
    lines.append("")
    current = model["current_step"]
    for s in model["steps"]:
        n, name, status = s["n"], s["name"], s["status"]
        label = f"{n} {name:<9}"
        edge_color = {"done": "green", "current": STATE_COLOR.get(model["state"], "gray"), "pending": "gray"}[status]
        if status == "done":
            lines.append(" " + st.paint("green", f"{st.done}  {label}") + " " + clip(s["detail"], width - 17, st))
        elif status == "current":
            col = STATE_COLOR[s["state"]]
            glyph = st.stop if s["state"] == "failed" else st.here
            note = f" {st.arrow} {STATE_NOTE[s['state']]} "
            lines.append(" " + st.paint(col, f"{glyph}  {label}", bold=True) + " " + st.paint(col, note, bold=True))
            bar_char = st.dotted if s["state"] == "running" else st.solid
            lines.append(" " + st.paint(col, bar_char) + "     " + clip(s["detail"], width - 8, st))
            if s["state"] == "failed":
                for e in model["errors"][-2:]:
                    lines.append(" " + st.paint("red", st.solid) + "     "
                                 + st.paint("red", clip(f"{e.get('id', '')}: {e.get('message', '')}", width - 8, st)))
            nxt_label = "fix: " if s["state"] == "failed" else "next: "
            lines.append(" " + st.paint(col, bar_char) + "     " + st.paint("gray", clip(nxt_label + model["next"], width - 8, st)))
        else:
            lines.append(" " + st.paint("gray", f"{st.todo}  {n} {name}"))
        if "gate" in s:
            g = s["gate"]
            if status == "done":
                if g["status"] == "warn":
                    text = clip(f"{st.branch} gate {st.warn} {g['label']}: {g['note']}", width - 5, st)
                    lines.append(" " + st.paint("yellow", st.solid) + "   " + st.paint("yellow", text))
                else:
                    lines.append(" " + st.paint("green", st.solid) + "   "
                                 + st.paint("gray", clip(f"{st.branch} gate {st.ok} {g['label']}", width - 5, st)))
            elif status == "current":
                bar_char = st.dotted if s["state"] == "running" else st.solid
                lines.append(" " + st.paint(edge_color, bar_char) + "   "
                             + st.paint("gray", clip(f"{st.branch} gate: {g['label']}", width - 5, st)))
            else:
                lines.append(" " + st.paint("gray", st.dotted))
    for note in model["notes"]:
        lines.append(" " + st.paint("yellow", clip(note, width - 2, st)))
    return "\n".join(lines) + "\n"


def render_line(model: dict, st: Style) -> str:
    current = model["current_step"]
    if current is None:
        return f"{bar(model, st)} {model['done_steps']}/{model['total_steps']} " + st.paint("green", f"{st.ok} complete")
    s = model["steps"][current - 1]
    col = STATE_COLOR[s["state"]]
    glyph = {"running": ">" if not st.u else "▶", "waiting": "||" if not st.u else "⏸", "failed": st.stop}[s["state"]]
    tail = {"running": s["detail"], "waiting": "waiting for you", "failed": "stopped: see logs"}[s["state"]]
    sep = "·" if st.u else "-"
    return f"{bar(model, st)} {model['done_steps']}/{model['total_steps']} " + st.paint(col, f"{glyph} {s['name']}") + " " \
        + st.paint("gray", f"{sep} {tail}")


# ------------------------------------------------------------------------------------------------- entry
def decide_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never" or os.environ.get("NO_COLOR"):
        return False
    return bool(os.environ.get("FORCE_COLOR")) or sys.stdout.isatty()


def decide_unicode(force_ascii: bool) -> bool:
    if force_ascii:
        return False
    enc = (getattr(sys.stdout, "encoding", None) or "").lower().replace("-", "")
    return enc == "utf8"


def status_line_base() -> Path:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        data = {}
    ws = data.get("workspace", {}) if isinstance(data, dict) else {}
    return Path(ws.get("current_dir") or ws.get("project_dir") or data.get("cwd") or ".")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="set_dir")
    ap.add_argument("--format", choices=["vertical", "line", "json"])
    ap.add_argument("--json", action="store_true", help="same as --format json")
    ap.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--ascii", action="store_true", help="plain ASCII symbols instead of Unicode")
    ap.add_argument("--width", type=int)
    ap.add_argument("--from-stdin", action="store_true", help="status line mode: read Claude Code's JSON on stdin")
    args = ap.parse_args()

    fmt = "json" if args.json else (args.format or ("line" if args.from_stdin else "vertical"))
    try:
        if args.from_stdin:
            base = status_line_base()
            set_dir, others = find_set(base)
        elif args.set_dir:
            set_dir, others = Path(args.set_dir), 0
        else:
            set_dir, others = find_set(Path.cwd())
        model = build_model(set_dir, with_drift=fmt != "line")
    except ToolError:
        if args.from_stdin:
            return EXIT_OK  # a status line stays silent where there is nothing to show
        raise
    st = Style(decide_color(args.color), decide_unicode(args.ascii))
    width = args.width or min(shutil.get_terminal_size((80, 24)).columns, 100)
    if fmt == "json":
        print(json.dumps(model, indent=2, sort_keys=True))
    elif fmt == "line":
        print(render_line(model, st))
    else:
        sys.stdout.write(render_vertical(model, st, width, others))
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
