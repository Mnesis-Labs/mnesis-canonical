"""``mnesis-import`` CLI — turn third-party teleop logs into canonical episodes.

    mnesis-import xrobotoolkit teleop_log_*.pkl --out out/ep0
    mnesis-import xrobotoolkit log.mcap --format airbot-mcap --out out/ep0

Exit codes: 0 = ok, 1 = conversion error, 2 = I/O error.
"""
from __future__ import annotations

import argparse
import json
import sys

from .airbot_mcap import import_mcap
from .xrobotoolkit import import_pickle


def _cmd_xrobotoolkit(args: argparse.Namespace) -> int:
    try:
        if args.format == "airbot-mcap":
            summary = import_mcap(args.log, args.out, embodiment_id=args.embodiment)
        else:
            summary = import_pickle(args.log, args.out)
    except FileNotFoundError:
        print(f"error: file not found: {args.log}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error: I/O failure on {args.log}: {e}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as e:
        print(f"error: could not import {args.log}: {e}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mnesis-import",
        description="Import third-party teleop logs into canonical episodes.",
    )
    sub = parser.add_subparsers(dest="command")

    x = sub.add_parser(
        "xrobotoolkit",
        help="Import an XRoboToolkit pickle (or airbot .mcap via --format).",
    )
    x.add_argument("log", help="Path to the teleop log (.pkl, or .mcap with --format)")
    x.add_argument("--out", required=True, help="Output episode directory")
    x.add_argument(
        "--format",
        choices=("pickle", "airbot-mcap"),
        default="pickle",
        help="Input format: pickle (XRoboToolkit, default) or airbot-mcap.",
    )
    x.add_argument(
        "--embodiment",
        default=None,
        help="embodiment_id to stamp on frames (airbot-mcap path; pickle uses meta).",
    )
    x.set_defaults(func=_cmd_xrobotoolkit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
