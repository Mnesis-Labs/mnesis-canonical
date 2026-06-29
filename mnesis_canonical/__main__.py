"""Command-line interface for the Mnesis Canonical Schema.

    python -m mnesis_canonical validate <path/to/data.jsonl>

Prints a ``total=.. valid=.. errors=..`` summary and exits non-zero when the
episode is not conformant, so it can gate CI and be reused by Mnesis Ambrosia
ingest. Exit codes: 0 = all frames valid, 1 = validation errors, 2 = I/O error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .io import read_jsonl, write_jsonl
from .isaac import to_isaac
from .lerobot import to_lerobot
from .manifest import manifest_for_episode, write_manifest
from .synth import demo_episodes
from .validate import validate_frames


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        frames = read_jsonl(args.path)
    except FileNotFoundError:
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: could not read {args.path}: {e}", file=sys.stderr)
        return 2

    report = validate_frames(frames, strict_vocab=args.strict_vocab)
    print(f"total={report.total} valid={report.valid} errors={len(report.errors)}")

    if report.errors:
        limit = args.max_errors or None
        for line_no, msg in report.errors[:limit]:
            print(f"  line {line_no}: {msg}", file=sys.stderr)
        if args.max_errors and len(report.errors) > args.max_errors:
            print(f"  ... and {len(report.errors) - args.max_errors} more", file=sys.stderr)
    elif report.total == 0:
        print("error: episode is empty (no frames)", file=sys.stderr)

    return 0 if report.ok else 1


def _cmd_manifest(args: argparse.Namespace) -> int:
    try:
        if args.no_write:
            manifest = manifest_for_episode(args.episode_dir)
        else:
            manifest = json.loads(write_manifest(args.episode_dir).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: no data.jsonl under: {args.episode_dir}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: could not build manifest for {args.episode_dir}: {e}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2))
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    out = Path(args.out)
    episodes = demo_episodes()
    rows: list[tuple[str, int, int, bool]] = []
    all_ok = True

    for name, frames in episodes.items():
        ep_dir = out / "episodes" / name
        write_jsonl(ep_dir / "data.jsonl", frames)
        write_manifest(ep_dir)

        report = validate_frames(frames, strict_vocab=True)
        all_ok = all_ok and report.ok

        lerobot_dir = out / "lerobot"
        lerobot_dir.mkdir(parents=True, exist_ok=True)
        (lerobot_dir / f"{name}.columns.json").write_text(
            json.dumps(to_lerobot(frames)), encoding="utf-8", newline="\n"
        )
        write_jsonl(out / "isaac" / f"{name}.jsonl", to_isaac(frames))

        f0 = frames[0]
        dur_ms = round((frames[-1]["t_ns"] - f0["t_ns"]) / 1_000_000)
        surface = f"{f0['source.device']}·{f0['source.modality']}"
        rows.append((surface, len(frames), dur_ms, report.ok))

    print("Mnesis Canonical — demo: one format, three capture surfaces\n")
    print(f"  {'surface':<20}{'frames':>8}{'durationMs':>12}  valid")
    for surface, n, dur, ok in rows:
        print(f"  {surface:<20}{n:>8}{dur:>12}  {'OK' if ok else 'FAIL'}")
    print(f"\n  validated -> LeRobot ({out / 'lerobot'}) + Isaac ({out / 'isaac'})")

    try:
        from .viz import plot_trajectories

        png = plot_trajectories(episodes, out / "trajectories.png")
        print(f"  trajectory plot: {png}")
    except RuntimeError as e:
        print(f"  (trajectory plot skipped: {e})")

    return 0 if all_ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mnesis-canonical",
        description="Mnesis Canonical Schema — validation tools for episode sidecars.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate an episode JSONL sidecar.")
    v.add_argument("path", help="Path to the episode data.jsonl")
    v.add_argument(
        "--strict-vocab",
        action="store_true",
        help="Reject unknown source.device / source.modality values.",
    )
    v.add_argument(
        "--max-errors",
        type=int,
        default=20,
        help="Max error lines to print (0 = print all).",
    )
    v.set_defaults(func=_cmd_validate)

    m = sub.add_parser(
        "manifest",
        help="Build (and write) an episode's manifest.json from its data.jsonl.",
    )
    m.add_argument("episode_dir", help="Episode directory containing data.jsonl")
    m.add_argument(
        "--no-write",
        action="store_true",
        help="Print the manifest to stdout without writing manifest.json.",
    )
    m.set_defaults(func=_cmd_manifest)

    d = sub.add_parser(
        "demo",
        help="Generate the 3-surface demo: synth data -> validate -> LeRobot/Isaac -> plot.",
    )
    d.add_argument(
        "--out",
        default="demo_out",
        help="Output directory for the generated demo artifacts (default: ./demo_out).",
    )
    d.set_defaults(func=_cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
