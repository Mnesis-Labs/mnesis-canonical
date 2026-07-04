"""Shared pytest fixtures for the Canonical Schema test suite."""
from __future__ import annotations

import pytest


@pytest.fixture
def good_frame():
    """Factory returning a fresh, valid CanonicalFrame dict on each call.

    Returned as a factory (not a plain dict) so tests can mutate their own copy
    without cross-test contamination.
    """

    def _make() -> dict:
        return {
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

    return _make
