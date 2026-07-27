"""Conformance for the hand keypoint block (C11 / Parthenon#47).

The design under test: keypoint vectors are **variable-length** and describe
themselves through ``observation.hand.layout`` (skeleton registry) +
``observation.hand.frame`` (reference frame), rather than being a fixed
``float[63]`` that would freeze MediaPipe's topology into the open standard.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnesis_canonical import (
    HAND_FRAMES,
    CanonicalFrame,
    joint_count,
    list_skeleton_ids,
    list_skeletons,
    load_skeleton,
    migrate_hand_v0,
    migrate_hand_v0_frames,
    read_jsonl,
    validate_frame,
)
from mnesis_canonical.migrate import HAND_V0_DROPPED, HAND_V0_RENAMES

ROOT = Path(__file__).resolve().parent.parent
SKELETONS_DIR = ROOT / "skeletons"
PKG_SKELETONS_DIR = ROOT / "mnesis_canonical" / "skeletons"

LEFT = "observation.hand.left"
RIGHT = "observation.hand.right"
LEFT_ROT = "observation.hand.left.rot"
RIGHT_ROT = "observation.hand.right.rot"
LAYOUT = "observation.hand.layout"
FRAME = "observation.hand.frame"
SOURCE = "observation.hand.source"


def _hand(layout_id: str, dims: int = 3) -> list[float]:
    """A correctly-sized (all-zero) keypoint vector for a layout."""
    return [0.0] * (dims * joint_count(layout_id))


@pytest.fixture
def hand_frame(good_frame):
    """A valid ego frame carrying a MediaPipe left hand."""
    f = good_frame()
    f[LEFT] = _hand("mediapipe_hand_21")
    f[LAYOUT] = "mediapipe_hand_21"
    f[FRAME] = "head_anchored"
    f[SOURCE] = "mediapipe_world+arcore_pose"
    return f


# --- skeleton registry ------------------------------------------------------

def test_registered_layouts():
    assert set(list_skeleton_ids()) == {
        "mediapipe_hand_21", "openxr_hand_26", "webxr_hand_25",
    }
    assert list_skeleton_ids(kind="hand") == list_skeleton_ids()


def test_layout_joint_counts():
    # The whole point of the layout mechanism: these differ, and the standard
    # accommodates all three without a schema change.
    assert joint_count("mediapipe_hand_21") == 21
    assert joint_count("webxr_hand_25") == 25
    assert joint_count("openxr_hand_26") == 26


def test_unknown_layout_raises():
    with pytest.raises(LookupError):
        load_skeleton("no_such_layout")


@pytest.mark.parametrize("entry", list_skeletons(), ids=lambda e: e["id"])
def test_layout_internally_consistent(entry):
    k = entry["joint_count"]
    assert len(entry["joint_names"]) == k
    assert len(entry["parents"]) == k
    assert entry["length_unit"] == "m"
    # parents describe a tree: exactly one root, every other parent in range and
    # pointing to an already-declared joint (so the list is topologically sorted).
    assert entry["parents"].count(-1) == 1
    for i, parent in enumerate(entry["parents"]):
        assert -1 <= parent < i, f"joint {i} has out-of-order parent {parent}"


@pytest.mark.parametrize("entry", list_skeletons(), ids=lambda e: e["id"])
def test_layout_matches_schema(entry):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (SKELETONS_DIR / "skeleton.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(entry)


def test_orientation_capable_layouts_declared():
    # Eidolon C2 (WebXR) / OpenXR carry per-joint orientation; MediaPipe does not.
    assert load_skeleton("mediapipe_hand_21")["has_orientation"] is False
    assert load_skeleton("webxr_hand_25")["has_orientation"] is True
    assert load_skeleton("openxr_hand_26")["has_orientation"] is True


def test_xr_layouts_are_experimental_pending_eidolon():
    assert load_skeleton("mediapipe_hand_21")["status"] == "stable"
    for lid in ("webxr_hand_25", "openxr_hand_26"):
        assert load_skeleton(lid)["status"] == "experimental"


def test_package_skeletons_sync_with_root():
    """Package-level skeletons must match root-level ones byte-for-byte."""
    root_files = sorted(p.name for p in SKELETONS_DIR.glob("*.json"))
    pkg_files = sorted(p.name for p in PKG_SKELETONS_DIR.glob("*.json"))
    assert root_files == pkg_files
    for name in root_files:
        assert (SKELETONS_DIR / name).read_bytes() == (
            PKG_SKELETONS_DIR / name
        ).read_bytes(), f"{name} differs between root skeletons/ and package skeletons/"


# --- frame validation -------------------------------------------------------

def test_valid_hand_frame(hand_frame):
    assert validate_frame(hand_frame) == []


def test_absent_hand_block_is_valid(good_frame):
    """Additive: a frame with no hand keys validates exactly as before."""
    assert validate_frame(good_frame()) == []


def test_both_hands(hand_frame):
    hand_frame[RIGHT] = _hand("mediapipe_hand_21")
    assert validate_frame(hand_frame) == []


def test_wrong_length_rejected(hand_frame):
    hand_frame[LEFT] = [0.0] * 60
    errs = validate_frame(hand_frame)
    assert any("must have length 63" in e for e in errs)


def test_layout_required_when_keypoints_present(hand_frame):
    del hand_frame[LAYOUT]
    errs = validate_frame(hand_frame)
    assert any(e.startswith(f"{LAYOUT} is required") for e in errs)


def test_frame_required_when_keypoints_present(hand_frame):
    del hand_frame[FRAME]
    errs = validate_frame(hand_frame)
    assert any(e.startswith(f"{FRAME} is required") for e in errs)


def test_unregistered_layout_rejected(hand_frame):
    hand_frame[LAYOUT] = "mediapipe_hand_42"
    errs = validate_frame(hand_frame)
    assert any("not a registered skeleton layout" in e for e in errs)


def test_layout_of_the_wrong_length_family_rejected(hand_frame):
    """A 21-point vector declared as a 25-joint layout must not slip through."""
    hand_frame[LAYOUT] = "webxr_hand_25"
    errs = validate_frame(hand_frame)
    assert any("must have length 75" in e for e in errs)


@pytest.mark.parametrize("bad", ["", "camera", "World", None, 3])
def test_frame_enum_enforced(hand_frame, bad):
    hand_frame[FRAME] = bad
    errs = validate_frame(hand_frame)
    assert any(e.startswith(f"{FRAME} must be one of") for e in errs)


@pytest.mark.parametrize("value", HAND_FRAMES)
def test_every_declared_frame_value_accepted(hand_frame, value):
    hand_frame[FRAME] = value
    assert validate_frame(hand_frame) == []


def test_source_must_be_a_real_label(hand_frame):
    hand_frame[SOURCE] = ""
    assert any(e.startswith(SOURCE) for e in validate_frame(hand_frame))


def test_source_is_optional(hand_frame):
    del hand_frame[SOURCE]
    assert validate_frame(hand_frame) == []


def test_orientation_channel(hand_frame):
    hand_frame[LAYOUT] = "openxr_hand_26"
    hand_frame[LEFT] = _hand("openxr_hand_26")
    hand_frame[FRAME] = "world"
    hand_frame[LEFT_ROT] = _hand("openxr_hand_26", dims=4)
    assert validate_frame(hand_frame) == []


def test_orientation_wrong_length_rejected(hand_frame):
    hand_frame[LEFT_ROT] = [0.0] * 63  # 3 per joint, not 4
    assert any("must have length 84" in e for e in validate_frame(hand_frame))


def test_orientation_without_positions_rejected(hand_frame):
    hand_frame[RIGHT_ROT] = _hand("mediapipe_hand_21", dims=4)
    errs = validate_frame(hand_frame)
    assert any(f"{RIGHT_ROT} requires {RIGHT}" in e for e in errs)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_rejected(hand_frame, bad):
    hand_frame[LEFT][4] = bad
    assert any("finite" in e for e in validate_frame(hand_frame))


def test_non_numeric_rejected(hand_frame):
    hand_frame[LEFT][0] = "0.0"
    assert any("only numbers" in e for e in validate_frame(hand_frame))


def test_null_is_not_a_way_to_say_absent(hand_frame):
    """Absence has exactly one representation: omit the key."""
    hand_frame[LEFT] = None
    assert any(f"{LEFT} must be a list" in e for e in validate_frame(hand_frame))


def test_hand_block_works_on_robot_v2(good_frame):
    f = good_frame()
    f["profile"] = "robot_v2"
    del f["observation.images.ego"]
    f["observation.images.head"] = "frames/000000.jpg"
    f[LEFT] = _hand("mediapipe_hand_21")
    f[LAYOUT] = "mediapipe_hand_21"
    f[FRAME] = "head_anchored"
    assert validate_frame(f) == []


# --- JSON Schema backend (the contract other languages validate against) -----

def test_jsonschema_enforces_layout_and_frame_dependency(hand_frame):
    pytest.importorskip("jsonschema")
    from mnesis_canonical import validate_frame_jsonschema

    assert validate_frame_jsonschema(hand_frame) == []
    del hand_frame[LAYOUT]
    assert validate_frame_jsonschema(hand_frame) != []


def test_jsonschema_enforces_frame_enum(hand_frame):
    pytest.importorskip("jsonschema")
    from mnesis_canonical import validate_frame_jsonschema

    hand_frame[FRAME] = "camera"
    assert validate_frame_jsonschema(hand_frame) != []


# --- typed wrapper ----------------------------------------------------------

def test_canonical_frame_roundtrip(hand_frame):
    frame = CanonicalFrame.from_dict(hand_frame)
    assert frame.hand_layout == "mediapipe_hand_21"
    assert frame.hand_frame == "head_anchored"
    assert len(frame.hand_left or []) == 63
    assert frame.hand_right is None
    assert frame.to_dict() == hand_frame


def test_canonical_frame_omits_absent_hand(good_frame):
    frame = CanonicalFrame.from_dict(good_frame())
    assert not any(k.startswith("observation.hand") for k in frame.to_dict())


# --- migration of pre-standard Iris data ------------------------------------

@pytest.fixture
def legacy_frame(good_frame):
    f = good_frame()
    f["hand_left_kpts3d"] = [0.1] * 63
    f["hand_right_kpts3d"] = [0.2] * 63
    f["hand_kpts_source"] = "mediapipe_world+arcore_pose"
    f["hand_pose"] = [1.0, 1.0] + [0.1] * 63 + [0.2] * 63
    return f


def test_legacy_names_are_not_accepted(legacy_frame):
    """The standard never learns an alias — legacy keys are simply unknown."""
    assert not any(k.startswith("observation.hand") for k in legacy_frame)


def test_migration_renames_and_declares(legacy_frame):
    out = migrate_hand_v0(legacy_frame)
    assert out[LEFT] == [0.1] * 63
    assert out[RIGHT] == [0.2] * 63
    assert out[SOURCE] == "mediapipe_world+arcore_pose"
    assert out[LAYOUT] == "mediapipe_hand_21"
    assert out[FRAME] == "head_anchored"
    assert validate_frame(out) == []


def test_migration_drops_derived_hand_pose(legacy_frame):
    out = migrate_hand_v0(legacy_frame)
    for legacy in (*HAND_V0_RENAMES, *HAND_V0_DROPPED):
        assert legacy not in out
    assert "hand_pose" not in out


def test_migration_does_not_touch_the_source_dict(legacy_frame):
    before = dict(legacy_frame)
    migrate_hand_v0(legacy_frame)
    assert legacy_frame == before


def test_migration_is_a_noop_without_legacy_keys(good_frame):
    f = good_frame()
    assert migrate_hand_v0(f) == f


def test_migration_is_idempotent(legacy_frame):
    once = migrate_hand_v0(legacy_frame)
    assert migrate_hand_v0(once) == once


def test_migration_rejects_an_unknown_reference_frame(legacy_frame):
    with pytest.raises(ValueError):
        migrate_hand_v0(legacy_frame, reference_frame="camera")


def test_migration_over_an_episode(legacy_frame, good_frame):
    out = migrate_hand_v0_frames([legacy_frame, good_frame()])
    assert LEFT in out[0] and LEFT not in out[1]


# --- shipped example --------------------------------------------------------

def test_example_episode_carries_hand_keypoints():
    frames = read_jsonl(ROOT / "examples" / "episode_hands" / "data.jsonl")
    assert frames[0][LAYOUT] == "mediapipe_hand_21"
    assert frames[0][FRAME] == "head_anchored"
    assert len(frames[0][LEFT]) == 63
    assert len(frames[0][RIGHT]) == 63


def test_example_omits_the_untracked_hand():
    """The rule most likely to be broken, demonstrated in shipped data."""
    frames = read_jsonl(ROOT / "examples" / "episode_hands" / "data.jsonl")
    assert RIGHT not in frames[1]
    assert LEFT in frames[1]


# --- spec text --------------------------------------------------------------

def test_spec_documents_the_hand_block():
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert "## Hand keypoints" in spec
    for token in (LEFT, LAYOUT, FRAME, SOURCE, "head_anchored", "mediapipe_hand_21"):
        assert token in spec
    # the 2.5D boundary and the presence rule must be stated, not implied
    assert "absolute position relative to the world is not recovered" in spec
    assert "Absent means unknown" in spec


def test_spec_documents_field_level_status():
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert "Field-level status" in spec
    assert "[experimental]" in spec


def test_contracts_registers_c11_as_settled():
    contracts = (ROOT / "CONTRACTS.md").read_text(encoding="utf-8")
    assert "observation.hand.left" in contracts
    assert "C11" in contracts
