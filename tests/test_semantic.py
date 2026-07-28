"""Conformance for the dual-endpoint semantic contract (C12, PS0).

The point of C12 is that the robot end and the headset end produce the SAME
thing, so these tests pin the properties a consumer on either end is allowed to
rely on: the enum contains ``headset`` / ``human`` from day one, ``class_id``
comes from the registered taxonomy and nowhere else, ``frame_id`` refuses a local
frame, ``dispute`` exists exactly when the state says so, and the three 8442
message types stay low-frequency.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnesis_canonical import (
    COLOCALIZATION_STALE_EVENT,
    COLOCALIZATION_STATES,
    LABEL_FRAME_IDS,
    LABEL_SOURCES,
    LABEL_STATES,
    OBJECT_CLASS_TAXONOMY,
    PS_MAX_HZ,
    PS_MESSAGE_TYPES,
    SCENE_GRAPH_RATE_HZ,
    TELEOP_FRAME_HZ,
    list_taxonomies,
    list_taxonomy_ids,
    list_term_ids,
    load_semantic_schema,
    load_taxonomy,
    object_class_ids,
    validate_observation_label,
    validate_ps_message,
    validate_ps_message_jsonschema,
    validate_ps_stream,
    validate_scene_graph,
)

ROOT = Path(__file__).resolve().parent.parent
TAXONOMIES_DIR = ROOT / "taxonomies"
PKG_TAXONOMIES_DIR = ROOT / "mnesis_canonical" / "taxonomies"
SAMPLES_DIR = ROOT / "examples" / "semantic"
SAMPLES = sorted(SAMPLES_DIR.glob("*.json"))

T0 = 1_785_196_800_000_000_000  # 2026-07-28T00:00:00Z in Unix nanoseconds


def _label(**overrides) -> dict:
    label = {
        "label_id": "b6b4a3e2-6c2f-4f3f-9a1a-1d2e3f4a5b6c",
        "class_id": "cup",
        "confidence": 0.87,
        "source": "robot",
        "sensor": "cam_overhead",
        "frame_id": "map",
        "pose": {"t": [0.4, 0.9, -0.2], "q": [0.0, 0.0, 0.0, 1.0]},
        "extent": [0.08, 0.11, 0.08],
        "observed_at_ns": T0,
    }
    label.update(overrides)
    return label


def _graph_label(**overrides) -> dict:
    verdict = {"state": "confirmed", "witnesses": ["robot", "headset"]}
    verdict.update(overrides)
    return _label(**verdict)


def _graph(**overrides) -> dict:
    graph = {
        "map_id": "lab_bench_a",
        "revision": 42,
        "updated_at_ns": T0,
        "labels": [_graph_label()],
    }
    graph.update(overrides)
    return graph


def _msg(mtype: str, body: dict, *, seq: int = 1, ts: int = T0) -> dict:
    return {"type": mtype, "seq": seq, "ts": ts, "body": body}


# ── taxonomy registry: the class_id value domain ─────────────────────────────


def test_object_class_taxonomy_is_registered():
    assert OBJECT_CLASS_TAXONOMY in list_taxonomy_ids()
    entry = load_taxonomy(OBJECT_CLASS_TAXONOMY)
    assert entry["classes"], "object taxonomy must not be empty"


def test_object_class_ids_are_unique_and_snake_case():
    ids = object_class_ids()
    assert len(ids) == len(set(ids)), "duplicate class ids"
    for cid in ids:
        assert cid.islower() and cid.replace("_", "").isalnum(), cid


def test_object_classes_cover_the_dispute_example():
    # The C12 worked example is robot:'cup' vs headset:'bottle' — both must exist.
    assert {"cup", "bottle"} <= set(object_class_ids())


def test_every_class_carries_a_definition():
    """A term without a boundary is how two repos label the same object differently."""
    for term in load_taxonomy(OBJECT_CLASS_TAXONOMY)["classes"]:
        assert term.get("definition"), f"{term['id']} has no definition"
        assert term.get("name_en"), f"{term['id']} has no name_en"


def test_manipulation_taxonomy_still_resolves():
    """The registry must serve the pre-existing taxonomy too, not just the new one."""
    assert "manipulation_v1" in list_taxonomy_ids()
    assert "reaching" in list_term_ids("manipulation_v1")


def test_unknown_taxonomy_raises():
    with pytest.raises(LookupError):
        load_taxonomy("no_such_taxonomy")


def test_package_taxonomies_sync_with_root():
    """Package-level taxonomies must match root-level ones byte-for-byte."""
    names = {p.name for p in TAXONOMIES_DIR.glob("*.json")}
    assert names, "root taxonomies/ is empty"
    for name in names:
        assert (PKG_TAXONOMIES_DIR / name).exists(), f"{name} missing from package"
        assert (PKG_TAXONOMIES_DIR / name).read_bytes() == (
            TAXONOMIES_DIR / name
        ).read_bytes(), f"{name} differs between root taxonomies/ and package taxonomies/"


@pytest.mark.parametrize("entry", list_taxonomies(), ids=lambda e: e["taxonomy_id"])
def test_taxonomies_match_their_schema(entry):
    pytest.importorskip("jsonschema")
    import jsonschema

    schema = json.loads(
        (PKG_TAXONOMIES_DIR / "taxonomy.schema.json").read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(schema)
    errs = [e.message for e in validator.iter_errors(entry)]
    assert errs == [], f"{entry['taxonomy_id']}: {errs}"


def test_schema_class_enum_matches_the_taxonomy():
    """The JSON Schema enum is generated from the taxonomy — it must not drift.

    The schema is what the headset end (JavaScript, no Python dependency)
    validates against, so a drift here means one end accepts a class the other
    rejects.
    """
    schema_enum = load_semantic_schema()["$defs"]["class_id"]["enum"]
    assert tuple(schema_enum) == object_class_ids()


# ── ObservationLabel ─────────────────────────────────────────────────────────


def test_good_label_validates():
    assert validate_observation_label(_label()) == []


def test_label_without_optional_keys_validates():
    label = _label()
    del label["sensor"]
    del label["extent"]
    assert validate_observation_label(label) == []


def test_source_enum_carries_headset_and_human_from_day_one():
    # PS4 (headset recognition) and human adjudication are backlog, but widening
    # an enum later is a contract change every consumer has to revisit.
    assert LABEL_SOURCES == ("robot", "headset", "human")
    for source in LABEL_SOURCES:
        assert validate_observation_label(_label(source=source)) == []


def test_unknown_source_rejected():
    errs = validate_observation_label(_label(source="cloud"))
    assert any("source" in e for e in errs)


def test_class_id_must_come_from_the_taxonomy():
    errs = validate_observation_label(_label(class_id="teacup"))
    assert any(OBJECT_CLASS_TAXONOMY in e for e in errs)


def test_local_frame_id_rejected():
    """A label in a sensor-local frame is not fusable — reject, don't mis-fuse."""
    assert LABEL_FRAME_IDS == ("map",)
    for bad in ("cam_overhead", "headset", "base_link", "world"):
        errs = validate_observation_label(_label(frame_id=bad))
        assert any("frame_id" in e for e in errs), bad


def test_confidence_range_enforced():
    assert validate_observation_label(_label(confidence=0.0)) == []
    assert validate_observation_label(_label(confidence=1.0)) == []
    for bad in (-0.1, 1.1, "high", None, float("nan")):
        assert validate_observation_label(_label(confidence=bad)), bad


def test_confidence_is_required():
    label = _label()
    del label["confidence"]
    assert any("confidence" in e for e in validate_observation_label(label))


def test_pose_quaternion_must_be_unit():
    errs = validate_observation_label(
        _label(pose={"t": [0, 0, 0], "q": [0.0, 0.0, 0.0, 0.5]})
    )
    assert any("unit quaternion" in e for e in errs)


def test_pose_must_be_finite():
    errs = validate_observation_label(
        _label(pose={"t": [0, float("inf"), 0], "q": [0.0, 0.0, 0.0, 1.0]})
    )
    assert any("finite" in e for e in errs)


def test_extent_absent_means_unknown_not_zero():
    """SPEC §Conventions iron rule: omit the key, never a zero-sized box."""
    label = _label()
    del label["extent"]
    assert validate_observation_label(label) == []
    assert validate_observation_label(_label(extent=[0.0, 0.1, 0.1]))
    assert validate_observation_label(_label(extent=None))


def test_observed_at_is_nanoseconds_int():
    # One time unit across the standard (t_ns / t_hw_ns / observed_at_ns).
    assert any(
        "nanoseconds" in e
        for e in validate_observation_label(_label(observed_at_ns=1785196800.123))
    )


def test_missing_label_id_rejected():
    label = _label()
    del label["label_id"]
    assert any("label_id" in e for e in validate_observation_label(label))


# ── scene_graph ──────────────────────────────────────────────────────────────


def test_good_scene_graph_validates():
    assert validate_scene_graph(_graph()) == []


def test_empty_label_list_is_valid():
    """An empty map is a real state, distinct from 'no scene graph'."""
    assert validate_scene_graph(_graph(labels=[])) == []


def test_all_label_states_validate():
    assert LABEL_STATES == ("confirmed", "unconfirmed", "disputed", "stale")
    for state in ("confirmed", "unconfirmed", "stale"):
        assert validate_scene_graph(_graph(labels=[_graph_label(state=state)])) == []
    disputed = _graph_label(state="disputed", dispute={"robot": "cup", "headset": "bottle"})
    assert validate_scene_graph(_graph(labels=[disputed])) == []


def test_dispute_required_exactly_when_disputed():
    missing = _graph_label(state="disputed")
    assert any("dispute" in e for e in validate_scene_graph(_graph(labels=[missing])))

    spurious = _graph_label(state="confirmed", dispute={"robot": "cup", "headset": "bottle"})
    assert any("dispute" in e for e in validate_scene_graph(_graph(labels=[spurious])))


def test_dispute_must_actually_disagree():
    agreeing = _graph_label(state="disputed", dispute={"robot": "cup", "headset": "cup"})
    assert any("differing" in e for e in validate_scene_graph(_graph(labels=[agreeing])))

    single = _graph_label(state="disputed", dispute={"robot": "cup"})
    assert any("two" in e for e in validate_scene_graph(_graph(labels=[single])))


def test_dispute_classes_come_from_the_taxonomy():
    bad = _graph_label(state="disputed", dispute={"robot": "cup", "headset": "flask"})
    assert any(OBJECT_CLASS_TAXONOMY in e for e in validate_scene_graph(_graph(labels=[bad])))


def test_dispute_keys_must_be_witnesses():
    bad = _graph_label(
        state="disputed",
        witnesses=["robot"],
        dispute={"robot": "cup", "headset": "bottle"},
    )
    assert any("witnesses" in e for e in validate_scene_graph(_graph(labels=[bad])))


def test_witnesses_must_include_own_source():
    bad = _graph_label(source="robot", witnesses=["headset"])
    assert any("witnesses" in e for e in validate_scene_graph(_graph(labels=[bad])))


def test_witnesses_must_be_known_sources_and_unique():
    assert validate_scene_graph(_graph(labels=[_graph_label(witnesses=["robot", "cloud"])]))
    assert validate_scene_graph(_graph(labels=[_graph_label(witnesses=["robot", "robot"])]))
    assert validate_scene_graph(_graph(labels=[_graph_label(witnesses=[])]))


def test_duplicate_label_id_rejected():
    graph = _graph(labels=[_graph_label(), _graph_label()])
    assert any("duplicates" in e for e in validate_scene_graph(graph))


def test_revision_must_be_non_negative_int():
    assert any("revision" in e for e in validate_scene_graph(_graph(revision=-1)))
    assert any("revision" in e for e in validate_scene_graph(_graph(revision=1.5)))


def test_scene_graph_label_is_a_valid_observation_label():
    """A scene-graph label is an ObservationLabel plus a verdict — not a variant."""
    label = _graph_label()
    base = {k: v for k, v in label.items() if k not in ("state", "witnesses", "dispute")}
    assert validate_observation_label(base) == []


# ── 8442 messages (envelope v1) ──────────────────────────────────────────────


def test_message_types():
    assert PS_MESSAGE_TYPES == ("semantic_label", "scene_graph", "colocalization")


def test_envelope_keys_required():
    msg = _msg("scene_graph", _graph())
    for key in ("type", "seq", "ts", "body"):
        broken = {k: v for k, v in msg.items() if k != key}
        assert any(key in e for e in validate_ps_message(broken)), key


def test_envelope_seq_is_uint32():
    assert validate_ps_message(_msg("scene_graph", _graph(), seq=-1))
    assert validate_ps_message(_msg("scene_graph", _graph(), seq=2**32))
    assert validate_ps_message(_msg("scene_graph", _graph(), seq=2**32 - 1)) == []


def test_unknown_message_type_rejected():
    assert validate_ps_message(_msg("semantic_labels", _graph()))


def test_semantic_label_message_validates():
    body = {"map_id": "lab_bench_a", "labels": [_label(source="headset")]}
    assert validate_ps_message(_msg("semantic_label", body)) == []


def test_semantic_label_uplink_rejects_robot_source():
    """A robot label is already on the authoritative side; it never travels up."""
    body = {"map_id": "lab_bench_a", "labels": [_label(source="robot")]}
    errs = validate_ps_message(_msg("semantic_label", body))
    assert any("source" in e for e in errs)


def test_semantic_label_accepts_human_adjudication():
    body = {"map_id": "lab_bench_a", "labels": [_label(source="human", confidence=1.0)]}
    assert validate_ps_message(_msg("semantic_label", body)) == []


def test_semantic_label_requires_at_least_one_label():
    body = {"map_id": "lab_bench_a", "labels": []}
    assert any("labels" in e for e in validate_ps_message(_msg("semantic_label", body)))


def test_colocalization_ok_requires_extrinsic_and_quality():
    ok = {
        "map_id": "lab_bench_a",
        "state": "ok",
        "T_map_headset": {"t": [1.2, 0.0, -0.5], "q": [0.0, 0.0, 0.0, 1.0]},
        "computed_at_ns": T0,
        "quality": {"rmse_m": 0.014, "inlier_ratio": 0.91, "match_count": 428},
    }
    assert validate_ps_message(_msg("colocalization", ok)) == []

    no_t = {k: v for k, v in ok.items() if k != "T_map_headset"}
    assert any("T_map_headset" in e for e in validate_ps_message(_msg("colocalization", no_t)))

    no_q = {k: v for k, v in ok.items() if k != "quality"}
    assert any("quality" in e for e in validate_ps_message(_msg("colocalization", no_q)))


def test_colocalization_lost_must_omit_the_extrinsic():
    """Never publish identity as a stand-in — it silently parks labels at the origin."""
    lost = {
        "map_id": "lab_bench_a",
        "state": "lost",
        "T_map_headset": {"t": [0.0, 0.0, 0.0], "q": [0.0, 0.0, 0.0, 1.0]},
        "computed_at_ns": T0,
    }
    assert any("T_map_headset" in e for e in validate_ps_message(_msg("colocalization", lost)))

    del lost["T_map_headset"]
    del lost["computed_at_ns"]
    assert validate_ps_message(_msg("colocalization", lost)) == []


def test_colocalization_stale_event_is_this_message_not_a_fourth_type():
    stale = {
        "map_id": "lab_bench_a",
        "state": "stale",
        "T_map_headset": {"t": [1.2, 0.0, -0.5], "q": [0.0, 0.0, 0.0, 1.0]},
        "computed_at_ns": T0,
        "event": COLOCALIZATION_STALE_EVENT,
        "reason": "tracking recovered; extrinsic not re-solved",
    }
    assert validate_ps_message(_msg("colocalization", stale)) == []
    assert COLOCALIZATION_STALE_EVENT not in PS_MESSAGE_TYPES


def test_colocalization_stale_event_contradicts_ok_state():
    bad = {
        "map_id": "lab_bench_a",
        "state": "ok",
        "T_map_headset": {"t": [1.2, 0.0, -0.5], "q": [0.0, 0.0, 0.0, 1.0]},
        "computed_at_ns": T0,
        "quality": {"rmse_m": 0.01, "inlier_ratio": 0.9},
        "event": COLOCALIZATION_STALE_EVENT,
    }
    assert any("contradicts" in e for e in validate_ps_message(_msg("colocalization", bad)))


def test_colocalization_states():
    assert COLOCALIZATION_STATES == ("ok", "stale", "lost")
    assert validate_ps_message(
        _msg("colocalization", {"map_id": "m", "state": "unaligned"})
    )


def test_quality_ranges_enforced():
    body = {
        "map_id": "m",
        "state": "ok",
        "T_map_headset": {"t": [0, 0, 0], "q": [0, 0, 0, 1]},
        "computed_at_ns": T0,
        "quality": {"rmse_m": -1.0, "inlier_ratio": 1.4},
    }
    errs = validate_ps_message(_msg("colocalization", body))
    assert any("rmse_m" in e for e in errs)
    assert any("inlier_ratio" in e for e in errs)


# ── stream-level rules: low frequency is a HARD requirement ──────────────────


def test_rate_ceilings_stay_far_below_teleop():
    assert TELEOP_FRAME_HZ == 30.0
    assert SCENE_GRAPH_RATE_HZ == (1.0, 5.0)
    for mtype in PS_MESSAGE_TYPES:
        assert PS_MAX_HZ[mtype] <= 5.0 < TELEOP_FRAME_HZ


def test_scene_graph_at_5_hz_passes():
    step = 200_000_000  # 5 Hz
    stream = [
        _msg("scene_graph", _graph(revision=42 + i), seq=i, ts=T0 + i * step)
        for i in range(6)
    ]
    assert validate_ps_stream(stream) == []


def test_scene_graph_at_30_hz_rejected():
    step = 33_000_000  # ~30 Hz — teleop's rate, not semantics'
    stream = [
        _msg("scene_graph", _graph(revision=42 + i), seq=i, ts=T0 + i * step)
        for i in range(10)
    ]
    assert any("ceiling" in e for e in validate_ps_stream(stream))


def test_colocalization_above_1_hz_rejected():
    step = 200_000_000  # 5 Hz
    body = {"map_id": "m", "state": "lost"}
    stream = [_msg("colocalization", body, seq=i, ts=T0 + i * step) for i in range(5)]
    assert any("ceiling" in e for e in validate_ps_stream(stream))


def test_burst_at_one_timestamp_rejected():
    """Several observations at once are batched into one message, not burst."""
    body = {"map_id": "m", "labels": [_label(source="headset")]}
    stream = [_msg("semantic_label", body, seq=i, ts=T0) for i in range(3)]
    assert any("batch" in e for e in validate_ps_stream(stream))


def test_change_driven_silence_is_legal():
    """1-5 Hz is a ceiling with a nominal floor, not a heartbeat to implement."""
    stream = [
        _msg("scene_graph", _graph(revision=42), seq=1, ts=T0),
        _msg("scene_graph", _graph(revision=43), seq=2, ts=T0 + 60_000_000_000),
    ]
    assert validate_ps_stream(stream) == []


def test_seq_must_increase():
    stream = [
        _msg("scene_graph", _graph(revision=42), seq=7, ts=T0),
        _msg("scene_graph", _graph(revision=43), seq=7, ts=T0 + 1_000_000_000),
    ]
    assert any("seq" in e for e in validate_ps_stream(stream))


def test_revision_must_not_go_backwards():
    stream = [
        _msg("scene_graph", _graph(revision=43), seq=1, ts=T0),
        _msg("scene_graph", _graph(revision=42), seq=2, ts=T0 + 1_000_000_000),
    ]
    assert any("revision" in e for e in validate_ps_stream(stream))


def test_timestamps_must_not_go_backwards():
    stream = [
        _msg("scene_graph", _graph(revision=42), seq=1, ts=T0 + 1_000_000_000),
        _msg("scene_graph", _graph(revision=43), seq=2, ts=T0),
    ]
    assert any("ts" in e for e in validate_ps_stream(stream))


# ── golden samples ───────────────────────────────────────────────────────────


def test_golden_samples_discovered():
    names = {p.name for p in SAMPLES}
    assert {
        "semantic_label.json",
        "scene_graph.json",
        "colocalization.json",
        "colocalization_stale.json",
    } <= names


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_golden_sample_validates(path):
    msg = json.loads(path.read_text(encoding="utf-8"))
    assert validate_ps_message(msg) == []


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_golden_sample_validates_against_json_schema(path):
    pytest.importorskip("jsonschema")
    msg = json.loads(path.read_text(encoding="utf-8"))
    assert validate_ps_message_jsonschema(msg) == []


def test_golden_samples_cover_the_boundary_cases():
    """disputed / stale / source:'headset' — the three the consumers asked for."""
    graph = json.loads((SAMPLES_DIR / "scene_graph.json").read_text(encoding="utf-8"))
    labels = graph["body"]["labels"]
    states = {label["state"] for label in labels}
    assert {"confirmed", "unconfirmed", "disputed", "stale"} <= states

    disputed = [label for label in labels if label["state"] == "disputed"]
    assert disputed and disputed[0]["dispute"] == {"robot": "cup", "headset": "bottle"}

    uplink = json.loads((SAMPLES_DIR / "semantic_label.json").read_text(encoding="utf-8"))
    sources = {label["source"] for label in uplink["body"]["labels"]}
    assert "headset" in sources
    assert "human" in sources

    stale = json.loads(
        (SAMPLES_DIR / "colocalization_stale.json").read_text(encoding="utf-8")
    )
    assert stale["body"]["event"] == COLOCALIZATION_STALE_EVENT


def test_golden_stream_is_within_the_rate_ceilings():
    """The four samples, read as one capture, must not breach C12's low-frequency rule."""
    stream = sorted(
        (json.loads(p.read_text(encoding="utf-8")) for p in SAMPLES),
        key=lambda m: m["ts"],
    )
    assert validate_ps_stream(stream) == []


# ── JSON Schema mirror (the headset end validates against this, not Python) ──


def test_json_schema_and_python_agree_on_a_bad_class_id():
    pytest.importorskip("jsonschema")
    msg = _msg("semantic_label", {
        "map_id": "m",
        "labels": [_label(source="headset", class_id="teacup")],
    })
    assert validate_ps_message(msg)
    assert validate_ps_message_jsonschema(msg)


def test_json_schema_and_python_agree_on_a_local_frame():
    pytest.importorskip("jsonschema")
    msg = _msg("scene_graph", _graph(labels=[_graph_label(frame_id="cam_overhead")]))
    assert validate_ps_message(msg)
    assert validate_ps_message_jsonschema(msg)


def test_json_schema_rejects_dispute_on_a_confirmed_label():
    pytest.importorskip("jsonschema")
    msg = _msg("scene_graph", _graph(labels=[
        _graph_label(state="confirmed", dispute={"robot": "cup", "headset": "bottle"}),
    ]))
    assert validate_ps_message_jsonschema(msg)
