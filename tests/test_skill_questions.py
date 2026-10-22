"""The structured questions the skill asks (references/questions.md) respect the AskUserQuestion limits, are wired
into SKILL.md, point at real scripts and flags, and never let the agent approve on the user's behalf."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "industrial-icon-designer"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
QUESTIONS_MD = (SKILL_DIR / "references" / "questions.md").read_text(encoding="utf-8")
BLOCK = re.search(r"```json\n(.*?)\n```", QUESTIONS_MD, re.S)
POINTS: dict = json.loads(BLOCK.group(1)) if BLOCK else {}

EXPECTED_POINTS = {"setup", "intake", "meaning", "mode", "reinterpret", "style_mode", "grid", "stroke", "pilot", "revise_which",
                   "batch", "export_scope", "drift", "conflict", "palette", "app_access", "contexts", "duplicate"}
RECOMMENDED = " (Recommended)"


def all_questions():
    for point, spec in POINTS.items():
        for q in spec["questions"]:
            yield point, q


def test_the_decision_points_are_the_expected_ones():
    assert set(POINTS) == EXPECTED_POINTS


@pytest.mark.parametrize("point", sorted(EXPECTED_POINTS))
def test_each_call_respects_the_tool_limits(point):
    spec = POINTS[point]
    assert spec["when"].strip(), "say where the question belongs"
    assert 1 <= len(spec["questions"]) <= 4, "1-4 questions per call"
    for q in spec["questions"]:
        assert q["question"].endswith("?"), q["question"]
        assert 0 < len(q["header"]) <= 12, f"header '{q['header']}' is longer than 12 characters"
        assert isinstance(q["multiSelect"], bool)
        assert 2 <= len(q["options"]) <= 4, f"{point}: 2-4 options per question"
        labels = [o["label"] for o in q["options"]]
        assert len(set(labels)) == len(labels), f"{point}: duplicate option labels"
        for o in q["options"]:
            words = o["label"].replace(RECOMMENDED.strip(), "").split()
            assert 1 <= len(words) <= 5, f"label '{o['label']}' should be 1-5 words"
            assert o["description"].strip()
            assert o["label"].strip().lower() not in {"other", "none of the above"}, "the tool adds Other itself"


def test_a_recommended_option_is_first_and_at_most_one_per_question():
    for point, q in all_questions():
        marked = [i for i, o in enumerate(q["options"]) if "(Recommended)" in o["label"]]
        assert len(marked) <= 1, f"{point}: more than one recommendation"
        assert marked in ([], [0]), f"{point}: the recommended option must come first"


def test_question_texts_and_headers_within_a_call_are_distinct():
    for point, spec in POINTS.items():
        headers = [q["header"] for q in spec["questions"]]
        texts = [q["question"] for q in spec["questions"]]
        assert len(set(headers)) == len(headers) and len(set(texts)) == len(texts), point


def test_no_option_lets_the_agent_approve_for_the_user():
    forbidden = re.compile(r"\bagent\b|unattended|auto-?approve|self-?approv|skip (the )?review", re.I)
    for point, q in all_questions():
        for o in q["options"]:
            assert not forbidden.search(o["label"] + " " + o["description"]), f"{point}: {o['label']}"
    assert "never offer \"let the agent approve\"" in QUESTIONS_MD.lower().replace("*", "")


def test_pilot_and_batch_approvals_are_user_decisions_with_a_way_to_say_no():
    for point, approve in (("pilot", "Approve pilot"), ("batch", "Approve all")):
        labels = [o["label"] for o in POINTS[point]["questions"][0]["options"]]
        assert any(l.startswith(approve) for l in labels)
        assert len(labels) >= 3, f"{point}: the user needs revise or change options besides approving"
    assert "only a real answer from the user may be recorded with `--reviewer user`" in QUESTIONS_MD.lower()


def test_skill_md_uses_the_tool_and_links_the_catalog():
    assert "AskUserQuestion" in SKILL
    assert "references/questions.md" in SKILL
    assert "Asking the user" in SKILL
    assert "headless" in SKILL and "brief.json" in SKILL, "the non-interactive fallback is stated"


def test_every_decision_point_is_wired_into_the_workflow():
    for point in EXPECTED_POINTS:
        assert f"`{point}`" in SKILL, f"SKILL.md never tells the agent to ask `{point}`"


def test_every_decision_point_says_what_to_do_with_the_answer():
    table = QUESTIONS_MD.split("## After the answer")[1]
    rows = set(re.findall(r"^\| `(\w+)` \|", table, re.M))
    assert rows == EXPECTED_POINTS


def test_scripts_and_flags_named_in_the_catalog_exist():
    scripts = {p.name for p in (SKILL_DIR / "scripts").glob("*.py")}
    for name in set(re.findall(r"\b([a-z_]+\.py)\b", QUESTIONS_MD)):
        assert name in scripts, f"{name} is not a script of this skill"
    sources = {p.name: p.read_text(encoding="utf-8") for p in (SKILL_DIR / "scripts").glob("*.py")}
    expectations = {
        "export_assets.py": ["--resolve", "--web-img", "--target", "--dry-run"],
        "invalidate.py": ["detect", "--apply"],
        "analysis.py": ["--semantic-approval", "--mode"],
        "approvals.py": ["--reviewer", "--scores-file", "--ids", "--type"],
        "app_validation.py": ["profile", "--remove", "--reason", "evaluate"],
        "render_preview.py": ["--group"],
        "style_spec.py": ["generate", "--style-mode"],
    }
    for script, flags in expectations.items():
        for flag in flags:
            assert flag in sources[script], f"{script} has no {flag}"
            assert flag in QUESTIONS_MD or flag in {"detect", "evaluate", "generate"}, f"{flag} unused"


def test_the_catalog_stays_small_enough_to_load_on_demand():
    assert len(QUESTIONS_MD.splitlines()) < 400
    assert len(SKILL.splitlines()) < 140
