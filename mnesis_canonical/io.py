"""JSONL read/write helpers for Canonical Schema episode sidecars."""
from __future__ import annotations

import json
from pathlib import Path


def read_jsonl(path: str | Path) -> list[dict]:
    """Read an episode JSONL sidecar into a list of frame dicts (skips blank lines)."""
    frames: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def write_jsonl(path: str | Path, frames: list[dict]) -> None:
    """Write frame dicts as a JSONL sidecar (one compact JSON object per line)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for frame in frames:
            f.write(json.dumps(frame, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")
