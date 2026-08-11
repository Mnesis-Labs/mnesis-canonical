"""Episode manifest helpers (SPEC §Episode layout).

An episode's optional ``manifest.json`` sidecar summarises the episode for
upload / ingest. Shape (camelCase, per SPEC):

    {episodeIndex, frameCount, jsonlSizeBytes, videoPath, videoSizeBytes, durationMs}

``durationMs`` is derived from the wall-clock ``t_ns`` span of the frames. The
video sidecar itself is binary capture *data* and is never produced or committed
here; the manifest only references it when a ``video.mp4`` is present on disk.

This module also provides :func:`validate_manifest` for consistency checks
between a manifest.json and its sibling data.jsonl (S2-5).

Side channels that have no dedicated pointer (IMU, audio, logs, calibration, …)
register via the generic ``sidecars[]`` array (SPEC §Episode layout). Each entry
carries a controlled ``kind`` plus its on-disk ``path`` and optional metadata.
"""
from __future__ import annotations

import json
from pathlib import Path

from .io import read_jsonl

_SCHEMA_PATH = Path(__file__).resolve().parent / "manifest.schema.json"
with open(_SCHEMA_PATH, encoding="utf-8") as _f:
    _MANIFEST_SCHEMA = json.loads(_f.read())

# Controlled vocabulary for sidecar ``kind`` (additive registration, SPEC §Episode
# layout). New kinds are added here, never invented ad hoc by a producer.
SIDECAR_KINDS = frozenset({"imu", "audio", "log", "calib"})

# Default ``kind``/``format`` for sidecar files discovered under a well-known
# subdirectory (used by :func:`manifest_for_episode` auto-discovery).
_SIDECAR_DIR_DEFAULTS = {
    "sensors": ("imu", "jsonl"),
    "audio": ("audio", "wav"),
    "logs": ("log", "jsonl"),
    "calib": ("calib", "json"),
}


def build_manifest(
    frames: list[dict],
    *,
    jsonl_size_bytes: int,
    video_path: str | None = None,
    video_size_bytes: int = 0,
    events_path: str | None = None,
    annotations_path: str | None = None,
    sidecars: list[dict] | None = None,
) -> dict:
    """Build a manifest dict from in-memory frames (pure; no I/O).

    ``sidecars`` is an optional list of sidecar descriptors (SPEC §Episode layout),
    each with at least ``kind`` and ``path``. ``kind`` must be in the controlled
    vocabulary :data:`SIDECAR_KINDS`.

    Raises ValueError on an empty episode (a manifest needs at least one frame).
    """
    if not frames:
        raise ValueError("cannot build a manifest for an empty episode")
    t = [f["t_ns"] for f in frames]
    result: dict = {
        "episodeIndex": frames[0]["episode_index"],
        "frameCount": len(frames),
        "jsonlSizeBytes": jsonl_size_bytes,
        "videoPath": video_path,
        "videoSizeBytes": video_size_bytes,
        "durationMs": round((max(t) - min(t)) / 1_000_000),
    }
    if events_path is not None:
        result["eventsPath"] = events_path
    if annotations_path is not None:
        result["annotationsPath"] = annotations_path
    if sidecars:
        for sc in sidecars:
            if sc.get("kind") not in SIDECAR_KINDS:
                raise ValueError(
                    f"unknown sidecar kind {sc.get('kind')!r}; "
                    f"expected one of {sorted(SIDECAR_KINDS)}"
                )
            if "path" not in sc:
                raise ValueError(f"sidecar entry missing 'path': {sc!r}")
        result["sidecars"] = sidecars
    return result


def _discover_sidecars(episode_dir: Path) -> list[dict]:
    """Auto-discover sidecar files under the well-known subdirectories.

    Each file under ``sensors/`` / ``audio/`` / ``logs/`` / ``calib/`` is
    registered as a ``sidecars[]`` entry with the directory's default kind and
    format, a real on-disk size, and a ``frame`` tag derived from the file stem
    (e.g. ``sensors/imu.jsonl`` → ``kind=imu``, ``frame=imu``).
    """
    sidecars: list[dict] = []
    for dirname, (kind, fmt) in _SIDECAR_DIR_DEFAULTS.items():
        sub = episode_dir / dirname
        if not sub.is_dir():
            continue
        for path in sorted(sub.iterdir()):
            if not path.is_file():
                continue
            entry: dict = {
                "kind": kind,
                "path": f"{dirname}/{path.name}",
                "format": fmt,
                "sizeBytes": path.stat().st_size,
            }
            stem = path.stem
            if stem and stem != dirname:
                entry["frame"] = stem
            sidecars.append(entry)
    return sidecars


def manifest_for_episode(episode_dir: str | Path) -> dict:
    """Read ``<episode_dir>/data.jsonl`` (and ``video.mp4`` / ``events.jsonl`` if present)
    and build the manifest, filling in real on-disk sizes."""
    episode_dir = Path(episode_dir)
    jsonl = episode_dir / "data.jsonl"
    frames = read_jsonl(jsonl)
    video = episode_dir / "video.mp4"
    if video.exists():
        video_path: str | None = video.name
        video_size = video.stat().st_size
    else:
        video_path, video_size = None, 0
    events = episode_dir / "events.jsonl"
    events_path: str | None = events.name if events.exists() else None
    annotations_dir = episode_dir / "annotations"
    annotations_path: str | None = (
        "annotations/spans.jsonl"
        if (annotations_dir / "spans.jsonl").exists()
        else None
    )
    return build_manifest(
        frames,
        jsonl_size_bytes=jsonl.stat().st_size,
        video_path=video_path,
        video_size_bytes=video_size,
        events_path=events_path,
        annotations_path=annotations_path,
        sidecars=_discover_sidecars(episode_dir),
    )


def write_manifest(episode_dir: str | Path, *, indent: int = 2) -> Path:
    """Compute and write ``<episode_dir>/manifest.json``; return its path."""
    episode_dir = Path(episode_dir)
    manifest = manifest_for_episode(episode_dir)
    out = episode_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=indent) + "\n", encoding="utf-8", newline="\n")
    return out


def validate_manifest(episode_dir: str | Path) -> dict:
    """Validate ``manifest.json`` against the manifest schema *and* check
    consistency with the sibling ``data.jsonl``.

    Returns a dict like ``{"ok": True}`` or ``{"ok": False, "errors": [...]}``.
    """
    episode_dir = Path(episode_dir)
    errors: list[str] = []

    manifest_path = episode_dir / "manifest.json"
    jsonl_path = episode_dir / "data.jsonl"

    if not manifest_path.exists():
        errors.append(f"manifest not found: {manifest_path}")
        return {"ok": False, "errors": errors}
    if not jsonl_path.exists():
        errors.append(f"data.jsonl not found: {jsonl_path}")
        return {"ok": False, "errors": errors}

    # Load both files
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        errors.append(f"cannot parse manifest.json: {e}")
        return {"ok": False, "errors": errors}

    try:
        frames = read_jsonl(jsonl_path)
    except (OSError, ValueError) as e:
        errors.append(f"cannot read data.jsonl: {e}")
        return {"ok": False, "errors": errors}

    # --- Schema validation (optional jsonschema if available) ---
    try:
        import jsonschema as _jsonschema  # noqa: N813
    except ImportError:
        _jsonschema = None  # type: ignore[assignment]

    if _jsonschema is not None:
        try:
            _jsonschema.validate(manifest, _MANIFEST_SCHEMA)
        except _jsonschema.ValidationError as e:
            errors.append(f"manifest violates schema: {e.message}")

    # --- Consistency checks ---
    actual_frame_count = len(frames)

    if manifest.get("frameCount") != actual_frame_count:
        errors.append(
            f"frameCount mismatch: manifest={manifest.get('frameCount')} "
            f"actual={actual_frame_count}"
        )

    if frames:
        actual_episode_index = frames[0].get("episode_index")
        if manifest.get("episodeIndex") != actual_episode_index:
            errors.append(
                f"episodeIndex mismatch: manifest={manifest.get('episodeIndex')} "
                f"actual={actual_episode_index}"
            )

    try:
        actual_bytes = jsonl_path.stat().st_size
        if manifest.get("jsonlSizeBytes") != actual_bytes:
            errors.append(
                f"jsonlSizeBytes mismatch: manifest={manifest.get('jsonlSizeBytes')} "
                f"actual={actual_bytes}"
            )
    except OSError as e:
        errors.append(f"cannot stat data.jsonl: {e}")

    # --- video consistency when present ---
    if manifest.get("videoPath") is not None:
        video_path = episode_dir / manifest["videoPath"]
        if video_path.exists():
            try:
                actual_video_bytes = video_path.stat().st_size
                if manifest.get("videoSizeBytes") != actual_video_bytes:
                    errors.append(
                        f"videoSizeBytes mismatch: manifest={manifest.get('videoSizeBytes')} "
                        f"actual={actual_video_bytes}"
                    )
            except OSError as e:
                errors.append(f"cannot stat video file: {e}")
        else:
            errors.append(f"videoPath '{manifest['videoPath']}' does not exist on disk")

    # --- eventsPath consistency when present ---
    if manifest.get("eventsPath") is not None:
        events_path = episode_dir / manifest["eventsPath"]
        if not events_path.exists():
            errors.append(
                f"eventsPath '{manifest['eventsPath']}' does not exist on disk"
            )

    # --- annotationsPath consistency when present ---
    if manifest.get("annotationsPath") is not None:
        annotations_path = episode_dir / manifest["annotationsPath"]
        if not annotations_path.exists():
            errors.append(
                f"annotationsPath '{manifest['annotationsPath']}' does not exist on disk"
            )

    # --- sidecars consistency when present ---
    if "sidecars" in manifest:
        sidecars = manifest["sidecars"]
        if not isinstance(sidecars, list):
            errors.append("sidecars must be an array")
        else:
            for i, sc in enumerate(sidecars):
                sc_path = sc.get("path") if isinstance(sc, dict) else None
                if sc_path is None:
                    errors.append(f"sidecars[{i}] missing 'path'")
                    continue
                full = episode_dir / sc_path
                if not full.exists():
                    errors.append(
                        f"sidecars[{i}].path '{sc_path}' does not exist on disk"
                    )
                # Check sizeBytes consistency when present
                if isinstance(sc, dict) and "sizeBytes" in sc:
                    try:
                        actual = full.stat().st_size
                        if sc["sizeBytes"] != actual:
                            errors.append(
                                f"sidecars[{i}].sizeBytes mismatch: "
                                f"manifest={sc['sizeBytes']} actual={actual}"
                            )
                    except OSError as e:
                        errors.append(f"cannot stat sidecars[{i}].path '{sc_path}': {e}")

    return {"ok": len(errors) == 0, "errors": errors}
