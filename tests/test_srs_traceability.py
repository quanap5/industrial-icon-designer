"""SRS 9.3: every requirement is covered by an acceptance test or the inspection list, and every
acceptance test exists in this suite."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRS = (ROOT / "docs" / "SRS.md").read_text(encoding="utf-8")
TESTS = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests").rglob("test_*.py"))
ID = r"(?:FR-[A-Z]+-\d+|SEC-\d+|NFR-\d+|DR-\d+)"


def section(start: str, end: str) -> str:
    return SRS[SRS.index(start):SRS.index(end)]


def defined_ids() -> list[str]:
    return re.findall(rf"^\| ({ID}) \|", SRS, re.M)


def test_requirement_ids_are_unique():
    ids = defined_ids()
    assert len(ids) > 80 and len(ids) == len(set(ids))


def test_every_requirement_is_in_the_traceability_table_or_the_inspection_list():
    trace = section("### 9.3 Traceability", "## 10. Delivery")
    missing = [i for i in defined_ids() if not re.search(rf"\b{re.escape(i)}\b", trace)]
    assert missing == []


def test_traceability_references_only_defined_requirements_and_tests():
    trace = section("### 9.3 Traceability", "## 10. Delivery")
    referenced = set(re.findall(rf"\b{ID}\b", trace))
    assert referenced <= set(defined_ids())
    table_ats = set(re.findall(r"^\| (AT-\d+) \|", trace, re.M))
    declared_ats = set(re.findall(r"^\| (AT-\d+) \|", section("### 9.2 Acceptance tests", "### 9.3 Traceability"), re.M))
    assert table_ats == declared_ats and len(declared_ats) == 26


def test_every_acceptance_test_has_an_automated_test_here():
    ats = re.findall(r"^\| (AT-\d+) \|", section("### 9.2 Acceptance tests", "### 9.3 Traceability"), re.M)
    missing = [a for a in ats if not re.search(rf"^def test_at{a[3:]}_", TESTS, re.M)]
    assert missing == []


def test_inspection_only_requirements_are_stated_in_the_srs():
    trace = section("### 9.3 Traceability", "## 10. Delivery")
    assert "SEC-07, SEC-08" in trace.split("Requirements verified by inspection only")[1]
