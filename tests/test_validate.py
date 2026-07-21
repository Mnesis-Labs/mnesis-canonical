"""Tests for the Canonical Schema reference validator + the example episode."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnesis_canonical import (
    ANNOTATION_HANDS,
    ANNOTATION_SOURCES,
    ANNOTATION_VISIBILITIES,
    EVENT_TYPES,
    MANIPULATION_ACTIONS,
    CanonicalFrame,
    load_json_schema,
    read_jsonl,
    validate_annotations,
    validate_events,
    validate_frame,
    validate_frame_jsonschema,
    validate_frames,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "episode_0" / "data.jsonl"


def test_good_frame_validates(good_frame):
    assert validate_frame(good_frame()) == []


def test_missing_key_fails(good_frame):
    f = good_frame()
    del f["t_hw_ns"]
    errs = validate_frame(f)
    assert any("t_hw_ns" in e for e in errs)


def test_wrong_vector_length_fails(good_frame):
    f = good_frame()
    f["action"] = [1.0, 2.0, 3.0]  # should be length 6
    errs = validate_frame(f)
    assert any("action" in e and "length 6" in e for e in errs)


def test_head_pose_must_be_7(good_frame):
    f = good_frame()
    f["head_pose_SE3"] = [0.0] * 6
    assert any("head_pose_SE3" in e for e in validate_frame(f))


def test_strict_vocab_rejects_unknown_device(good_frame):
    f = good_frame()
    f["source.device"] = "hololens"
    assert validate_frame(f) == []  # lenient by default
    assert any("source.device" in e for e in validate_frame(f, strict_vocab=True))


def test_example_episode_is_valid():
    frames = read_jsonl(EXAMPLE)
    report = validate_frames(frames)
    assert report.ok, report.errors
    assert report.total == 2 and report.valid == 2


def test_frame_index_must_increase(good_frame):
    frames = [good_frame(), good_frame()]  # both frame_index=0
    report = validate_frames(frames)
    assert not report.ok
    assert any("duplicate frame_index" in m for _, m in report.errors)


def test_dataclass_roundtrip(good_frame):
    d = good_frame()
    assert CanonicalFrame.from_dict(d).to_dict() == d


# --- JSON Schema backend ------------------------------------------------------

def test_json_schema_loads_and_matches_required_keys():
    schema = load_json_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    # The bundled JSON Schema top-level required is the intersection of all
    # profile required sets (without observation.images.ego, which is conditional).
    # The Python REQUIRED_KEYS is the ego_v1 set (backward compat superset).
    from mnesis_canonical import REQUIRED_KEYS, required_keys_for_profile

    schema_top_required = set(schema["required"])
    robot_v2_required = set(required_keys_for_profile("robot_v2"))
    # Schema top-level must be exactly the robot_v2 required set
    assert schema_top_required == robot_v2_required
    # Python REQUIRED_KEYS (ego_v1) is a superset
    assert set(REQUIRED_KEYS) >= robot_v2_required


def test_example_passes_both_validators():
    pytest.importorskip("jsonschema")
    for frame in read_jsonl(EXAMPLE):
        assert validate_frame(frame) == []
        assert validate_frame_jsonschema(frame) == []


def test_jsonschema_backend_rejects_bad_frame(good_frame):
    pytest.importorskip("jsonschema")
    f = good_frame()
    f["action"] = [1.0, 2.0, 3.0]  # wrong length (should be 6)
    assert validate_frame_jsonschema(f)  # non-empty error list


# --- S2-3: Boundary hardening -------------------------------------------------

def test_nan_in_vector_rejected(good_frame):
    f = good_frame()
    f["action"] = [1.0, float("nan"), 3.0, 4.0, 5.0, 6.0]
    errs = validate_frame(f)
    assert any("action" in e and "finite" in e for e in errs)


def test_inf_in_vector_rejected(good_frame):
    f = good_frame()
    f["head_pose_SE3"] = [0.0, 0.0, 0.0, 0.0, 0.0, float("inf"), 1.0]
    errs = validate_frame(f)
    assert any("head_pose_SE3" in e and "finite" in e for e in errs)


def test_finite_vector_accepted(good_frame):
    f = good_frame()
    f["action"] = [1.0, -2.5, 3.0, 0.0, 0.5, -1.0]
    assert validate_frame(f) == []


def test_duplicate_frame_index_rejected(good_frame):
    f0 = good_frame()
    f1 = good_frame()  # both frame_index=0
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    report = validate_frames([f0, f1])
    assert not report.ok
    assert any("duplicate frame_index" in m for _, m in report.errors)


def test_negative_frame_index_rejected(good_frame):
    f = good_frame()
    f["frame_index"] = -1
    report = validate_frames([f])
    assert not report.ok
    assert any("non-negative" in m for _, m in report.errors)


def test_positive_frame_index_increasing_accepted(good_frame):
    f0 = good_frame()
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    report = validate_frames([f0, f1])
    assert report.ok


# --- S2-10: spatial_anchor_id episode-level validation ------------------------


def test_duplicate_spatial_anchor_rejected(good_frame):
    """Same anchor_id in two frames → duplicate definition error."""
    f0 = good_frame()
    f0["spatial_anchor_id"] = "anchor-A"
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    f1["spatial_anchor_id"] = "anchor-A"
    report = validate_frames([f0, f1])
    assert not report.ok
    assert any("duplicate" in m and "anchor-A" in m for _, m in report.errors)


def test_undefined_spatial_anchor_rejected(good_frame):
    """Empty string spatial_anchor_id → undefined/reference error."""
    f = good_frame()
    f["spatial_anchor_id"] = ""
    errs = validate_frame(f)
    assert any("spatial_anchor_id" in e and "empty" in e for e in errs)


def test_unique_spatial_anchors_accepted(good_frame):
    """Different anchor_ids across frames → valid."""
    f0 = good_frame()
    f0["spatial_anchor_id"] = "anchor-A"
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    f1["spatial_anchor_id"] = "anchor-B"
    report = validate_frames([f0, f1])
    assert report.ok


def test_null_spatial_anchor_accepted(good_frame):
    """None spatial_anchor_id → skip (no anchor)."""
    f = good_frame()
    assert f["spatial_anchor_id"] is None
    assert validate_frame(f) == []


def test_multiple_duplicate_anchor_errors(good_frame):
    """Three frames with the same anchor_id → error on each duplicate."""
    f0 = good_frame()
    f0["spatial_anchor_id"] = "anchor-X"
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    f1["spatial_anchor_id"] = "anchor-X"
    f2 = good_frame()
    f2["frame_index"] = 2
    f2["t_ns"] = 3_000_000
    f2["t_hw_ns"] = 3_000_000_000
    f2["spatial_anchor_id"] = "anchor-X"
    report = validate_frames([f0, f1, f2])
    assert not report.ok
    assert len(report.errors) == 2  # two duplicates of anchor-X
    assert all("duplicate" in m and "anchor-X" in m for _, m in report.errors)


def test_anchor_errors_include_cli_in_output(capsys, tmp_path, good_frame):
    """CLI validate exits 1 and prints anchor errors to stderr."""
    from mnesis_canonical.__main__ import main

    bad = tmp_path / "data.jsonl"
    f0 = good_frame()
    f0["spatial_anchor_id"] = "anchor-A"
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    f1["spatial_anchor_id"] = "anchor-A"
    import json
    bad.write_text(
        json.dumps(f0) + "\n" + json.dumps(f1) + "\n", encoding="utf-8"
    )
    rc = main(["validate", str(bad)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "duplicate" in err and "anchor-A" in err


# ── events.jsonl validation (v0.2+) ────────────────────────────────────────────


def test_validate_events_missing_file_returns_empty(tmp_path):
    """No events.jsonl → no errors (additive-only)."""
    assert validate_events(tmp_path) == []


def test_validate_events_empty_file_returns_empty(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text("", encoding="utf-8")
    assert validate_events(ep) == []


def test_validate_events_good_events_passes(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    lines = [
        {"t_ns": 1000000, "type": "plan_preview", "payload": {"plan_id": "p1"}},
        {"t_ns": 2000000, "type": "execute_confirm", "payload": {"confirmed": True}},
        {"t_ns": 3000000, "type": "estop", "payload": None},
        {"t_ns": 4000000, "type": "episode_mark", "payload": {"mark": "start"}},
        {"t_ns": 5000000, "type": "anchor_set", "payload": {"anchor_id": "a1"}},
    ]
    (ep / "events.jsonl").write_text(
        "\n".join(json.dumps(ev) for ev in lines) + "\n", encoding="utf-8"
    )
    assert validate_events(ep) == []


def test_validate_events_unknown_type_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text(
        json.dumps({"t_ns": 1, "type": "bad_type", "payload": {}}) + "\n",
        encoding="utf-8",
    )
    errs = validate_events(ep)
    assert any("unknown event type" in e and "bad_type" in e for e in errs)


def test_validate_events_bad_t_ns_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text(
        json.dumps({"t_ns": "not_an_int", "type": "estop", "payload": {}}) + "\n",
        encoding="utf-8",
    )
    errs = validate_events(ep)
    assert any("t_ns" in e and "int" in e for e in errs)


def test_validate_events_missing_type_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text(
        json.dumps({"t_ns": 1, "payload": {}}) + "\n",
        encoding="utf-8",
    )
    errs = validate_events(ep)
    assert any("type must be a string" in e for e in errs)


def test_validate_events_null_type_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text(
        json.dumps({"t_ns": 1, "type": None, "payload": {}}) + "\n",
        encoding="utf-8",
    )
    errs = validate_events(ep)
    assert any("type must be a string" in e for e in errs)


def test_validate_events_missing_payload_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text(
        json.dumps({"t_ns": 1, "type": "estop"}) + "\n",
        encoding="utf-8",
    )
    errs = validate_events(ep)
    assert any("payload" in e for e in errs)


def test_validate_events_null_payload_accepted(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text(
        json.dumps({"t_ns": 1, "type": "estop", "payload": None}) + "\n",
        encoding="utf-8",
    )
    assert validate_events(ep) == []


def test_validate_events_non_dict_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text(
        json.dumps(["not", "a", "dict"]) + "\n", encoding="utf-8"
    )
    errs = validate_events(ep)
    assert any("expected JSON object" in e for e in errs)


def test_validate_events_blank_line_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text("\n\n", encoding="utf-8")
    errs = validate_events(ep)
    assert any("blank line" in e for e in errs)


def test_validate_events_invalid_json_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "events.jsonl").write_text(
        "{bad json}\n", encoding="utf-8"
    )
    errs = validate_events(ep)
    assert any("invalid JSON" in e for e in errs)


def test_validate_events_example_episode_valid():
    """The episode_dual_airbot example ships with events.jsonl — it must pass."""
    ep = Path(__file__).resolve().parent.parent / "examples" / "episode_dual_airbot"
    errs = validate_events(ep)
    assert errs == [], errs


def test_validate_events_other_examples_have_no_events():
    """Existing episodes (episode_0, episode_quest, episode_robot) have no
    events.jsonl — validate_events must return empty (additive-only)."""
    examples = Path(__file__).resolve().parent.parent / "examples"
    for name in ("episode_0", "episode_quest", "episode_robot"):
        ep = examples / name
        assert validate_events(ep) == [], f"{name} should have no events"


def test_event_types_are_exported():
    assert "plan_preview" in EVENT_TYPES
    assert "execute_confirm" in EVENT_TYPES
    assert "estop" in EVENT_TYPES
    assert "episode_mark" in EVENT_TYPES
    assert "anchor_set" in EVENT_TYPES
    assert len(EVENT_TYPES) == 5


# ── Manipulation action taxonomy (v0.3+) ──────────────────────────────────────


def test_manipulation_actions_are_exported():
    assert "reaching" in MANIPULATION_ACTIONS
    assert "grasping_pinching" in MANIPULATION_ACTIONS
    assert "lifting" in MANIPULATION_ACTIONS
    assert "holding" in MANIPULATION_ACTIONS
    assert "placing_inserting" in MANIPULATION_ACTIONS
    assert "pushing_pulling" in MANIPULATION_ACTIONS
    assert "rotating" in MANIPULATION_ACTIONS
    assert "opening_closing" in MANIPULATION_ACTIONS
    assert "releasing" in MANIPULATION_ACTIONS
    assert "pressing_sliding" in MANIPULATION_ACTIONS
    assert "pouring" in MANIPULATION_ACTIONS
    assert "bimanual_coordination" in MANIPULATION_ACTIONS
    assert "tool_use" in MANIPULATION_ACTIONS
    assert "idle" in MANIPULATION_ACTIONS
    assert len(MANIPULATION_ACTIONS) == 14


def test_annotation_hands_are_exported():
    assert "left" in ANNOTATION_HANDS
    assert "right" in ANNOTATION_HANDS
    assert "both" in ANNOTATION_HANDS
    assert "none" in ANNOTATION_HANDS
    assert len(ANNOTATION_HANDS) == 4


def test_annotation_visibilities_are_exported():
    assert "visible" in ANNOTATION_VISIBILITIES
    assert "occluded" in ANNOTATION_VISIBILITIES
    assert "out_of_frame" in ANNOTATION_VISIBILITIES
    assert len(ANNOTATION_VISIBILITIES) == 3


def test_annotation_sources_are_exported():
    assert "argus_v0" in ANNOTATION_SOURCES
    assert "human" in ANNOTATION_SOURCES
    assert "external" in ANNOTATION_SOURCES
    assert "iris_heuristic" in ANNOTATION_SOURCES
    assert len(ANNOTATION_SOURCES) == 4


# ── Annotations/spans.jsonl validation (v0.3+) ─────────────────────────────────


def test_validate_annotations_missing_file_returns_empty(tmp_path):
    """No annotations/spans.jsonl → no errors (additive-only)."""
    assert validate_annotations(tmp_path) == []


def test_validate_annotations_empty_file_returns_empty(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    annotations_dir = ep / "annotations"
    annotations_dir.mkdir()
    (annotations_dir / "spans.jsonl").write_text("", encoding="utf-8")
    assert validate_annotations(ep) == []


def _write_spans(ep_dir: Path, spans: list[dict]) -> None:
    annotations_dir = ep_dir / "annotations"
    annotations_dir.mkdir(parents=True, exist_ok=True)
    (annotations_dir / "spans.jsonl").write_text(
        "\n".join(json.dumps(s) for s in spans) + "\n", encoding="utf-8"
    )


def test_validate_annotations_good_spans_passes(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    spans = [
        {
            "span_id": "s1",
            "t_start_ns": 1000000,
            "t_end_ns": 2000000,
            "hand": "right",
            "action": "reaching",
            "action_text": "reach for cup",
            "object": "cup",
            "visibility": "visible",
            "confidence": 0.95,
            "source": "human",
            "verified": True,
        },
        {
            "span_id": "s2",
            "t_start_ns": 2000000,
            "t_end_ns": 4000000,
            "hand": "left",
            "action": "holding",
            "source": "argus_v0",
        },
    ]
    _write_spans(ep, spans)
    assert validate_annotations(ep) == []


def test_validate_annotations_blank_line_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    _write_spans(ep, [_min_span()])
    # Append a blank line
    path = ep / "annotations" / "spans.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    errs = validate_annotations(ep)
    assert any("blank line" in e for e in errs)


def test_validate_annotations_invalid_json_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    _write_spans(ep, [_min_span()])
    # Append a bad line
    (ep / "annotations" / "spans.jsonl").write_text(
        "{bad json}\n", encoding="utf-8"
    )
    errs = validate_annotations(ep)
    assert any("invalid JSON" in e for e in errs)


def test_validate_annotations_non_dict_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "annotations" / "spans.jsonl").parent.mkdir(parents=True)
    (ep / "annotations" / "spans.jsonl").write_text(
        json.dumps(["not", "a", "dict"]) + "\n", encoding="utf-8"
    )
    errs = validate_annotations(ep)
    assert any("expected JSON object" in e for e in errs)


def _min_span():
    return {
        "span_id": "s1",
        "t_start_ns": 1,
        "t_end_ns": 2,
        "hand": "right",
        "action": "idle",
    }


def test_validate_annotations_t_start_gt_t_end_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["t_start_ns"] = 5000000
    s["t_end_ns"] = 1000000
    s["action"] = "reaching"
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any(
        "t_start_ns" in e and "5000000" in e and "t_end_ns" in e
        for e in errs
    )


def test_validate_annotations_t_start_eq_t_end_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["t_start_ns"] = 1000000
    s["t_end_ns"] = 1000000
    s["action"] = "reaching"
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("t_start_ns" in e and "t_end_ns" in e for e in errs)


def test_validate_annotations_bad_t_ns_types_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["t_start_ns"] = "not_an_int"
    s["t_end_ns"] = 2000000
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("t_start_ns" in e and "int" in e for e in errs)


def test_validate_annotations_unknown_action_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["action"] = "unknown_action"
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("unknown_action" in e for e in errs)


def test_validate_annotations_bad_hand_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["hand"] = "left_foot"
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("hand" in e and "left_foot" in e for e in errs)


def test_validate_annotations_confidence_out_of_range_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["confidence"] = 1.5
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("confidence" in e and "1.5" in e for e in errs)


def test_validate_annotations_confidence_negative_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["confidence"] = -0.1
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("confidence" in e and "-0.1" in e for e in errs)


def test_validate_annotations_confidence_edge_cases_accepted(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s1 = _min_span()
    s1["confidence"] = 0.0
    s2 = _min_span()
    s2["span_id"] = "s2"
    s2["t_start_ns"] = 2
    s2["t_end_ns"] = 3
    s2["hand"] = "left"
    s2["confidence"] = 1.0
    _write_spans(ep, [s1, s2])
    assert validate_annotations(ep) == []


def test_validate_annotations_bad_visibility_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["visibility"] = "invisible"
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("visibility" in e and "invisible" in e for e in errs)


def test_validate_annotations_bad_source_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["source"] = "unknown"
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("source" in e and "unknown" in e for e in errs)


def test_validate_annotations_iris_heuristic_source_passes(tmp_path):
    """D-13: iris_heuristic is an accepted span source (端上启发式粗分段)."""
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["source"] = "iris_heuristic"
    _write_spans(ep, [s])
    assert validate_annotations(ep) == []


def test_validate_annotations_bad_verified_type_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["verified"] = "yes"
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("verified" in e and "bool" in e for e in errs)


def test_validate_annotations_bad_action_text_type_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["action_text"] = 42
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("action_text" in e for e in errs)


def test_validate_annotations_bad_object_type_rejected(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    s = _min_span()
    s["object"] = True
    _write_spans(ep, [s])
    errs = validate_annotations(ep)
    assert any("object" in e for e in errs)


def test_validate_annotations_all_actions_accepted(tmp_path):
    """Every MANIPULATION_ACTIONS value should be accepted as a valid action."""
    ep = tmp_path / "ep"
    ep.mkdir()
    spans = []
    for i, action in enumerate(MANIPULATION_ACTIONS):
        spans.append({
            "span_id": f"s{i}",
            "t_start_ns": i * 1000,
            "t_end_ns": (i + 1) * 1000,
            "hand": "right",
            "action": action,
        })
    _write_spans(ep, spans)
    assert validate_annotations(ep) == []


def test_validate_annotations_all_hands_accepted(tmp_path):
    """Every ANNOTATION_HANDS value should be accepted."""
    ep = tmp_path / "ep"
    ep.mkdir()
    spans = []
    for i, hand in enumerate(ANNOTATION_HANDS):
        spans.append({
            "span_id": f"s{i}",
            "t_start_ns": i * 1000,
            "t_end_ns": (i + 1) * 1000,
            "hand": hand,
            "action": "idle",
        })
    _write_spans(ep, spans)
    assert validate_annotations(ep) == []


def test_validate_annotations_example_episode_hands_valid():
    """The episode_hands example ships with annotations/spans.jsonl — it must pass."""
    examples = Path(__file__).resolve().parent.parent / "examples" / "episode_hands"
    errs = validate_annotations(examples)
    assert errs == [], errs


def test_validate_annotations_existing_episodes_have_no_annotations():
    """Existing episodes have no annotations/spans.jsonl — must return empty (additive-only)."""
    examples = Path(__file__).resolve().parent.parent / "examples"
    for name in ("episode_0", "episode_quest", "episode_robot", "episode_dual_airbot"):
        ep = examples / name
        assert validate_annotations(ep) == [], f"{name} should have no annotations"
