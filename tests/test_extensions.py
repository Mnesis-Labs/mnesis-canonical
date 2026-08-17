"""Tests for the vendor extension namespace (issue #69).

Covers:
  - the reserved ``x-<vendor>.`` prefix in the JSON Schema (patternProperties)
  - the unknown-key **warning** channel (not an error) on ValidationReport
  - the CLI printing warnings without changing the exit code
  - the extensions/registry.json + schema
  - SPEC.md §Conventions documenting the prefix
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnesis_canonical import (
    VENDOR_EXTENSION_PREFIX,
    load_json_schema,
    validate_frame,
    validate_frames,
)
from mnesis_canonical.__main__ import main

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_TEXT = (REPO_ROOT / "SPEC.md").read_text(encoding="utf-8")
REGISTRY = json.loads((REPO_ROOT / "extensions" / "registry.json").read_text(encoding="utf-8"))
REGISTRY_SCHEMA = json.loads(
    (REPO_ROOT / "extensions" / "registry.schema.json").read_text(encoding="utf-8")
)


def _frame_with(**extra) -> dict:
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-06-26T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.images.ego": "",
        "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "spatial_anchor_id": None,
        "source.device": "phone", "source.modality": "ego_human",
        "tracking_state": "TRACKING",
    }
    f.update(extra)
    return f


# ── SPEC.md documents the reserved prefix ─────────────────────────────────────


def test_spec_documents_vendor_prefix():
    assert "x-<vendor>." in SPEC_TEXT
    assert "reserved" in SPEC_TEXT
    assert "patternProperties" in SPEC_TEXT


# ── JSON Schema acknowledges the prefix via patternProperties ────────────────


def test_schema_has_vendor_pattern_properties():
    schema = load_json_schema()
    pp = schema.get("patternProperties", {})
    assert any("^x-" in pat for pat in pp), (
        "canonical_frame.schema.json must acknowledge the x-<vendor>. prefix "
        "via patternProperties"
    )


def test_x_vendor_key_passes_jsonschema(good_frame):
    pytest.importorskip("jsonschema")
    from mnesis_canonical import validate_frame_jsonschema

    f = good_frame()
    f["x-iris.hand_left_kpts3d"] = [0.0] * 63
    assert validate_frame_jsonschema(f) == []


# ── Unknown-key warning channel (not an error) ────────────────────────────────


def test_unknown_key_is_warning_not_error(good_frame):
    f = good_frame()
    f["mystery_field"] = "hello"
    # per-frame: no error
    assert validate_frame(f) == []
    # episode-level: warning, but still ok (exit code unchanged)
    report = validate_frames([f])
    assert report.ok
    assert len(report.warnings) == 1
    assert "mystery_field" in report.warnings[0][1]


def test_x_vendor_key_is_exempt_from_warning(good_frame):
    f = good_frame()
    f["x-iris.hand_left_kpts3d"] = [0.0] * 63
    report = validate_frames([f])
    assert report.ok
    assert report.warnings == []


def test_known_standard_keys_produce_no_warnings(good_frame):
    report = validate_frames([good_frame()])
    assert report.warnings == []


def test_observation_images_open_key_set_no_warning(good_frame):
    f = good_frame()
    f["profile"] = "robot_v2"
    f["observation.images.wrist_left"] = "frame.jpg"
    report = validate_frames([f])
    assert report.ok
    assert report.warnings == []


def test_vendor_extension_prefix_constant():
    assert VENDOR_EXTENSION_PREFIX == "x-"


# ── CLI prints warnings without changing exit code ────────────────────────────


def test_cli_prints_warning_but_exits_zero(tmp_path, capsys, good_frame):
    f = good_frame()
    f["mystery_field"] = "hello"
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps(f) + "\n", encoding="utf-8")
    rc = main(["validate", str(path)])
    assert rc == 0  # warnings must not change the exit code
    captured = capsys.readouterr()
    assert "warning:" in captured.err
    assert "mystery_field" in captured.err
    assert "warnings=1" in captured.out


def test_cli_exits_one_on_real_error_still(tmp_path, capsys, good_frame):
    f = good_frame()
    del f["t_hw_ns"]  # missing required key -> error
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps(f) + "\n", encoding="utf-8")
    rc = main(["validate", str(path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "t_hw_ns" in err


# ── Extension registry ────────────────────────────────────────────────────────


def test_registry_has_schema():
    assert REGISTRY_SCHEMA["$schema"].endswith("2020-12/schema")
    assert "extensions" in REGISTRY_SCHEMA["properties"]


def test_registry_contains_iris_fields():
    names = {e["name"] for e in REGISTRY["extensions"]}
    assert "x-iris.hand_left_kpts3d" in names
    assert "x-iris.hand_right_kpts3d" in names
    assert "x-iris.hand_kpts_source" in names
    assert "x-iris.hand_pose" in names


def test_registry_iris_fields_promoted():
    by_name = {e["name"]: e for e in REGISTRY["extensions"]}
    for name in ("x-iris.hand_left_kpts3d", "x-iris.hand_right_kpts3d", "x-iris.hand_kpts_source"):
        assert by_name[name]["promotion_status"] == "promoted"
        assert by_name[name]["promoted_in_issue"] == "mnesis-canonical#68"


def test_registry_entries_match_schema():
    """Every registry entry must satisfy the registry schema."""
    pytest.importorskip("jsonschema")
    import jsonschema

    validator = jsonschema.Draft202012Validator(REGISTRY_SCHEMA)
    errors = list(validator.iter_errors(REGISTRY))
    assert errors == [], [e.message for e in errors]


def test_registry_names_use_x_vendor_prefix():
    for e in REGISTRY["extensions"]:
        assert e["name"].startswith("x-"), f"{e['name']} must use the x- prefix"