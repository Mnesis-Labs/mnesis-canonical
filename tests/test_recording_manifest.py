"""C2b recording manifest: schema + validator + golden examples (issue #162).

The examples under ``examples/recording_manifest/`` are what Iris (phone) and
Eidolon (headset) produce; every negative case below must name the offending
field in its error so a capture surface can fix the right thing, and a manifest
with several problems must report all of them in one pass.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import mnesis_canonical as mc
from mnesis_canonical import contracts_check
from mnesis_canonical.recording_manifest import (
    SCHEMA_VERSION,
    load_recording_manifest,
    load_recording_manifest_schema,
    validate_recording_manifest,
)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = ROOT / "examples" / "recording_manifest"
EXAMPLES = sorted(EXAMPLES_DIR.glob("c2_manifest_*.json"))
SCHEMA_REL = "mnesis_canonical/contracts/c2_recording_manifest.schema.json"


@pytest.fixture
def phone() -> dict:
    return load_recording_manifest(EXAMPLES_DIR / "c2_manifest_phone.json")


def _errors_mentioning(errors: list[str], field: str) -> list[str]:
    return [e for e in errors if field in e]


# --- positive -----------------------------------------------------------------


def test_both_examples_present():
    names = {p.name for p in EXAMPLES}
    assert {"c2_manifest_phone.json", "c2_manifest_headset.json"} <= names


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_examples_validate(path: Path):
    assert validate_recording_manifest(load_recording_manifest(path)) == []


def test_examples_cover_phone_and_headset():
    kinds = {load_recording_manifest(p)["device"]["kind"] for p in EXAMPLES}
    assert {"phone", "headset"} <= kinds


def test_exported_from_package():
    assert mc.validate_recording_manifest is validate_recording_manifest
    assert "validate_recording_manifest" in mc.__all__


def test_schema_is_draft_2020_12_and_documented():
    schema = load_recording_manifest_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION == "c2/1.0"

    # Every declared property, at every depth, carries a description.
    def walk(node: dict, where: str) -> None:
        for name, sub in node.get("properties", {}).items():
            assert sub.get("description"), f"{where}.{name} has no description"
            walk(sub, f"{where}.{name}")
        if isinstance(node.get("items"), dict):
            walk(node["items"], f"{where}[]")

    walk(schema, "<root>")


def test_schema_file_pinned_in_contracts_lock():
    """Iris/Eidolon vendor the schema by sha256 — the lock must carry that hash."""
    lock = contracts_check._load_lock()
    assert lock is not None
    digest = hashlib.sha256((ROOT / SCHEMA_REL).read_bytes()).hexdigest()
    assert lock["files"].get(SCHEMA_REL) == digest


# --- negative: each names the offending field ----------------------------------


def test_bad_sha256_length(phone):
    phone["media"][0]["sha256"] = "ab" * 31  # 62 chars
    errors = validate_recording_manifest(phone)
    assert len(errors) == 1
    assert _errors_mentioning(errors, "media[0].sha256"), errors


def test_uppercase_sha256_rejected(phone):
    phone["media"][0]["sha256"] = phone["media"][0]["sha256"].upper()
    assert _errors_mentioning(validate_recording_manifest(phone), "sha256")


def test_missing_timebase(phone):
    del phone["timebase"]
    errors = validate_recording_manifest(phone)
    assert len(errors) == 1
    assert _errors_mentioning(errors, "timebase"), errors


def test_unknown_top_level_field(phone):
    phone["surprise_field"] = 1
    errors = validate_recording_manifest(phone)
    assert len(errors) == 1
    assert _errors_mentioning(errors, "surprise_field"), errors


def test_negative_frame_count(phone):
    phone["stream_confirmations"][1]["frame_count"] = -1
    errors = validate_recording_manifest(phone)
    assert len(errors) == 1
    assert _errors_mentioning(errors, "stream_confirmations[1].frame_count"), errors


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-28 08:15:30Z",  # space instead of T
        "2026-09-28T08:15:30",  # no offset
        "yesterday",
        "2026-13-01T00:00:00Z",  # right shape, impossible month
        "2026-02-30T00:00:00Z",  # right shape, impossible day
    ],
)
def test_bad_utc_start(phone, value):
    phone["timebase"]["utc_start"] = value
    errors = validate_recording_manifest(phone)
    assert len(errors) == 1, errors
    assert _errors_mentioning(errors, "timebase.utc_start"), errors


def test_utc_start_offsets_accepted(phone):
    for value in ("2026-09-28T08:15:30Z", "2026-09-28T16:15:30.5+08:00", "2016-12-31T23:59:60Z"):
        phone["timebase"]["utc_start"] = value
        assert validate_recording_manifest(phone) == [], value


def test_media_kind_not_in_enum(phone):
    phone["media"][2]["kind"] = "pointcloud"
    errors = validate_recording_manifest(phone)
    assert len(errors) == 1
    assert _errors_mentioning(errors, "media[2].kind"), errors


def test_bad_device_kind(phone):
    phone["device"]["kind"] = "tablet"
    assert _errors_mentioning(validate_recording_manifest(phone), "device.kind")


def test_wrong_schema_version(phone):
    phone["schema_version"] = "c2/0.9"
    assert _errors_mentioning(validate_recording_manifest(phone), "schema_version")


def test_resolved_capture_options_requires_video_fields(phone):
    del phone["resolved_capture_options"]["video"]["codec"]
    assert _errors_mentioning(validate_recording_manifest(phone), "codec")


@pytest.mark.parametrize("path", ["/abs/video.mp4", "../video.mp4", "a/../b.mp4", "C:video.mp4"])
def test_media_path_must_be_relative(phone, path):
    phone["media"][0]["path"] = path
    assert _errors_mentioning(validate_recording_manifest(phone), "media[0].path")


def test_stream_confirmation_not_declared(phone):
    phone["stream_confirmations"][0]["name"] = "thermal"
    errors = validate_recording_manifest(phone)
    assert _errors_mentioning(errors, "stream_confirmations[0].name")
    # ...and the declared stream that lost its confirmation is reported too.
    assert _errors_mentioning(errors, "'rgb' has no entry")


def test_enabled_stream_with_zero_fps(phone):
    phone["stream_confirmations"][0]["fps"] = 0
    assert _errors_mentioning(validate_recording_manifest(phone), "stream_confirmations[0].fps")


def test_duplicate_media_path(phone):
    phone["media"].append(copy.deepcopy(phone["media"][0]))
    assert _errors_mentioning(validate_recording_manifest(phone), "media[3].path")


def test_non_object_input():
    errors = validate_recording_manifest([])  # type: ignore[arg-type]
    assert errors and "<root>" in errors[0]


# --- all errors, not just the first --------------------------------------------


def test_three_errors_all_reported(phone):
    phone["media"][0]["sha256"] = "deadbeef"
    phone["stream_confirmations"][0]["frame_count"] = -5
    phone["unexpected"] = True
    errors = validate_recording_manifest(phone)
    assert len(errors) == 3, errors
    assert _errors_mentioning(errors, "media[0].sha256")
    assert _errors_mentioning(errors, "stream_confirmations[0].frame_count")
    assert _errors_mentioning(errors, "unexpected")


def test_load_recording_manifest_rejects_non_object(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_recording_manifest(p)
