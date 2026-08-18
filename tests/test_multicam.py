"""Conformance for the ``ego_multicam_v1`` profile (C1, issue #115).

A 5-camera ego rig (2× wide @60 fps + 3× fisheye @30 fps, one FSYNC trigger) has
no legal representation under ``ego_v1``: one ``observation.images.ego`` key holds
one stream.  This profile opens the image keys to the camera **set** declared by
the embodiment registry — and nothing else changes, so phone-side ``ego_v1`` data
needs no migration.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mnesis_canonical import (
    PROFILES,
    from_lerobot,
    list_camera_names,
    read_jsonl,
    reference_camera,
    required_keys_for_profile,
    to_lerobot,
    validate_frame,
    validate_frames,
)

EXAMPLE = (
    Path(__file__).resolve().parent.parent / "examples" / "episode_ego_multicam" / "data.jsonl"
)
ARGUS = "ego_human_5cam_v1"
CAMERAS = ("wide_l", "wide_r", "fisheye_l", "fisheye_c", "fisheye_r")


def _multicam_frame(**overrides) -> dict:
    """A valid ego_multicam_v1 frame carrying all five Argus cameras."""
    frame = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-08-18T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "spatial_anchor_id": None,
        "source.device": "glasses", "source.modality": "ego_human",
        "tracking_state": "TRACKING",
        "profile": "ego_multicam_v1",
        "embodiment_id": ARGUS,
    }
    for cam in CAMERAS:
        frame[f"observation.images.{cam}"] = f"frames/000000_{cam}.jpg"
    frame.update(overrides)
    return frame


# ── Profile registration ────────────────────────────────────────────────────────


def test_profile_is_registered():
    assert "ego_multicam_v1" in PROFILES


def test_required_keys_drop_the_fixed_ego_camera():
    """No single camera is mandatory — the set is, and it lives in the registry."""
    keys = required_keys_for_profile("ego_multicam_v1")
    assert "observation.images.ego" not in keys
    # Everything else is ego_v1, verbatim.
    assert set(keys) == set(required_keys_for_profile("ego_v1")) - {"observation.images.ego"}


# ── The five-camera frame ───────────────────────────────────────────────────────


def test_five_camera_frame_validates():
    assert validate_frame(_multicam_frame(), strict_vocab=True) == []


def test_dropped_camera_is_omitted_not_blanked():
    """A camera that dropped this frame has no key at all — and that still validates."""
    frame = _multicam_frame()
    del frame["observation.images.fisheye_r"]
    assert validate_frame(frame) == []


def test_empty_string_camera_reference_rejected():
    """'' is the in-band sentinel the iron rule forbids: omit the key instead."""
    errs = validate_frame(_multicam_frame(**{"observation.images.fisheye_r": ""}))
    assert any("fisheye_r" in e and "non-empty" in e for e in errs)


def test_no_camera_at_all_rejected():
    frame = _multicam_frame()
    for cam in CAMERAS:
        del frame[f"observation.images.{cam}"]
    errs = validate_frame(frame)
    assert any("at least one" in e for e in errs)


def test_non_string_camera_reference_rejected():
    errs = validate_frame(_multicam_frame(**{"observation.images.wide_l": 42}))
    assert any("wide_l" in e and "string" in e for e in errs)


# ── Camera names are registry identifiers, not free strings ─────────────────────


def test_typo_camera_name_rejected_against_registry():
    """The whole point: 'wide_left' is a typo, not a sixth camera."""
    frame = _multicam_frame()
    frame["observation.images.wide_left"] = "frames/000000_wide_left.jpg"
    errs = validate_frame(frame)
    assert any("wide_left" in e and ARGUS in e for e in errs)


def test_registry_names_are_the_value_domain():
    assert set(list_camera_names(ARGUS)) == set(CAMERAS)


def test_camera_name_syntax_enforced_without_embodiment_id():
    """Without a resolvable embodiment the domain is unknown — syntax still holds."""
    frame = _multicam_frame(embodiment_id=None)
    frame["observation.images.WideL"] = "frames/000000.jpg"
    errs = validate_frame(frame)
    assert any("WideL" in e for e in errs)


def test_unregistered_embodiment_skips_the_name_check():
    """An unknown embodiment leaves the domain unknown — don't invent errors."""
    frame = _multicam_frame(embodiment_id="some_unreleased_rig_v9")
    frame["observation.images.tele"] = "frames/000000_tele.jpg"
    assert validate_frame(frame) == []


def test_ego_v1_camera_names_are_not_checked_against_the_registry():
    """robot_v2 / ego_v1 behaviour is untouched by the new rule."""
    frame = _multicam_frame(profile="robot_v2")
    frame["observation.images.whatever_CAM"] = "frames/000000.jpg"
    assert validate_frame(frame) == []


# ── ego_v1 is a strict subset (zero migration for the phone surface) ────────────


def test_ego_v1_frame_is_a_valid_multicam_frame(good_frame):
    """'observation.images.ego' under this profile is just 'the camera named ego'."""
    frame = good_frame()
    frame["profile"] = "ego_multicam_v1"
    frame["observation.images.ego"] = "frames/000000_ego.jpg"  # '' is ego_v1-only
    assert validate_frame(frame) == []


def test_ego_v1_itself_is_unchanged(good_frame):
    """ego_v1 keeps requiring its single key and keeps accepting ''."""
    assert validate_frame(good_frame()) == []
    frame = good_frame()
    del frame["observation.images.ego"]
    assert any("observation.images.ego" in e for e in validate_frame(frame))


def test_fixed_length_vectors_still_enforced():
    """Only the image keys change — state/action stay ego_v1-fixed."""
    errs = validate_frame(_multicam_frame(**{"observation.state": [0.0] * 14}))
    assert any("observation.state" in e and "length 7" in e for e in errs)


# ── Ruling 2: mixed frame rates ────────────────────────────────────────────────


def test_registry_declares_a_reference_camera():
    """Row cadence is defined by exactly one camera — converters must not guess."""
    ref = reference_camera(ARGUS)
    assert ref in CAMERAS


def test_reference_camera_fps_is_the_row_rate():
    """The 60 fps wide pair cannot define a 30 Hz row sequence."""
    from mnesis_canonical import load_embodiment

    capture = load_embodiment(ARGUS)["capture"]
    by_name = {c["name"]: c for c in capture["cameras"]}
    assert by_name[capture["reference_camera"]]["fps"] == capture["default_fps"]
    # The rig genuinely mixes rates — otherwise this ruling would be moot.
    assert {c.get("fps") for c in capture["cameras"]} == {30, 60}


# ── Shipped example episode ────────────────────────────────────────────────────


def test_example_episode_exists_and_validates():
    report = validate_frames(read_jsonl(EXAMPLE), strict_vocab=True)
    assert report.ok, report.errors
    assert report.total == 2 and report.valid == 2


def test_example_shows_a_dropped_camera_and_the_faster_pair():
    frames = read_jsonl(EXAMPLE)
    assert all(f["profile"] == "ego_multicam_v1" for f in frames)
    assert all(f["embodiment_id"] == ARGUS for f in frames)
    # Row 0: all five cameras. Row 1: fisheye_r dropped → key absent, not ''.
    assert all(f"observation.images.{c}" in frames[0] for c in CAMERAS)
    assert "observation.images.fisheye_r" not in frames[1]
    # The 60 fps pair advanced two source frames while the 30 fps trio advanced one.
    assert frames[1]["observation.images.wide_l"] == "frames/000002_wide_l.jpg"
    assert frames[1]["observation.images.fisheye_c"] == "frames/000001_fisheye_c.jpg"


# ── Typed wrapper round-trip ───────────────────────────────────────────────────


def test_canonical_frame_round_trip_does_not_invent_an_ego_camera():
    """CanonicalFrame carries `observation.images.ego` as a named attribute; a rig
    without a camera called `ego` must not get a blank one back."""
    from mnesis_canonical import CanonicalFrame

    frame = _multicam_frame()
    round_tripped = CanonicalFrame.from_dict(frame).to_dict()
    assert round_tripped == frame
    assert validate_frame(round_tripped) == []


def test_canonical_frame_keeps_the_ego_camera_when_there_is_one(good_frame):
    """ego_v1's single key — including its legal '' placeholder — is untouched."""
    from mnesis_canonical import CanonicalFrame

    frame = good_frame()
    assert CanonicalFrame.from_dict(frame).to_dict() == frame


# ── SPEC text (the standard, not just the implementation) ──────────────────────


def test_spec_documents_the_profile_and_both_rulings():
    spec = (Path(__file__).resolve().parent.parent / "SPEC.md").read_text(encoding="utf-8")
    assert "### `ego_multicam_v1` profile" in spec
    # Ruling 1: names are per-embodiment, so a consumer must qualify by embodiment_id.
    assert "`(embodiment_id, camera_name)` is the unique key" in spec
    # Ruling 2: one reference camera defines the row cadence, declared in the registry.
    assert "`capture.reference_camera`" in spec


# ── JSON Schema backend (the copy other languages validate against) ────────────


def test_jsonschema_backend_accepts_the_multicam_frame():
    pytest.importorskip("jsonschema")
    from mnesis_canonical import validate_frame_jsonschema

    assert validate_frame_jsonschema(_multicam_frame()) == []


def test_jsonschema_backend_rejects_blank_camera_reference():
    pytest.importorskip("jsonschema")
    from mnesis_canonical import validate_frame_jsonschema

    assert validate_frame_jsonschema(_multicam_frame(**{"observation.images.wide_l": ""}))


def test_jsonschema_backend_still_requires_ego_for_ego_v1(good_frame):
    """The new conditional branch must not relax ego_v1."""
    pytest.importorskip("jsonschema")
    from mnesis_canonical import validate_frame_jsonschema

    frame = good_frame()
    del frame["observation.images.ego"]
    assert validate_frame_jsonschema(frame)


@pytest.mark.parametrize("path", [EXAMPLE], ids=["episode_ego_multicam"])
def test_lerobot_round_trip_keeps_the_dropped_camera_dropped(path):
    """The columnar form pads short columns with None — the inverse must not
    resurrect a camera that never delivered that frame."""
    frames = read_jsonl(path)
    restored = from_lerobot(to_lerobot(frames))
    assert restored == frames
    assert "observation.images.fisheye_r" not in restored[1]
