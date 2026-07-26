"""Tests for the ecosystem importers (D-19a, split 2/4 — airbot-mcap smoke path).

Covers the airbot-mcap second-input smoke path. Fixtures are synthetic, self-made
data (see tests/fixtures/_generate.py) — no third-party real data.
"""
from __future__ import annotations

import json
from pathlib import Path

from mnesis_canonical.importers import _mcap
from mnesis_canonical.importers.__main__ import main
from mnesis_canonical.importers.airbot_mcap import convert as convert_mcap
from mnesis_canonical.io import read_jsonl
from mnesis_canonical.validate import validate_frames

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MCAP = FIXTURES / "airbot" / "airdc_synth.mcap"


# --- airbot-mcap second input (smoke) -----------------------------------------


def test_mcap_reader_roundtrips(tmp_path):
    path = tmp_path / "rt.mcap"
    msgs = [{"log_time": 10, "data": b'{"a":1}'}, {"log_time": 20, "data": b'{"a":2}'}]
    _mcap.write_messages(path, msgs, topic="/t", message_encoding="json")
    read = _mcap.read_messages(path)
    assert [m.log_time for m in read] == [10, 20]
    assert json.loads(read[0].data) == {"a": 1}
    assert read[0].channel.message_encoding == "json"


def test_mcap_import_smoke_produces_conformant_episode(tmp_path, capsys):
    out = tmp_path / "ep"
    rc = main(
        [
            "xrobotoolkit",
            str(MCAP),
            "--format",
            "airbot-mcap",
            "--embodiment",
            "dual_airbot_play",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    frames = read_jsonl(out / "data.jsonl")
    assert len(frames) == 4
    report = validate_frames(frames, strict_vocab=True)
    assert report.ok, report.errors
    meta = json.loads((out / "import_meta.json").read_text(encoding="utf-8"))
    assert meta["source"] == "imported_airbot_mcap"


def test_mcap_convert_holds_missing_cmd():
    frames, meta = convert_mcap(
        [
            {"t_ns": 1, "joint_state": [0.1, 0.2], "joint_cmd": [0.3, 0.4]},
            {"t_ns": 2, "joint_state": [0.5, 0.6], "joint_cmd": None},
        ]
    )
    assert frames[1]["action"] == [0.1, 0.2]  # held previous joint_state
    assert meta["quality"]["downgraded"] is True


# --- CLI -----------------------------------------------------------------------


def test_cli_no_command_returns_two(capsys):
    assert main([]) == 2


def test_cli_missing_file_returns_two(tmp_path, capsys):
    out = str(tmp_path / "ep")
    rc = main(
        ["xrobotoolkit", "does/not/exist.mcap", "--format", "airbot-mcap", "--out", out]
    )
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_cli_mcap_end_to_end(tmp_path, capsys):
    out = tmp_path / "ep"
    rc = main(["xrobotoolkit", str(MCAP), "--format", "airbot-mcap", "--out", str(out)])
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["frameCount"] == 4
    assert (out / "data.jsonl").exists()


# --- Bad MCAP ----------------------------------------------------------------


def test_mcap_bad_magic_raises(tmp_path):
    bad = tmp_path / "bad.mcap"
    bad.write_bytes(b"not mcap")
    import pytest
    with pytest.raises(ValueError, match="not an MCAP"):
        _mcap.read_messages(bad)


def test_mcap_unsupported_encoding_raises(tmp_path, capsys):
    """Write an MCAP with a non-json encoding and verify the importer rejects it."""
    msgs = [{"log_time": 1, "data": b"{}"}]
    path = tmp_path / "bad_enc.mcap"
    _mcap.write_messages(path, msgs, topic="/t", message_encoding="flatbuf")
    rc = main(["xrobotoolkit", str(path), "--format", "airbot-mcap", "--out", str(tmp_path / "ep")])
    assert rc == 1
    assert "unsupported" in capsys.readouterr().err


# --- XRoboToolkit pickle (third input) ----------------------------------------


PKL = FIXTURES / "xrobotoolkit" / "teleop_log_synth.pkl"


def test_pickle_convert_basic():
    from mnesis_canonical.importers.xrobotoolkit import convert as convert_pkl

    frames, meta = convert_pkl(
        [
            {"t_ns": 1, "joint_state": [0.1, 0.2], "joint_cmd": [0.3, 0.4]},
            {"t_ns": 2, "joint_state": [0.5, 0.6], "joint_cmd": None},
        ]
    )
    assert len(frames) == 2
    assert frames[0]["action"] == [0.3, 0.4]
    assert frames[1]["action"] == [0.1, 0.2]  # held last joint_state
    assert meta["quality"]["downgraded"] is True


def test_pickle_convert_gripper():
    from mnesis_canonical.importers.xrobotoolkit import convert as convert_pkl

    frames, _ = convert_pkl(
        [
            {
                "t_ns": 1,
                "joint_state": [0.1, 0.2],
                "joint_cmd": [0.3, 0.4],
                "gripper": 0.75,
                "gripper_left": 0.8,
                "gripper_right": 0.7,
            },
        ]
    )
    assert frames[0]["action.gripper"] == 0.75
    assert frames[0]["observation.gripper.left"] == 0.8
    assert frames[0]["observation.gripper.right"] == 0.7


def test_pickle_convert_empty_raises():
    import pytest

    from mnesis_canonical.importers.xrobotoolkit import convert as convert_pkl
    with pytest.raises(ValueError, match="no messages"):
        convert_pkl([])


def test_pickle_import_smoke_produces_conformant_episode(tmp_path, capsys):
    out = tmp_path / "ep"
    rc = main(
        [
            "xrobotoolkit",
            str(PKL),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    frames = read_jsonl(out / "data.jsonl")
    assert len(frames) == 4
    report = validate_frames(frames, strict_vocab=True)
    assert report.ok, report.errors
    meta = json.loads((out / "import_meta.json").read_text(encoding="utf-8"))
    assert meta["source"] == "imported_xrobotoolkit_pickle"
    assert meta["importer"] == "xrobotoolkit"
    # Verify gripper fields survived (present in the synthetic fixture).
    assert "action.gripper" in frames[0]
    assert "observation.gripper.left" in frames[0]
    assert "observation.gripper.right" in frames[0]


def test_pickle_cli_end_to_end(tmp_path, capsys):
    out = tmp_path / "ep"
    rc = main(["xrobotoolkit", str(PKL), "--out", str(out)])
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["frameCount"] == 4
    assert (out / "data.jsonl").exists()


def test_pickle_cli_missing_file_returns_two(tmp_path, capsys):
    rc = main(["xrobotoolkit", "does/not/exist.pkl", "--out", str(tmp_path / "ep")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_pickle_bad_data_raises(tmp_path, capsys):
    bad = tmp_path / "bad.pkl"
    bad.write_bytes(b"not a pickle")
    rc = main(["xrobotoolkit", str(bad), "--out", str(tmp_path / "ep")])
    assert rc == 1
    assert "invalid load key" in capsys.readouterr().err


def test_pickle_empty_list_raises(tmp_path, capsys):
    import pickle
    empty = tmp_path / "empty.pkl"
    with open(empty, "wb") as f:
        pickle.dump([], f)
    rc = main(["xrobotoolkit", str(empty), "--out", str(tmp_path / "ep")])
    assert rc == 1
    assert "no messages" in capsys.readouterr().err


def test_pickle_dict_with_messages_key(tmp_path, capsys):
    """Verify the importer accepts a dict with a 'messages' key."""
    import pickle
    p = tmp_path / "wrapped.pkl"
    msg = {"t_ns": 1, "joint_state": [0.1, 0.2], "joint_cmd": [0.3, 0.4]}
    with open(p, "wb") as f:
        pickle.dump({"messages": [msg]}, f)
    rc = main(["xrobotoolkit", str(p), "--out", str(tmp_path / "ep2")])
    assert rc == 0
    frames = read_jsonl(tmp_path / "ep2" / "data.jsonl")
    assert len(frames) == 1


def test_pickle_convert_holds_missing_cmd():
    from mnesis_canonical.importers.xrobotoolkit import convert as convert_pkl

    frames, meta = convert_pkl(
        [
            {"t_ns": 1, "joint_state": [0.1, 0.2], "joint_cmd": [0.3, 0.4]},
            {"t_ns": 2, "joint_state": [0.5, 0.6], "joint_cmd": None},
        ]
    )
    assert frames[1]["action"] == [0.1, 0.2]  # held previous joint_state
    assert meta["quality"]["downgraded"] is True