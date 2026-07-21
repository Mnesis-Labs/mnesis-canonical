"""Tests for the ecosystem importers (D-19a).

Covers the XRoboToolkit pickle core end-to-end (conformance) and the
airbot-mcap second-input smoke path. Fixtures are synthetic, self-made data
(see tests/fixtures/_generate.py) — no third-party real data.
"""
from __future__ import annotations

import json
from pathlib import Path

from mnesis_canonical.importers import _mcap
from mnesis_canonical.importers.__main__ import main
from mnesis_canonical.importers.airbot_mcap import convert as convert_mcap
from mnesis_canonical.importers.xrobotoolkit import import_pickle
from mnesis_canonical.io import read_jsonl
from mnesis_canonical.validate import validate_frames

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PICKLE = FIXTURES / "xrobotoolkit" / "teleop_log_synth.pkl"
MCAP = FIXTURES / "airbot" / "airdc_synth.mcap"


# --- XRoboToolkit pickle core -------------------------------------------------


def test_pickle_import_produces_conformant_episode(tmp_path):
    out = tmp_path / "ep"
    summary = import_pickle(PICKLE, out)
    assert summary["frameCount"] == 5

    frames = read_jsonl(out / "data.jsonl")
    report = validate_frames(frames, strict_vocab=True)
    assert report.ok, report.errors
    assert all(f["profile"] == "robot_v2" for f in frames)
    assert all(f["embodiment_id"] == "airbot_play" for f in frames)


def test_pickle_import_writes_jpg_camera_frames(tmp_path):
    out = tmp_path / "ep"
    import_pickle(PICKLE, out)
    jpgs = sorted((out / "frames").glob("*.jpg"))
    assert len(jpgs) == 5
    # JPG bytes were extracted from the pickle and start with the SOI marker.
    assert jpgs[0].read_bytes()[:2] == b"\xff\xd8"
    frames = read_jsonl(out / "data.jsonl")
    assert frames[0]["observation.images.ego"] == "frames/000000_ego.jpg"


def test_pickle_import_meta_declares_provenance_and_downgrade(tmp_path):
    out = tmp_path / "ep"
    import_pickle(PICKLE, out)
    meta = json.loads((out / "import_meta.json").read_text(encoding="utf-8"))
    assert meta["source"] == "imported_xrobotoolkit"
    assert meta["quality"]["downgraded"] is True
    assert meta["fillStrategy"]  # explicit fill strategy declared
    # Frame 3 in the fixture omits the commanded action → hold-last fill recorded.
    assert any("hold_last" in f for f in meta["filledFields"])
    assert "xr_input" in meta["droppedFields"]


def test_pickle_import_manifest_matches_data(tmp_path):
    out = tmp_path / "ep"
    import_pickle(PICKLE, out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["frameCount"] == 5
    assert manifest["episodeIndex"] == 0


def test_pickle_action_hold_fill_duplicates_last_state(tmp_path):
    """The missing-action frame holds the previous observed joint_pos."""
    out = tmp_path / "ep"
    import_pickle(PICKLE, out)
    frames = read_jsonl(out / "data.jsonl")
    # Fixture drops joint_action on frame index 3.
    assert frames[3]["action"] == frames[2]["observation.state"]


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
    rc = main(["xrobotoolkit", "does/not/exist.pkl", "--out", str(tmp_path / "ep")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_cli_pickle_end_to_end(tmp_path, capsys):
    out = tmp_path / "ep"
    rc = main(["xrobotoolkit", str(PICKLE), "--out", str(out)])
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["frameCount"] == 5
    assert (out / "data.jsonl").exists()
