"""Shared helpers for the ecosystem importers.

Importers turn third-party teleop logs into a canonical episode directory:

    <out>/
      data.jsonl        # canonical robot_v2 frames (passes conformance)
      manifest.json     # standard episode manifest (POST /api/episodes ready)
      import_meta.json   # provenance + quality downgrade + field-fill strategy
      frames/*.jpg      # extracted JPG camera frames (when present)

Provenance is kept in the ``import_meta.json`` *sidecar* rather than on the
frames, so the frames stay strictly conformant with the read-only canonical
contract while the ``source=imported_*`` marker and quality downgrade are still
explicit and machine-readable for the quality-score card.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..io import write_jsonl
from ..manifest import write_manifest
from ..schema import get_schema_version

# Imported data never carries the trust of a native capture surface, so it is
# always tagged a downgraded quality tier (the score card can weight it down).
QUALITY_TIER_IMPORTED = "imported"


def iso_from_ns(ns: int) -> str:
    """ISO-8601 UTC millisecond timestamp from wall-clock nanoseconds."""
    dt = datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def build_import_meta(
    *,
    importer: str,
    source: str,
    source_format: str,
    embodiment_id: str | None,
    frame_count: int,
    fill_strategy: dict[str, str],
    filled_fields: list[str],
    dropped_fields: list[str],
    reasons: list[str],
) -> dict:
    """Assemble the ``import_meta.json`` provenance sidecar payload."""
    return {
        "importer": importer,
        "source": source,
        "sourceFormat": source_format,
        "canonicalSchemaVersion": get_schema_version(),
        "embodimentId": embodiment_id,
        "frameCount": frame_count,
        "quality": {
            "tier": QUALITY_TIER_IMPORTED,
            "downgraded": True,
            "reasons": ["provenance=imported (not a native capture surface)", *reasons],
        },
        "fillStrategy": fill_strategy,
        "filledFields": filled_fields,
        "droppedFields": dropped_fields,
    }


def write_episode(
    out_dir: str | Path,
    frames: list[dict],
    import_meta: dict,
    assets: dict[str, bytes] | None = None,
) -> dict:
    """Write a canonical episode directory (data.jsonl + assets + manifest +
    import_meta.json). Returns a small summary dict.

    ``assets`` maps episode-relative paths (e.g. ``"frames/000000_ego.jpg"``) to
    raw bytes; parent directories are created as needed.
    """
    import json

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    for rel, blob in (assets or {}).items():
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)

    write_jsonl(out / "data.jsonl", frames)
    (out / "import_meta.json").write_text(
        json.dumps(import_meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = write_manifest(out)

    return {
        "episodeDir": str(out),
        "frameCount": len(frames),
        "manifest": str(manifest_path),
        "assets": len(assets or {}),
    }
