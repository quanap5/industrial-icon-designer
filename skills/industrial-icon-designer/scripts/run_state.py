"""Run-state checkpointing: stage tracking, batches, errors, resumable phase.

Normal stages advance in order. Exceptional states (BLOCKED, NEEDS_REVIEW, FAILED) keep
the last valid stage and a recovery action so a run can resume without redoing approved work.
"""
from __future__ import annotations

from pathlib import Path

from common import EXIT_INPUT, ToolError, load_json, validate_schema, write_json

NORMAL_STAGES = [
    "NEW", "INVENTORIED", "REFERENCES_ANALYZED", "SPEC_READY", "PILOT_READY", "PILOT_APPROVED",
    "GENERATING", "SOURCE_QA_PASSED", "EXPORTED", "POST_EXPORT_QA_PASSED", "ASSETS_READY",
    "APPLICATION_VALIDATED", "COMPLETE",
]
EXCEPTIONAL = {"BLOCKED", "NEEDS_REVIEW", "FAILED"}
SCHEMA_VERSION = "1.0"


def path_for(set_dir: Path) -> Path:
    return Path(set_dir) / "run-state.json"


def new_state(set_id: str) -> dict:
    return {"schema_version": SCHEMA_VERSION, "set_id": set_id, "stage": "NEW", "last_valid_stage": "NEW",
            "pending_ids": [], "completed_batches": [], "errors": []}


def load(set_dir: Path, set_id: str | None = None) -> dict:
    p = path_for(set_dir)
    if p.exists():
        state = load_json(p)
        validate_schema(state, "run-state", str(p))
        return state
    if set_id is None:
        raise ToolError(EXIT_INPUT, "run-state.json missing and no set id given", str(p))
    return new_state(set_id)


def save(set_dir: Path, state: dict) -> None:
    validate_schema(state, "run-state", str(path_for(set_dir)))
    write_json(path_for(set_dir), state)


def stage_index(stage: str) -> int:
    return NORMAL_STAGES.index(stage)


def advance(set_dir: Path, set_id: str, stage: str, **fields) -> dict:
    """Move to a normal stage. Never moves backward; use rewind() for invalidation."""
    if stage not in NORMAL_STAGES:
        raise ToolError(EXIT_INPUT, f"not a normal stage: {stage}")
    state = load(set_dir, set_id)
    current = state["last_valid_stage"]
    if stage_index(stage) >= stage_index(current):
        state["stage"] = stage
        state["last_valid_stage"] = stage
    else:
        state["stage"] = current
    state.update(fields)
    state.pop("recovery_action", None)
    save(set_dir, state)
    return state


def rewind(set_dir: Path, stage: str, reason: str) -> dict:
    """Invalidation: go back to an earlier normal stage, keeping history in errors."""
    state = load(set_dir)
    state["stage"] = stage
    state["last_valid_stage"] = stage
    state["errors"].append({"id": "invalidation", "message": reason})
    save(set_dir, state)
    return state


def fail(set_dir: Path, exceptional: str, icon_id: str, message: str, recovery: str,
         resumable_phase: str | None = None) -> dict:
    if exceptional not in EXCEPTIONAL:
        raise ToolError(EXIT_INPUT, f"not an exceptional state: {exceptional}")
    state = load(set_dir)
    state["stage"] = exceptional  # last_valid_stage is intentionally untouched
    state["errors"].append({"id": icon_id, "message": message})
    state["recovery_action"] = recovery
    if resumable_phase:
        state["resumable_phase"] = resumable_phase
    save(set_dir, state)
    return state


def set_pending(set_dir: Path, ids: list[str]) -> dict:
    state = load(set_dir)
    done = {i for b in state["completed_batches"] for i in b["ids"]}
    state["pending_ids"] = sorted(i for i in ids if i not in done)
    save(set_dir, state)
    return state


def record_batch(set_dir: Path, group: str, ids: list[str]) -> dict:
    """Checkpoint a finished batch; completed ids leave the pending list."""
    state = load(set_dir)
    number = len(state["completed_batches"]) + 1
    state["completed_batches"].append({"batch": number, "group": group, "ids": sorted(ids)})
    state["pending_ids"] = [i for i in state["pending_ids"] if i not in set(ids)]
    state["resumable_phase"] = "generate"
    save(set_dir, state)
    return state


def resume_plan(set_dir: Path) -> dict:
    """What a resume must do: only pending ids; completed batches are never regenerated."""
    state = load(set_dir)
    done = [i for b in state["completed_batches"] for i in b["ids"]]
    return {"stage": state["stage"], "last_valid_stage": state["last_valid_stage"],
            "keep": sorted(done), "regenerate": sorted(state["pending_ids"]),
            "recovery_action": state.get("recovery_action")}
