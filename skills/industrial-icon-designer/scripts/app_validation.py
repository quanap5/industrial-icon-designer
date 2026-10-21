#!/usr/bin/env python3
"""Application-context validation: honest records of testing exported assets in the real application.

    app_validation.py init      --set DIR
    app_validation.py profile   --set DIR --remove CONTEXT --reason TEXT      (a removal needs a reason)
    app_validation.py record    --set DIR --context ID --status passed|failed|not-tested --reason TEXT
                                [--env k=v ...] [--icons a,b] [--evidence TEXT] [--themes light,dark]
                                [--states normal,disabled] [--scaling 100,125,150,200]
    app_validation.py evaluate  --set DIR [--complete] [--json]
    app_validation.py checklist --set DIR

A context is `passed` only with environment, evidence, both themes, every supported state and (for
Desktop) display scaling 100/125/150/200% on record, and only while the recorded export hashes still
equal the current exports. Simulations never count. Without application access every context stays
`not-tested` and the set is ASSETS_READY, never APPLICATION_VALIDATED.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import analysis
import manifest as manifest_mod
import run_state
import style_spec
from common import (EXIT_INPUT, EXIT_OK, ToolError, atomic_write, emit, load_json, run_main, validate_schema,
                    write_json)

REPORT = "reports/application-validation.json"
CHECKLIST = "reports/application-validation-checklist.md"
SCALING = [100, 125, 150, 200]
DESKTOP_PLATFORM_KEYS = ("framework",)
WEB_PLATFORM_KEYS = ("browser",)


def report_path(set_dir: Path) -> Path:
    return Path(set_dir) / REPORT


def load_profile(set_dir: Path) -> list[dict]:
    brief_path = Path(set_dir) / "brief.json"
    if brief_path.exists():
        contexts = load_json(brief_path).get("required_contexts")
        if contexts:
            return contexts
    return [{"id": c, "platform": p} for c, p in analysis.DEFAULT_CONTEXTS]


def required(set_dir: Path) -> list[dict]:
    return [c for c in load_profile(set_dir) if not c.get("removed_reason")]


def usage_tokens(context_id: str) -> set[str]:
    return {context_id, context_id.split("-", 1)[-1]}


def expected_icons(set_dir: Path, context_id: str) -> list[str]:
    """Eligible icons whose recorded usage includes this context."""
    manifest = manifest_mod.load(set_dir)
    if manifest is None:
        return []
    tokens = usage_tokens(context_id)
    return sorted(i["id"] for i in manifest["icons"] if i["status"] == "eligible"
                  and tokens & set(i["usage_locations"]))


def current_hashes(set_dir: Path, platform: str, ids: list[str]) -> dict[str, str]:
    """One hash per icon over its current exported files for the platform (changes when any file changes)."""
    import hashlib
    manifest = manifest_mod.load(set_dir)
    kinds = {"desktop-png"} if platform == "desktop" else {"web-inline", "web-img"}
    out = {}
    for icon in (manifest["icons"] if manifest else []):
        if icon["id"] in ids:
            files = sorted((e["path"], e["sha256"]) for e in icon["exports"] if e["kind"] in kinds)
            if files:
                out[icon["id"]] = hashlib.sha256("|".join(f"{p}:{h}" for p, h in files).encode()).hexdigest()
    return out


def load(set_dir: Path) -> dict:
    p = report_path(set_dir)
    if not p.exists():
        raise ToolError(EXIT_INPUT, "application-validation.json missing; run init", str(p))
    data = load_json(p)
    validate_schema(data, "application-validation", str(p))
    return data


def save(set_dir: Path, data: dict) -> None:
    validate_schema(data, "application-validation", str(report_path(set_dir)))
    write_json(report_path(set_dir), data)


def cmd_init(args, set_dir: Path) -> dict:
    if report_path(set_dir).exists():
        raise ToolError(EXIT_INPUT, "application-validation.json already exists", str(report_path(set_dir)))
    spec = style_spec.load_spec(set_dir)
    contexts = [{"context": c["id"], "platform": c["platform"], "status": "not-tested",
                 "reason": "no actual application context has been tested yet", "environment": {},
                 "icon_ids": [], "exported_hashes": {}, "evidence": ""} for c in required(set_dir)]
    save(set_dir, {"schema_version": "1.0", "set_id": spec["set_id"], "profile": "default",
                   "contexts": contexts, "overall": "ASSETS_READY"})
    return {"contexts": len(contexts), "status": "all not-tested"}


def cmd_profile(args, set_dir: Path) -> dict:
    if not (args.reason or "").strip():
        raise ToolError(EXIT_INPUT, "removing a context from the required profile needs an explicit reason; "
                        "it is never counted as passed")
    brief_path = set_dir / "brief.json"
    if not brief_path.exists():
        raise ToolError(EXIT_INPUT, "brief.json missing; run analysis.py brief", str(brief_path))
    brief = load_json(brief_path)
    contexts = brief.get("required_contexts") or [{"id": c, "platform": p} for c, p in analysis.DEFAULT_CONTEXTS]
    hit = [c for c in contexts if c["id"] == args.remove]
    if not hit:
        raise ToolError(EXIT_INPUT, f"unknown context: {args.remove}")
    hit[0]["removed_reason"] = args.reason.strip()
    brief["required_contexts"] = contexts
    analysis.save_brief(set_dir, brief)
    if report_path(set_dir).exists():
        data = load(set_dir)
        data["contexts"] = [c for c in data["contexts"] if c["context"] != args.remove]
        save(set_dir, data)
    return {"removed": args.remove, "reason": args.reason.strip()}


def cmd_record(args, set_dir: Path) -> dict:
    if getattr(args, "simulation", False):
        raise ToolError(EXIT_INPUT, "a simulation is not the actual application and cannot be recorded here")
    profile = {c["id"]: c for c in required(set_dir)}
    if args.context not in profile:
        raise ToolError(EXIT_INPUT, f"'{args.context}' is not a required context (see brief.json)")
    platform = profile[args.context]["platform"]
    env = dict(kv.split("=", 1) for kv in (args.env or []) if "=" in kv)
    ids = sorted({i.strip() for i in (args.icons or "").split(",") if i.strip()})
    themes = sorted({t.strip() for t in (args.themes or "").split(",") if t.strip()})
    states = sorted({t.strip() for t in (args.states or "").split(",") if t.strip()})
    scaling = sorted({int(x) for x in (args.scaling or "").split(",") if x.strip()})
    spec = style_spec.load_spec(set_dir)
    if not args.reason.strip():
        raise ToolError(EXIT_INPUT, "a reason is required")
    hashes = {}
    if args.status != "not-tested":
        hashes = current_hashes(set_dir, platform, ids)
        missing = sorted(set(ids) - set(hashes))
        if not ids or missing:
            raise ToolError(EXIT_INPUT, "tested icon ids must be exported for this platform"
                            + (f" (not exported: {', '.join(missing)})" if missing else ""))
    if args.status == "passed":
        problems = []
        if not env:
            problems.append("environment (--env k=v)")
        need_env = DESKTOP_PLATFORM_KEYS if platform == "desktop" else WEB_PLATFORM_KEYS
        problems += [f"environment key '{k}'" for k in need_env if k not in env]
        if not args.evidence:
            problems.append("evidence (screenshot path or filled manual checklist)")
        if themes != sorted(spec["themes"]):
            problems.append(f"every theme ({', '.join(sorted(spec['themes']))})")
        if states != sorted(spec["states"]):
            problems.append(f"every supported state ({', '.join(sorted(spec['states']))})")
        if platform == "desktop" and scaling != SCALING:
            problems.append("display scaling 100,125,150,200 with the control behavior recorded")
        if problems:
            raise ToolError(EXIT_INPUT, "cannot record 'passed': missing " + "; ".join(problems))
    data = load(set_dir) if report_path(set_dir).exists() else None
    if data is None:
        cmd_init(args, set_dir)
        data = load(set_dir)
    entry = {"context": args.context, "platform": platform, "status": args.status, "reason": args.reason.strip(),
             "environment": env, "icon_ids": ids, "exported_hashes": hashes, "evidence": args.evidence or "",
             "themes": themes, "states": states}
    if platform == "desktop":
        entry["scaling_percent"] = scaling
    data["contexts"] = [c for c in data["contexts"] if c["context"] != args.context] + [entry]
    data["contexts"].sort(key=lambda c: c["context"])
    save(set_dir, data)
    return {"context": args.context, "status": args.status}


def effective(set_dir: Path, ctx: dict) -> tuple[str, str]:
    """Status that still holds now. Evidence goes stale when exports change or new icons join the context."""
    if ctx["status"] != "passed":
        return ctx["status"], ctx["reason"]
    now = current_hashes(set_dir, ctx["platform"], ctx["icon_ids"])
    changed = sorted(i for i in ctx["icon_ids"] if now.get(i) != ctx["exported_hashes"].get(i))
    if changed:
        return "not-tested", "stale evidence: exports changed for " + ", ".join(changed)
    untested = sorted(set(expected_icons(set_dir, ctx["context"])) - set(ctx["icon_ids"]))
    if untested:
        return "not-tested", "icons used in this context were never tested: " + ", ".join(untested)
    return "passed", ctx["reason"]


def cmd_evaluate(args, set_dir: Path) -> dict:
    data = load(set_dir)
    spec_id = data["set_id"]
    req = {c["id"] for c in required(set_dir)}
    rows, changed = [], False
    for ctx in data["contexts"]:
        if ctx["context"] not in req:
            continue
        status, reason = effective(set_dir, ctx)
        if status != ctx["status"]:
            ctx["status"], ctx["reason"], ctx["exported_hashes"] = status, reason, {}
            changed = True
        rows.append({"context": ctx["context"], "status": ctx["status"], "reason": ctx["reason"]})
    recorded = {r["context"] for r in rows}
    for cid in sorted(req - recorded):  # a required context with no record is simply not tested
        rows.append({"context": cid, "status": "not-tested", "reason": "no record"})
    failed = [r["context"] for r in rows if r["status"] == "failed"]
    untested = [r["context"] for r in rows if r["status"] == "not-tested"]
    import invalidate  # local import: invalidate itself uses this module's reset hook
    drift = [c["change"] for c in invalidate.detect(set_dir)["changes"]]
    if failed:
        overall = "NEEDS_REVIEW"
    elif untested or not rows or drift:
        overall = "ASSETS_READY"
    else:
        overall = "APPLICATION_VALIDATED"
    if overall != data["overall"] or changed:
        data["overall"] = overall
        save(set_dir, data)
    claim = overall == "APPLICATION_VALIDATED"
    if claim:
        run_state.advance(set_dir, spec_id, "APPLICATION_VALIDATED")
        if args.complete:
            run_state.advance(set_dir, spec_id, "COMPLETE")
    if claim:
        message = "all required contexts passed on current exports"
    elif not rows:
        message = ("APPLICATION_VALIDATED is not claimed: no required context remains, so nothing was tested "
                   "(restore at least one context in the profile)")
    elif drift and not (failed or untested):
        message = ("APPLICATION_VALIDATED is not claimed: unprocessed changes (" + ", ".join(drift) + ") mean the "
                   "assets are no longer what was tested; run invalidate.py detect --apply, export and retest")
    else:
        message = (f"APPLICATION_VALIDATED is not claimed: {len(untested)} not-tested, {len(failed)} failed "
                   f"of {len(rows)} required contexts")
    return {"overall": overall, "application_validated": claim, "message": message, "pending_changes": drift,
            "required_contexts": len(rows), "not_tested": untested, "failed": failed, "contexts": rows}


def cmd_checklist(args, set_dir: Path) -> dict:
    spec = style_spec.load_spec(set_dir)
    manifest = manifest_mod.load(set_dir)
    if manifest is None:
        raise ToolError(EXIT_INPUT, "manifest.json missing; export first", str(set_dir / "manifest.json"))
    lines = [f"# Application validation checklist: {spec['set_id']}", "",
             "Test the exported assets in the real application. A simulation or preview does not count.",
             "Record each result with `app_validation.py record` (status, reason, environment, evidence).", ""]
    for ctx in required(set_dir):
        ids = expected_icons(set_dir, ctx["id"])
        lines += [f"## {ctx['id']} ({ctx['platform']})", "", f"Icons used here: {', '.join(ids) or 'none recorded'}", ""]
        lines += [f"- [ ] Theme `{t}`, states {', '.join(spec['states'])}" for t in sorted(spec["themes"])]
        if ctx["platform"] == "desktop":
            lines += ["- [ ] Display scaling " + ", ".join(f"{s}%" for s in SCALING)
                      + ": note whether the control picks the right bitmap size, or scales or blurs it",
                      "- [ ] Record framework and control (for example DevExpress 15.1.11, which control)"]
        else:
            lines += ["- [ ] Record browser and version and rendering conditions (zoom, device pixel ratio)"]
        lines += ["- [ ] Icons are the intended ones, not clipped, correct color in each state", ""]
    atomic_write(set_dir / CHECKLIST, ("\n".join(lines) + "\n").encode("utf-8"))
    return {"checklist": str(set_dir / CHECKLIST), "contexts": len(required(set_dir))}


def reset_contexts(set_dir: Path, ids: list[str] | None, reason: str) -> list[str]:
    """Invalidation hook: contexts touching `ids` (all when None) return to not-tested."""
    path = report_path(set_dir)
    if not path.exists():
        return []
    data = load(set_dir)
    reset = []
    for ctx in data["contexts"]:
        if ids is None or set(ctx["icon_ids"]) & set(ids):
            if ctx["status"] != "not-tested":
                ctx["status"] = "not-tested"
                ctx["reason"] = f"invalidated: {reason}"
                ctx["exported_hashes"] = {}
                reset.append(ctx["context"])
    if reset:
        data["overall"] = "ASSETS_READY"
        save(set_dir, data)
    return sorted(reset)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "profile", "record", "evaluate", "checklist"):
        p = sub.add_parser(name)
        p.add_argument("--set", dest="set_dir", required=True)
        p.add_argument("--json", action="store_true")
        if name == "profile":
            p.add_argument("--remove", required=True)
            p.add_argument("--reason")
        if name == "record":
            p.add_argument("--context", required=True)
            p.add_argument("--status", choices=["passed", "failed", "not-tested"], required=True)
            p.add_argument("--reason", required=True)
            p.add_argument("--env", nargs="*")
            p.add_argument("--icons")
            p.add_argument("--evidence")
            p.add_argument("--themes")
            p.add_argument("--states")
            p.add_argument("--scaling")
            p.add_argument("--simulation", action="store_true")
        if name == "evaluate":
            p.add_argument("--complete", action="store_true")
    args = ap.parse_args()
    set_dir = Path(args.set_dir)
    result = {"init": cmd_init, "profile": cmd_profile, "record": cmd_record, "evaluate": cmd_evaluate,
              "checklist": cmd_checklist}[args.cmd](args, set_dir)
    emit(result, args.json, result.get("message") or " ".join(f"{k}={v}" for k, v in result.items()))
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
