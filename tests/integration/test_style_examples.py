"""The style examples under examples/: their inputs are complete and the committed sets match what the pipeline
reported (a full rebuild is slow and is done with `python examples/build_style_examples.py`)."""
from __future__ import annotations

import json
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "examples"))
import build_style_examples as examples  # noqa: E402

TEN = {"add", "alarm-list", "device-connect", "network", "open-folder", "pump", "save", "settings", "trend-chart",
       "valve"}
MODES = {"filled": "filled", "duotone": "duotone", "outline-bold": "outline", "selected-states": "outline",
         "badged": "outline"}
BADGED = {"pump-add", "valve-remove", "network-add", "device-connected", "save-done", "alarm-list-clear"}


def expected_ids(ex):
    """The ids an example draws: its own metadata when it brings its own icons, else the shared ten."""
    if ex.get("metadata"):
        return {i["id"] for i in json.loads(ex["metadata"].read_text())["icons"]}
    return TEN


def set_dir(key):
    return ROOT / "examples" / f"scada-{key}" / "icon-work" / f"scada-{key}"


def test_every_example_has_a_set_of_ten_masters_and_a_complete_agent_review():
    for key, ex in examples.EXAMPLES.items():
        masters = ex["masters"] or ROOT / "tests" / "fixtures" / "masters"
        ids = expected_ids(ex)
        assert {p.stem for p in masters.glob("*.svg")} == ids, key
        scores = json.loads(ex["review"].read_text())
        assert set(scores) == ids, key
        if ex.get("references"):
            assert {p.stem for p in ex["references"].glob("*.svg")} == ids, key
        for small in (ex["small"].glob("*.svg") if ex.get("small") else ()):
            assert small.stem in ids, (key, small.name)
        for icon, s in scores.items():
            assert all(s[c] >= 4 for c in ("meaning", "clarity_16", "balance", "consistency", "contrast")), (key, icon)
            assert s["semantic_defect"] is False and s["note"].strip(), (key, icon)
        assert set(ex["prose"]) == set(examples.PLACEHOLDERS), key
        for base in ex.get("variants", ()):
            assert (ex["variant_masters"] / f"{base}.svg").is_file(), (key, base)


@pytest.mark.parametrize("key", sorted(MODES))
def test_the_committed_example_set_reached_assets_ready_in_its_mode(key):
    d = set_dir(key)
    assert json.loads((d / "style-spec.json").read_text()).get("style_mode") == MODES[key]
    assert json.loads((d / "run-state.json").read_text())["last_valid_stage"] == "ASSETS_READY"
    source = json.loads((d / "reports" / "pre-export-qa.json").read_text())
    exported = json.loads((d / "reports" / "post-export-qa.json").read_text())
    assert source["summary"]["failed"] == 0 and exported["summary"]["failed"] == 0
    assert source["style_mode"] == MODES[key] and source["consistency"]["spec"] == []
    assert (ROOT / "examples" / f"scada-{key}" / "README.md").is_file()


def test_the_selected_states_example_pairs_four_icons_with_filled_variants():
    inv = {i["id"]: i for i in json.loads((set_dir("selected-states") / "inventory.json").read_text())["icons"]}
    variants = {i: e["variant_of"] for i, e in inv.items() if e.get("variant_of")}
    assert variants == {"valve-filled": "valve", "pump-filled": "pump", "alarm-list-filled": "alarm-list",
                        "settings-filled": "settings"}
    manifest = {i["id"]: i for i in json.loads((set_dir("selected-states") / "manifest.json").read_text())["icons"]}
    assert all(manifest[v]["status"] == "eligible" for v in variants)


def test_the_duotone_example_keeps_its_secondary_opacity_and_a_non_default_palette():
    spec = json.loads((set_dir("duotone") / "style-spec.json").read_text())
    assert spec["duotone_secondary_opacity"] == 0.3 and spec["palette_status"] == "provisional_requires_review"
    assert spec["themes"]["light"]["normal"] == "#1D4ED8"


def test_the_bold_example_uses_stroke_2_in_spec_and_masters():
    d = set_dir("outline-bold")
    assert json.loads((d / "style-spec.json").read_text())["stroke_width"] == 2
    assert all('stroke-width="2"' in p.read_text() for p in (d / "masters").glob("*.svg"))


def test_no_example_embeds_an_absolute_path_of_the_machine_that_built_it():
    for key in MODES:
        for p in (ROOT / "examples" / f"scada-{key}").rglob("*"):
            if p.is_file() and p.suffix in {".json", ".md", ".html"}:
                text = p.read_text(encoding="utf-8", errors="ignore")
                assert "/home/" not in text and "/tmp/" not in text and "/mnt/" not in text, p


def test_the_badged_example_has_a_solid_badge_and_16_px_variants_for_the_crowded_icons():
    d = set_dir("badged")
    masters = {p.stem: p.read_text() for p in (d / "masters").glob("*.svg")}
    assert set(masters) == BADGED
    for text in masters.values():
        assert 'fill="currentColor" stroke="none" fill-rule="evenodd"' in text, "one solid badge with a cut-out symbol"
    small = {p.stem for p in (d / "variants" / "small").glob("*.svg")}
    assert small == {"pump-add", "valve-remove", "save-done"}
    manifest = {i["id"]: i for i in json.loads((d / "manifest.json").read_text())["icons"]}
    assert set(manifest) == BADGED and all(i["status"] == "eligible" for i in manifest.values())
    review = json.loads((d / "reports" / "pilot-review.json").read_text())
    assert all(review[i]["clarity_16"] >= 4 for i in small), "scored after the 16 px variants"
