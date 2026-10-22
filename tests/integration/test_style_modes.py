"""AT-07 (style spec with modes, consistency rules) and AT-10 (filled variant pairs): spec contract, hash
compatibility, consistency rules and filled variants. The SVGs below are constructed fixtures, not designs."""
from __future__ import annotations

import copy
import json
import shutil

import pytest

import consistency
import style_spec
from common import parse_svg
from conftest import FIXTURES, ROOT, run_json, run_script

# Hashes computed by the code before style modes existed, for tests/fixtures/style-spec.json.
LEGACY_GEOMETRY_HASH = "9d910a8bb62725b8cd8d5ebea81035fd00c7580a4b448d19958573dc15fa1ad5"
LEGACY_STYLE_HASH = "83f191c55da969cd2882d92f656d7de0e43bfa10d6e7cc6b474b7d192b840510"

HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round" ')
OUTLINE = HEAD + 'fill="none" stroke="currentColor"><circle cx="12" cy="12" r="8"/><path d="M12 4v16M4 12h16"/></svg>'
FILLED = HEAD + ('fill="currentColor" stroke="none"><path fill-rule="evenodd" d="M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18Z'
                 'M11 7h2v4h4v2h-4v4h-2v-4H7v-2h4Z"/></svg>')
DUOTONE = HEAD + ('fill="none" stroke="currentColor"><circle cx="12" cy="12" r="8" fill="currentColor" '
                  'fill-opacity="0.3"/><path d="M12 4v16M4 12h16"/></svg>')


@pytest.fixture
def legacy_spec():
    return json.loads((FIXTURES / "style-spec.json").read_text())


def with_mode(spec, mode, **extra):
    return {**copy.deepcopy(spec), "style_mode": mode, **extra}


def icon_findings(svg, spec, mode=None):
    return consistency.icon_findings(parse_svg(svg.encode()), spec, mode)


def rules(findings, severity=None):
    return {f["rule"] for f in findings if severity in (None, f["severity"])}


# ------------------------------------------------------------------ spec contract and hash compatibility

def test_spec_without_a_mode_hashes_as_before(legacy_spec):
    assert style_spec.geometry_hash(legacy_spec) == LEGACY_GEOMETRY_HASH
    assert style_spec.style_hash(legacy_spec) == LEGACY_STYLE_HASH
    assert style_spec.style_mode(legacy_spec) == "outline"


def test_declaring_outline_explicitly_keeps_the_geometry_hash(legacy_spec):
    assert style_spec.geometry_hash(with_mode(legacy_spec, "outline")) == LEGACY_GEOMETRY_HASH


def test_other_modes_change_the_geometry_hash(legacy_spec):
    filled = style_spec.geometry_hash(with_mode(legacy_spec, "filled"))
    duo_30 = style_spec.geometry_hash(with_mode(legacy_spec, "duotone", duotone_secondary_opacity=0.3))
    duo_40 = style_spec.geometry_hash(with_mode(legacy_spec, "duotone", duotone_secondary_opacity=0.4))
    assert len({LEGACY_GEOMETRY_HASH, filled, duo_30, duo_40}) == 4


def test_a_palette_only_change_does_not_change_the_geometry_hash(legacy_spec):
    spec = with_mode(legacy_spec, "filled")
    recolored = copy.deepcopy(spec)
    recolored["themes"]["light"]["normal"] = "#112233"
    assert style_spec.geometry_hash(recolored) == style_spec.geometry_hash(spec)


@pytest.mark.parametrize("patch", [{"style_mode": "gradient"}, {"duotone_secondary_opacity": 1.5},
                                   {"consistency_overrides": {"stroke-min-at-smallest": {}}}])
def test_schema_rejects_invalid_mode_fields(legacy_spec, patch):
    from common import ToolError, validate_schema
    with pytest.raises(ToolError):
        validate_schema({**legacy_spec, **patch}, "style-spec", "spec")


def test_init_writes_a_mode_only_when_one_is_requested(tmp_path):
    outline, filled = tmp_path / "a", tmp_path / "b"
    assert run_script("style_spec.py", "init", "--set", outline).returncode == 0
    assert run_script("style_spec.py", "init", "--set", filled, "--style-mode", "filled").returncode == 0
    assert "style_mode" not in json.loads((outline / "style-spec.json").read_text())
    assert json.loads((filled / "style-spec.json").read_text())["style_mode"] == "filled"


def test_generated_style_summary_lists_the_mode_and_checks_clean(tmp_path):
    set_dir = tmp_path / "duo"
    run_script("style_spec.py", "init", "--set", set_dir, "--style-mode", "duotone")
    assert run_script("style_spec.py", "generate", "--set", set_dir).returncode == 0
    assert "| `style_mode` | duotone |" in (set_dir / "icon-style.md").read_text()
    proc, data = run_json("style_spec.py", "check", "--set", set_dir)
    assert proc.returncode == 0 and data["consistent"] is True and data["consistency"] == []


# ------------------------------------------------------------------ spec-level rules

def test_thin_stroke_is_an_error_when_the_mode_is_declared_and_a_warning_otherwise(legacy_spec):
    thin = {**legacy_spec, "stroke_width": 1.0}
    legacy = consistency.spec_findings(thin)
    declared = consistency.spec_findings({**thin, "style_mode": "outline"})
    assert [(f["rule"], f["severity"]) for f in legacy] == [("stroke-min-at-smallest", "warning")]
    assert [(f["rule"], f["severity"]) for f in declared] == [("stroke-min-at-smallest", "error")]
    assert declared[0]["suggested"] == "stroke_width 1.5"


def test_the_default_stroke_passes_and_filled_sets_ignore_the_stroke_rule(legacy_spec):
    assert consistency.spec_findings(legacy_spec) == []
    assert consistency.spec_findings(with_mode(legacy_spec, "filled", stroke_width=0.5)) == []


def test_duotone_opacity_outside_the_range_is_an_error_with_a_clamped_suggestion(legacy_spec):
    found = consistency.spec_findings(with_mode(legacy_spec, "duotone", duotone_secondary_opacity=0.8))
    assert [(f["rule"], f["suggested"]) for f in found if f["severity"] == "error"] == [
        ("duotone-opacity-range", "duotone_secondary_opacity 0.5")]


def test_a_secondary_layer_too_faint_for_its_background_is_reported_with_a_working_opacity(legacy_spec):
    spec = with_mode(legacy_spec, "duotone", duotone_secondary_opacity=0.2)
    found = [f for f in consistency.spec_findings(spec) if f["rule"] == "duotone-secondary-contrast"]
    assert found and all(f["severity"] == "error" for f in found), "a declared mode gives errors"
    suggestions = [f["suggested"] for f in found]
    assert all(sg.startswith("duotone_secondary_opacity ") or sg == "a darker or lighter normal token"
               for sg in suggestions)
    for sg in suggestions:
        if sg.startswith("duotone_secondary_opacity"):
            assert 0.2 <= float(sg.rsplit(" ", 1)[1]) <= 0.5, "a suggestion must not trigger the range rule"


def test_an_override_with_a_reason_replaces_the_limit_and_is_listed(legacy_spec):
    thin = {**legacy_spec, "style_mode": "outline", "stroke_width": 1.0}
    thin["consistency_overrides"] = {"stroke-min-at-smallest": {"reason": "16 px uses small variants", "value": 0.5}}
    assert consistency.spec_findings(thin) == []
    assert consistency.overrides(thin) == [{"rule": "stroke-min-at-smallest", "reason": "16 px uses small variants"}]


def test_finalize_refuses_a_spec_with_error_findings(tmp_path):
    set_dir = tmp_path / "thin"
    run_script("style_spec.py", "init", "--set", set_dir, "--style-mode", "outline")
    path = set_dir / "style-spec.json"
    spec = json.loads(path.read_text())
    spec["stroke_width"] = 1.0
    path.write_text(json.dumps(spec))
    run_script("style_spec.py", "generate", "--set", set_dir)
    proc = run_script("style_spec.py", "finalize", "--set", set_dir)
    assert proc.returncode == 4 and "stroke-min-at-smallest" in proc.stderr


# ------------------------------------------------------------------ icon-level rules

@pytest.mark.parametrize("mode,svg", [("outline", OUTLINE), ("filled", FILLED), ("duotone", DUOTONE)])
def test_each_mode_accepts_its_own_construction(legacy_spec, mode, svg):
    assert icon_findings(svg, with_mode(legacy_spec, mode)) == []


@pytest.mark.parametrize("mode,svg,rule", [
    ("outline", FILLED, "mode-matches-spec"),
    ("filled", OUTLINE, "mode-matches-spec"),
    ("filled", DUOTONE, "mode-matches-spec"),
    ("duotone", OUTLINE, "mode-matches-spec"),
    ("duotone", FILLED, "mode-matches-spec"),
])
def test_a_master_built_for_another_mode_is_an_error_with_a_suggestion(legacy_spec, mode, svg, rule):
    found = icon_findings(svg, with_mode(legacy_spec, mode))
    assert rule in rules(found, "error") and all(f["suggested"] for f in found)


def test_mode_mismatch_is_only_a_warning_for_a_spec_that_never_declared_a_mode(legacy_spec):
    found = icon_findings(FILLED, legacy_spec)
    assert rules(found, "error") == set() and rules(found, "warning") == {"mode-matches-spec"}


def test_outline_icons_may_keep_small_filled_parts(legacy_spec):
    dotted = OUTLINE.replace("</svg>", '<circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>')
    assert icon_findings(dotted, with_mode(legacy_spec, "outline")) == []


def test_duotone_layers_must_use_the_set_opacity(legacy_spec):
    off = DUOTONE.replace('fill-opacity="0.3"', 'fill-opacity="0.45"')
    found = icon_findings(off, with_mode(legacy_spec, "duotone", duotone_secondary_opacity=0.3))
    assert [(f["rule"], f["suggested"]) for f in found] == [("duotone-opacity-consistent", 'fill-opacity="0.3"')]


def test_a_knockout_painted_in_a_background_color_is_rejected_by_source_qa(pilot_set):
    cheat = FILLED.replace("</svg>", '<circle cx="12" cy="12" r="3" fill="#ffffff"/></svg>')
    (pilot_set / "masters" / "pump.svg").write_text(cheat)
    proc, report = run_json("validate_icons.py", "--set", pilot_set, "--phase", "source", "--project-root", ROOT)
    assert proc.returncode == 4
    assert any("fixed fill color" in e for e in report["icons"]["pump"]["errors"])


# ------------------------------------------------------------------ source QA with modes and variant pairs

def validate(set_dir):
    return run_json("validate_icons.py", "--set", set_dir, "--phase", "source", "--project-root", ROOT)


def add_variant(set_dir, base="valve"):
    return run_json("variants.py", "add", "--set", set_dir, "--base", base)


def test_an_outline_set_validates_exactly_as_before(pilot_set):
    proc, report = validate(pilot_set)
    assert proc.returncode == 0 and report["summary"] == {"checked": 10, "passed": 10, "failed": 0}
    assert report["style_mode"] == "outline" and report["consistency"] == {"spec": [], "overrides": []}


def test_a_filled_variant_is_registered_as_a_state_paired_with_its_base(pilot_set):
    proc, data = add_variant(pilot_set)
    assert proc.returncode == 0 and data["added"] == "valve-filled"
    inv = {i["id"]: i for i in json.loads((pilot_set / "inventory.json").read_text())["icons"]}
    variant = inv["valve-filled"]
    assert (variant["variant_of"], variant["variant_kind"], variant["semantic_role"]) == ("valve", "filled", "state")
    assert variant["references"] == inv["valve"]["references"]


def test_adding_the_same_variant_twice_or_a_variant_of_a_variant_is_refused(pilot_set):
    assert add_variant(pilot_set)[0].returncode == 0
    assert add_variant(pilot_set)[0].returncode == 4
    assert add_variant(pilot_set, "valve-filled")[0].returncode == 2
    assert add_variant(pilot_set, "no-such-icon")[0].returncode == 2


def test_duplicate_check_treats_the_variant_flag_as_the_only_way_past_the_base(pilot_set):
    inv = {i["id"]: i for i in json.loads((pilot_set / "inventory.json").read_text())["icons"]}
    args = ["--set", pilot_set, "--id", "valve-filled", "--meaning", inv["valve"]["meaning"],
            "--group", inv["valve"]["functional_group"]]
    assert run_script("duplicate_check.py", *args).returncode == 4
    assert run_script("duplicate_check.py", *args, "--variant-of", "valve").returncode == 0
    assert run_script("duplicate_check.py", *args, "--variant-of", "missing").returncode == 2


@pytest.mark.skipif(shutil.which("resvg") is None, reason="needs the pinned renderer")
def test_a_filled_variant_in_an_outline_set_passes_source_qa_and_is_in_the_manifest(pilot_set):
    (pilot_set / "masters" / "valve.svg").write_text(OUTLINE)
    add_variant(pilot_set)
    (pilot_set / "masters" / "valve-filled.svg").write_text(FILLED)
    proc, report = validate(pilot_set)
    assert proc.returncode == 0, report["icons"]["valve-filled"]
    assert report["icons"]["valve-filled"]["status"] == "passed"
    entry = {i["id"]: i for i in json.loads((pilot_set / "manifest.json").read_text())["icons"]}["valve-filled"]
    assert (entry["variant_of"], entry["variant_kind"]) == ("valve", "filled")


@pytest.mark.skipif(shutil.which("resvg") is None, reason="needs the pinned renderer")
def test_a_filled_variant_that_drifts_from_its_base_box_fails_with_the_base_box_as_suggestion(pilot_set):
    (pilot_set / "masters" / "valve.svg").write_text(OUTLINE)
    add_variant(pilot_set)
    small = HEAD + 'fill="currentColor" stroke="none"><circle cx="12" cy="12" r="5"/></svg>'
    (pilot_set / "masters" / "valve-filled.svg").write_text(small)
    proc, report = validate(pilot_set)
    assert proc.returncode == 4
    errors = report["icons"]["valve-filled"]["errors"]
    assert any("variant-bounds-parity" in e and "suggested: match the base box" in e for e in errors), errors


def test_a_variant_without_its_base_master_fails(pilot_set):
    add_variant(pilot_set)
    (pilot_set / "masters" / "valve.svg").unlink()
    (pilot_set / "masters" / "valve-filled.svg").write_text(FILLED)
    proc, report = validate(pilot_set)
    assert any("masters/valve.svg does not exist" in e for e in report["icons"]["valve-filled"]["errors"])


def test_a_filled_variant_drawn_as_an_outline_fails_even_in_an_outline_set(pilot_set):
    (pilot_set / "masters" / "valve.svg").write_text(OUTLINE)
    add_variant(pilot_set)
    (pilot_set / "masters" / "valve-filled.svg").write_text(OUTLINE)
    proc, report = validate(pilot_set)
    assert proc.returncode == 4
    assert any("filled icon has no currentColor fill" in e for e in report["icons"]["valve-filled"]["errors"])


# ------------------------------------------------------------------ review fixes: crashes and bypasses

@pytest.mark.parametrize("raw,ok", [("30%", True), ("0.3", True), ("abc", False), ("1.5", False), ("-0.2", False)])
def test_fill_opacity_is_parsed_and_an_unreadable_one_is_a_finding_not_a_crash(legacy_spec, raw, ok):
    svg = DUOTONE.replace('fill-opacity="0.3"', f'fill-opacity="{raw}"')
    found = icon_findings(svg, with_mode(legacy_spec, "duotone", duotone_secondary_opacity=0.3))
    if ok:
        assert found == []
    else:
        assert any("not a number between 0 and 1" in f["message"] for f in found)


@pytest.mark.parametrize("override", [
    {"duotone-opacity-range": {"reason": "x", "value": 0.3}},
    {"duotone-opacity-range": {"reason": "x", "value": [0.5, 0.2]}},
    {"stroke-min-at-smallest": {"reason": "x", "value": "2"}},
    {"stroke-min-at-smallest": {"reason": "x", "value": -1}},
    {"no-such-rule": {"reason": "x", "value": 1}},
])
def test_a_bad_override_is_refused_cleanly(legacy_spec, override, tmp_path):
    from common import ToolError
    with pytest.raises(ToolError):
        consistency.spec_findings({**legacy_spec, "consistency_overrides": override})
    set_dir = tmp_path / "ov"
    run_script("style_spec.py", "init", "--set", set_dir, "--style-mode", "duotone")
    path = set_dir / "style-spec.json"
    spec = json.loads(path.read_text())
    spec["consistency_overrides"] = override
    path.write_text(json.dumps(spec))
    run_script("style_spec.py", "generate", "--set", set_dir)
    proc = run_script("style_spec.py", "check", "--set", set_dir)
    assert proc.returncode == 2 and "Traceback" not in proc.stderr


def test_a_valid_override_range_replaces_the_default(legacy_spec):
    spec = with_mode(legacy_spec, "duotone", duotone_secondary_opacity=0.7)
    assert "duotone-opacity-range" in rules(consistency.spec_findings(spec))
    spec["consistency_overrides"] = {"duotone-opacity-range": {"reason": "bold style", "value": [0.2, 0.8]}}
    assert "duotone-opacity-range" not in rules(consistency.spec_findings(spec))


@pytest.mark.parametrize("mode,svg", [
    ("duotone", DUOTONE.replace('fill-opacity="0.3"', 'style="fill-opacity:0.3"')),
    ("duotone", DUOTONE.replace('fill-opacity="0.3"', 'opacity="0.3"')),
    ("outline", OUTLINE.replace("<circle", '<circle opacity="0.5"')),
])
def test_opacity_set_the_hidden_way_is_reported(legacy_spec, mode, svg):
    found = icon_findings(svg, with_mode(legacy_spec, mode, duotone_secondary_opacity=0.3))
    assert any("not read by these checks" in f["message"] for f in found)


def test_a_filled_master_with_a_path_that_has_no_fill_is_reported(legacy_spec):
    sloppy = HEAD + 'stroke="none"><path d="M4 4h16v16H4z"/></svg>'
    found = icon_findings(sloppy, with_mode(legacy_spec, "filled"))
    assert any("no fill and would paint black" in f["message"] for f in found)
    assert icon_findings(FILLED, with_mode(legacy_spec, "filled")) == []


def test_the_inventory_schema_ties_variant_of_to_variant_kind(pilot_set):
    from common import ToolError, validate_schema
    doc = json.loads((pilot_set / "inventory.json").read_text())
    entry = {**next(i for i in doc["icons"] if i["id"] == "valve"), "id": "valve-filled", "variant_of": "valve"}
    doc["icons"].append(entry)
    with pytest.raises(ToolError):
        validate_schema(doc, "inventory", "inventory.json")
    entry["variant_kind"] = "filled"
    validate_schema(doc, "inventory", "inventory.json")


def test_duplicate_check_does_not_crash_on_a_variant_entry_without_a_kind(pilot_set):
    path = pilot_set / "inventory.json"
    inv = json.loads(path.read_text())
    sample = next(i for i in inv["icons"] if i["id"] == "valve")
    inv["icons"].append({**sample, "id": "valve-filled", "variant_of": "valve"})
    path.write_text(json.dumps(inv))
    proc = run_script("duplicate_check.py", "--set", pilot_set, "--id", "valve-other", "--meaning", "other",
                      "--variant-of", "valve")
    assert proc.returncode == 4 and "Traceback" not in proc.stderr


@pytest.mark.parametrize("variant_of,message", [
    ("../../../etc/passwd", "is not an icon id"),
    ("pump", None),
    ("not-in-inventory", "is not in the inventory"),
])
def test_an_untrusted_variant_of_is_rejected_by_source_qa(pilot_set, variant_of, message):
    path = pilot_set / "inventory.json"
    inv = json.loads(path.read_text())
    sample = next(i for i in inv["icons"] if i["id"] == "valve")
    inv["icons"].append({**sample, "id": "valve-filled", "variant_of": variant_of, "variant_kind": "filled"})
    path.write_text(json.dumps(inv))
    (pilot_set / "masters" / "valve-filled.svg").write_text(FILLED)
    proc, report = validate(pilot_set)
    errors = report["icons"]["valve-filled"]["errors"]
    if message:
        assert any(message in e for e in errors), errors
    else:  # a real icon id is accepted as a base; the drawing still has to match it
        assert not any("variant_of" in e for e in errors), errors


def test_a_variant_of_itself_or_of_a_variant_is_rejected(pilot_set):
    path = pilot_set / "inventory.json"
    inv = json.loads(path.read_text())
    sample = next(i for i in inv["icons"] if i["id"] == "valve")
    inv["icons"] += [{**sample, "id": "valve-filled", "variant_of": "valve-filled", "variant_kind": "filled"},
                     {**sample, "id": "pump-filled", "variant_of": "valve-filled", "variant_kind": "filled"}]
    path.write_text(json.dumps(inv))
    for name in ("valve-filled", "pump-filled"):
        (pilot_set / "masters" / f"{name}.svg").write_text(FILLED)
    proc, report = validate(pilot_set)
    assert any("names the icon itself" in e for e in report["icons"]["valve-filled"]["errors"])
    assert any("is itself a variant" in e for e in report["icons"]["pump-filled"]["errors"])
