"""Episode manifest helpers (SPEC §Episode layout).

An episode's optional ``manifest.json`` sidecar summarises the episode for
upload / ingest. Shape (camelCase, per SPEC):

    {episodeIndex, frameCount, jsonlSizeBytes, videoPath, videoSizeBytes, durationMs}

``durationMs`` is derived from the wall-clock ``t_ns`` span of the frames. The
video sidecar itself is binary capture *data* and is never produced or committed
here; the manifest only references it when a ``video.mp4`` is present on disk.
"""
from __future__ import annotations

import json
from pathlib import Path

from .io import read_jsonl


def build_manifest(
    frames: list[dict],
    *,
    jsonl_size_bytes: int,
    video_path: str | None = None,
    video_size_bytes: int = 0,
) -> dict:
    """Build a manifest dict from in-memory frames (pure; no I/O).

    Raises ValueError on an empty episode (a manifest needs at least one frame).
    """
    if not frames:
        raise ValueError("cannot build a manifest for an empty episode")
    t = [f["t_ns"] for f in frames]
    return {
        "episodeIndex": frames[0]["episode_index"],
        "frameCount": len(frames),
        "jsonlSizeBytes": jsonl_size_bytes,
        "videoPath": video_path,
        "videoSizeBytes": video_size_bytes,
        "durationMs": round((max(t) - min(t)) / 1_000_000),
    }


def manifest_for_episode(episode_dir: str | Path) -> dict:
    """Read ``<episode_dir>/data.jsonl`` (and ``video.mp4`` if present) and build
    the manifest, filling in real on-disk sizes."""
    episode_dir = Path(episode_dir)
    jsonl = episode_dir / "data.jsonl"
    frames = read_jsonl(jsonl)
    video = episode_dir / "video.mp4"
    if video.exists():
        video_path: str | None = video.name
        video_size = video.stat().st_size
    else:
        video_path, video_size = None, 0
    return build_manifest(
        frames,
        jsonl_size_bytes=jsonl.stat().st_size,
        video_path=video_path,
        video_size_bytes=video_size,
    )


def write_manifest(episode_dir: str | Path, *, indent: int = 2) -> Path:
    """Compute and write ``<episode_dir>/manifest.json``; return its path."""
    episode_dir = Path(episode_dir)
    manifest = manifest_for_episode(episode_dir)
    out = episode_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=indent) + "\n", encoding="utf-8")
    return out
