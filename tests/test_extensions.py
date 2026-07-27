"""Conformance for the reserved extension namespace + registry (#69).

This is the root-cause card behind Parthenon#47: four Iris hand fields lived in
production for two weeks and canonical was the last to know, because extending
the standard cost more than quietly not extending it.  The fix has three halves
pinned here — a legal namespace (`x-<vendor>.<field>`), a registry anyone can
append to with a single-repo PR, and a **warning** channel that makes everything
outside those two visible without ever turning old data red.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnesis_canonical import (
    EXTENSION_KEY_PATTERN,
    KNOWN_FRAME_KEYS,
    PROMOTION_STATUSES,
    find_extension,
    frame_warnings,
    is_extension_key,
    list_extension_names,
    list_extensions,
    load_extension,
    load_json_schema,
    load_registry,
    validate_frame,
    validate_frames,
)
from mnesis_canonical.extension_registry import load_registry_schema

ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS_DIR = ROOT / "extensions"
PKG_EXTENSIONS_DIR = ROOT / "mnesis_canonical" / "extensions"

# The four fields Iris shipped before C11 — the worked example that this whole
# mechanism exists to have caught on day one.
IRIS_LEGACY_KEYS = (
    "hand_left_kpts3d",
    "hand_right_kpts3d",
    "hand_kpts_source",
    "hand_pose",
)


# ── the reserved namespace ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "key",
    [
        "x-iris.hand_left_kpts3d",
        "x-eidolon.grip_force",
        "x-ambrosia.quality.score",
        "x-daedalus2.joint-temp",
    ],
)
def test_well_formed_extension_keys_are_recognised(key):
    assert is_extension_key(key)


@pytest.mark.parametrize(
    "key",
    [
        "x-iris",           # no field part
        "x-.field",         # no vendor
        "x-Iris.field",     # vendor must be lower-case
        "xiris.field",      # missing the reserved prefix
        "observation.state",
    ],
)
def test_malformed_extension_keys_are_rejected(key):
    assert not is_extension_key(key)


def test_schema_declares_the_reserved_prefix_in_pattern_properties():
    """The namespace must be explicitly legal in the JSON Schema, not merely tolerated."""
    schema = load_json_schema()
    assert EXTENSION_KEY_PATTERN in schema["patternProperties"]


def test_schema_does_not_set_additional_properties_false():
    """Closing the frame would break the additive promise and the open camera key set."""
    assert "additionalProperties" not in load_json_schema()


def test_known_frame_keys_match_the_json_schema_properties():
    """schema.py's key list and the JSON Schema must not drift apart."""
    declared = set(load_json_schema()["properties"])
    assert set(KNOWN_FRAME_KEYS) == declared


# ── the registry ─────────────────────────────────────────────────────────────

def test_registry_loads_and_is_sorted():
    registry = load_registry()
    assert registry["version"] == 1
    names = [e["name"] for e in registry["extensions"]]
    assert names == sorted(names), "keep extensions/registry.json sorted by name"
    assert len(names) == len(set(names)), "duplicate extension names"


@pytest.mark.parametrize("entry", list_extensions(), ids=lambda e: e["name"])
def test_registry_entries_carry_the_required_fields(entry):
    for key in ("name", "owner_repo", "since", "description", "promotion_status"):
        assert entry.get(key) or entry.get(key) == 0, f"{entry['name']} missing {key}"
    assert entry["promotion_status"] in PROMOTION_STATUSES
    if entry["promotion_status"] == "promoted":
        assert "replaced_by" in entry, (
            f"{entry['name']} is promoted but does not say what replaced it "
            f"(use null when it was promoted by being dropped)"
        )


def test_registry_validates_against_its_own_schema():
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(load_registry_schema())
    errors = [e.message for e in validator.iter_errors(load_registry())]
    assert errors == []


def test_iris_legacy_keys_are_registered_as_promoted():
    """The #68 fields are the sample entry — registered, and marked promoted."""
    for key in IRIS_LEGACY_KEYS:
        entry = load_extension(key)
        assert entry["promotion_status"] == "promoted"
        assert entry["owner_repo"] == "Mnesis-Labs/Mnesis-Iris"
    assert load_extension("hand_left_kpts3d")["replaced_by"] == "observation.hand.left"
    assert load_extension("hand_right_kpts3d")["replaced_by"] == "observation.hand.right"
    assert load_extension("hand_kpts_source")["replaced_by"] == "observation.hand.source"
    # hand_pose was promoted by being DROPPED — it is a derived projection.
    assert load_extension("hand_pose")["replaced_by"] is None


def test_load_extension_unknown_raises_and_find_returns_none():
    with pytest.raises(LookupError):
        load_extension("x-nobody.nothing")
    assert find_extension("x-nobody.nothing") is None


def test_list_extension_names_can_filter_on_promotion_status():
    assert set(list_extension_names(promotion_status="promoted")) >= set(IRIS_LEGACY_KEYS)
    assert list_extension_names(promotion_status="withdrawn") == []


def test_package_registry_synced_with_root():
    for name in ("registry.json", "registry.schema.json"):
        assert (EXTENSIONS_DIR / name).read_bytes() == (
            PKG_EXTENSIONS_DIR / name
        ).read_bytes(), f"{name} differs between root extensions/ and package extensions/"


# ── the warning channel ──────────────────────────────────────────────────────

def test_clean_frame_has_no_warnings(good_frame):
    assert frame_warnings(good_frame()) == []


def test_reserved_prefix_key_is_silent(good_frame):
    f = good_frame()
    f["x-iris.finger_curl"] = [0.1, 0.2]
    assert frame_warnings(f) == []
    assert validate_frame(f) == []


def test_open_camera_key_set_is_silent(good_frame):
    f = good_frame()
    f["observation.images.wrist_left"] = "frames/000001.jpg"
    assert frame_warnings(f) == []


def test_unknown_key_warns_and_points_at_the_namespace(good_frame):
    f = good_frame()
    f["grip_force"] = 0.5
    warnings = frame_warnings(f)
    assert len(warnings) == 1
    assert "grip_force" in warnings[0]
    assert "x-<vendor>." in warnings[0]
    assert "extensions/registry.json" in warnings[0]


def test_unknown_key_is_not_an_error(good_frame):
    """The additive promise: an undeclared key never invalidates a frame."""
    f = good_frame()
    f["grip_force"] = 0.5
    assert validate_frame(f) == []
    report = validate_frames([f])
    assert report.ok is True
    assert report.errors == []
    assert len(report.warnings) == 1


def test_malformed_reserved_prefix_warns(good_frame):
    f = good_frame()
    f["x-iris"] = 1
    warnings = frame_warnings(f)
    assert len(warnings) == 1
    assert "x-<vendor>.<field>" in warnings[0]


def test_registered_promoted_key_warns_with_the_standard_field(good_frame):
    f = good_frame()
    f["hand_left_kpts3d"] = [0.0] * 63
    warnings = frame_warnings(f)
    assert len(warnings) == 1
    assert "promotion_status=promoted" in warnings[0]
    assert "observation.hand.left" in warnings[0]
    assert "Mnesis-Labs/Mnesis-Iris" in warnings[0]


def test_promoted_by_dropping_warns_without_a_replacement(good_frame):
    f = good_frame()
    f["hand_pose"] = [0.0] * 128
    warnings = frame_warnings(f)
    assert len(warnings) == 1
    assert "dropped" in warnings[0]


def test_report_warnings_carry_line_numbers(good_frame):
    a, b = good_frame(), good_frame()
    b["frame_index"] = 1
    b["index"] = 1
    b["grip_force"] = 0.5
    report = validate_frames([a, b])
    assert report.ok is True
    assert [line for line, _ in report.warnings] == [1]


def test_warnings_are_collected_even_for_invalid_frames(good_frame):
    f = good_frame()
    del f["t_hw_ns"]
    f["grip_force"] = 0.5
    report = validate_frames([f])
    assert report.errors, "frame is still invalid on its own merits"
    assert len(report.warnings) == 1


# ── the spec says so ─────────────────────────────────────────────────────────

def test_spec_documents_the_reserved_prefix():
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert "## Extensions" in spec
    assert EXTENSION_KEY_PATTERN in spec
    # the Conventions iron rules must carry it too — that is where producers look
    conventions = spec.split("### Conventions (iron rules)")[1].split("\n## ")[0]
    assert "x-<vendor>." in conventions
    assert "warnings, never errors" in conventions


def test_contracts_documents_the_registration_flow():
    contracts = (ROOT / "CONTRACTS.md").read_text(encoding="utf-8")
    assert "## 扩展登记" in contracts
    assert "extensions/registry.json" in contracts
    # the load-bearing claim: registering must not require a cross-repo card
    assert "type:contract-change" in contracts.split("## 扩展登记")[1]


# ── examples stay clean ──────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "path",
    sorted((ROOT / "examples").glob("*/data.jsonl")),
    ids=lambda p: p.parent.name,
)
def test_bundled_examples_produce_no_warnings(path):
    frames = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    report = validate_frames(frames)
    assert report.warnings == []
