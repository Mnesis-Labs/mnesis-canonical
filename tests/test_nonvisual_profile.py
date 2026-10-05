"""Explicit camera-less joint recording; not motion or training permission."""
from __future__ import annotations

import hashlib
import json

import pytest

from mnesis_canonical import validate_frame, validate_frame_jsonschema, validate_frames
from mnesis_canonical.embodiment_registry import load_embodiment

# Actual ED CPU writer output (597 UTF-8 bytes including newline). Portable:
# no private filesystem path and no camera placeholder. Only profile is changed
# by the proposed contract test; the original robot_v2 payload stays unchanged.
ED_JSONL = (
    '{"index":0,"episode_index":1,"task_index":0,"frame_index":0,'
    '"t_ns":1500000000,"t_hw_ns":987654321,"timestamp":"2026-09-30T12:00:00.500Z",'
    '"head_pose_SE3":[0.10000000149011612,1.600000023841858,-0.25,'
    '-0.10000000149011612,-0.20000000298023224,0.30000001192092896,0.8999999761581421],'
    '"observation.state":[-5.1744245865847915E-06,0.48187917470932007,'
    '1.0758801698684692,-0.4807344973087311,-5.912746928515844E-06,0.8395251631736755],'
    '"action":[0,0,0,0,0,0.07000000029802322],"source.device":"quest",'
    '"source.modality":"teleop","tracking_state":"TRACKING",'
    '"profile":"robot_v2","embodiment_id":"so_arm101"}\n'
)


def nonvisual_frame():
    frame = json.loads(ED_JSONL)
    frame['profile'] = 'robot_nonvisual_v1'
    return frame


def test_explicit_nonvisual_accepts_actual_six_joint_head_action():
    frame = nonvisual_frame()
    assert validate_frame(frame) == []
    assert len(frame['head_pose_SE3']) == 7
    assert len(frame['observation.state']) == len(frame['action']) == 6
    assert frame['observation.state'] != frame['action']
    assert not any(k.startswith('observation.images.') for k in frame)


@pytest.mark.parametrize('identity', [None, '', 'unknown-model', '../so_arm101'])
def test_nonvisual_requires_actual_registered_identity(identity):
    frame = nonvisual_frame()
    frame['embodiment_id'] = identity
    assert any('registered embodiment_id' in e for e in validate_frame(frame))


def test_nonvisual_missing_identity_is_rejected():
    frame = nonvisual_frame()
    del frame['embodiment_id']
    assert any('registered embodiment_id' in e for e in validate_frame(frame))


@pytest.mark.parametrize('key', ['observation.state', 'action'])
@pytest.mark.parametrize('length', [0, 5, 7, 12])
def test_nonvisual_length_comes_from_registry_not_variable_shape(key, length):
    frame = nonvisual_frame()
    frame[key] = [0.0] * length
    assert any(f'{key} must have length 6' in e for e in validate_frame(frame))


@pytest.mark.parametrize('identity', ['so_arm101', 'alohamini', 'airbot_play'])
def test_nonvisual_uses_each_actual_registry_joint_count(identity):
    frame = nonvisual_frame()
    frame['embodiment_id'] = identity
    count = len(load_embodiment(identity)['joint_names'])
    frame['observation.state'] = [0.1] * count
    frame['action'] = [0.0] * count
    assert validate_frame(frame) == []


@pytest.mark.parametrize('key', ['observation.images.front', 'observation.images.ego',
                               'observation.images.'])
@pytest.mark.parametrize('value', ['', None, 'frames/000000_front.jpg'])
def test_nonvisual_rejects_any_image_key_not_only_empty_placeholders(key, value):
    frame = nonvisual_frame()
    frame[key] = value
    assert any('nonvisual' in e and 'image' in e for e in validate_frame(frame))


@pytest.mark.parametrize('nonvisual_first', [True, False])
def test_nonvisual_episode_rejects_mixed_visual_profile(nonvisual_first):
    nonvisual = nonvisual_frame()
    visual = json.loads(ED_JSONL)
    visual['observation.images.front'] = 'frames/000001_front.jpg'
    frames = [nonvisual, visual] if nonvisual_first else [visual, nonvisual]
    frames[1]['frame_index'] = 1
    assert all(validate_frame(frame) == [] for frame in frames)
    report = validate_frames(frames)
    assert not report.ok
    assert any('mixed profile' in e for _, e in report.errors)


def test_nonvisual_episode_rejects_registered_embodiment_switch():
    first = nonvisual_frame()
    second = nonvisual_frame()
    second['frame_index'] = 1
    second['embodiment_id'] = 'alohamini'
    count = len(load_embodiment('alohamini')['joint_names'])
    second['observation.state'] = [0.0] * count
    second['action'] = [0.1] * count
    assert validate_frame(second) == []
    report = validate_frames([first, second])
    assert not report.ok
    assert any('embodiment_id changed' in e for _, e in report.errors)


@pytest.mark.parametrize('key', ['head_pose_SE3', 'observation.state', 'action'])
def test_nonvisual_null_vector_is_not_missing_information_pass(key):
    frame = nonvisual_frame()
    frame[key] = None
    assert any(key in e for e in validate_frame(frame))


def test_nonvisual_jsonschema_accepts_real_joint_head_structure():
    pytest.importorskip('jsonschema')
    assert validate_frame_jsonschema(nonvisual_frame()) == []


@pytest.mark.parametrize('key', ['observation.images.front', 'observation.images.'])
@pytest.mark.parametrize('value', ['', 'frames/000000_front.jpg'])
def test_nonvisual_jsonschema_forbids_any_image_key(key, value):
    pytest.importorskip('jsonschema')
    frame = nonvisual_frame()
    frame[key] = value
    assert validate_frame_jsonschema(frame)


@pytest.mark.parametrize('mutation', ['missing_identity', 'empty_identity', 'null_identity',
                                     'empty_state', 'empty_action'])
def test_nonvisual_jsonschema_requires_explicit_nonempty_structure(mutation):
    pytest.importorskip('jsonschema')
    frame = nonvisual_frame()
    if mutation == 'missing_identity':
        del frame['embodiment_id']
    elif mutation == 'empty_identity':
        frame['embodiment_id'] = ''
    elif mutation == 'null_identity':
        frame['embodiment_id'] = None
    else:
        frame['observation.state' if mutation == 'empty_state' else 'action'] = []
    assert validate_frame_jsonschema(frame)


def test_portable_payload_is_the_fixed_actual_ed_597_byte_output():
    payload = ED_JSONL.encode('utf-8')
    assert len(payload) == 597
    assert hashlib.sha256(payload).hexdigest() == (
        'f26bf44911aece06eaf66df592834a3d59ace7c35143996a0627742882d9ac54'
    )
    original = json.loads(ED_JSONL)
    candidate = nonvisual_frame()
    assert {k: v for k, v in candidate.items() if k != 'profile'} == {
        k: v for k, v in original.items() if k != 'profile'
    }
    assert any('at least one observation.images.' in e for e in validate_frame(original))


def test_old_visual_positives_and_default_are_unchanged(good_frame):
    assert validate_frame(good_frame()) == []
    robot = json.loads(ED_JSONL)
    robot['observation.images.front'] = 'frames/000000_front.jpg'
    assert validate_frame(robot) == []
    candidate = nonvisual_frame()
    del candidate['profile']
    assert validate_frame(candidate)


@pytest.mark.parametrize('profile', ['', 'unknown', 'ROBOT_NONVISUAL_V1'])
def test_nonvisual_needs_exact_explicit_profile(profile):
    frame = nonvisual_frame()
    frame['profile'] = profile
    assert validate_frame(frame)


@pytest.mark.parametrize('key', ['head_pose_SE3', 'observation.state', 'action'])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), True, '0'])
def test_nonvisual_existing_finite_numeric_guards_are_preserved(key, value):
    frame = nonvisual_frame()
    frame[key][0] = value
    assert any(key in e for e in validate_frame(frame))


@pytest.mark.parametrize('key', ['head_pose_SE3', 'observation.state', 'action'])
@pytest.mark.parametrize('value', [{}, '0', 0])
def test_nonvisual_nonlist_vector_is_rejected(key, value):
    frame = nonvisual_frame()
    frame[key] = value
    assert any(key in e for e in validate_frame(frame))


@pytest.mark.parametrize('key', list(json.loads(ED_JSONL).keys())[:-2])
def test_nonvisual_missing_common_field_is_rejected(key):
    frame = nonvisual_frame()
    del frame[key]
    assert any(key in e for e in validate_frame(frame))


@pytest.mark.parametrize('indices', [[0, 0], [1, 0], [-1]])
def test_nonvisual_existing_frame_index_guards_are_preserved(indices):
    frames = []
    for index in indices:
        frame = nonvisual_frame()
        frame['frame_index'] = index
        frames.append(frame)
    assert not validate_frames(frames).ok


def test_nonvisual_explicit_zero_and_increasing_indices_are_valid():
    first = nonvisual_frame()
    first['observation.state'] = [0.0] * 6
    first['action'] = [0.0] * 6
    second = dict(first, frame_index=1)
    assert validate_frames([first, second], strict_vocab=True).ok
    first['frame_index'] = True
    assert not validate_frames([first]).ok


@pytest.mark.parametrize('mutation', ['unknown_registry', 'wrong_registry_length'])
def test_jsonschema_is_structure_only_registry_validation_is_required(mutation):
    pytest.importorskip('jsonschema')
    frame = nonvisual_frame()
    if mutation == 'unknown_registry':
        frame['embodiment_id'] = 'not-registered'
    else:
        frame['action'] = [0.0]
    # Generic JSON Schema cannot resolve bundled joint_names; Python is mandatory.
    assert validate_frame_jsonschema(frame) == []
    assert validate_frame(frame)


@pytest.mark.parametrize('identity', ['ego_human', 'ego_human_5cam_v1'])
def test_nonvisual_rejects_empty_vectors_for_registered_human_joint_layout(identity):
    frame = nonvisual_frame()
    frame['embodiment_id'] = identity
    assert len(load_embodiment(identity)['joint_names']) == 14
    frame['observation.state'] = []
    frame['action'] = []
    assert validate_frame(frame)
