"""Contract integrity checker — verifies ``contracts.lock`` SHA-256 consistency.

Usage::

    python -m mnesis_canonical.contracts_check              # verify
    python -m mnesis_canonical.contracts_check --generate    # regenerate lock
    python -m mnesis_canonical.contracts_check --list        # list files + hashes

Exit codes: 0 = ok, 1 = integrity error, 2 = I/O or lock format error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "contracts"
LOCK_FILE = CONTRACTS_DIR / "contracts.lock"
LOCK_VERSION = 1

# Machine-readable contract schemas that ship inside the package (so the Python
# validator can load them from an installed wheel) are pinned by the same lock.
# Their lock keys are repo-relative ("mnesis_canonical/contracts/<name>") to keep
# them distinct from the top-level contracts/ entries, which are bare file names.
PACKAGE_CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"
PACKAGE_CONTRACTS_PREFIX = "mnesis_canonical/contracts/"
PACKAGE_CONTRACTS_GLOB = "*.schema.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tracked_files() -> dict[str, Path]:
    """Return {lock_key: path} for every file the lock should cover.

    Top-level ``contracts/`` files use their bare name (the lock file itself,
    README.md and dotfiles are excluded); package-shipped schemas use the
    repo-relative ``mnesis_canonical/contracts/<name>`` key.
    """
    files: dict[str, Path] = {}
    for child in sorted(CONTRACTS_DIR.iterdir()):
        if not child.is_file():
            continue
        name = child.name
        if name == "contracts.lock" or name == "README.md":
            continue
        if name.startswith("."):
            continue
        files[name] = child
    if PACKAGE_CONTRACTS_DIR.is_dir():
        for child in sorted(PACKAGE_CONTRACTS_DIR.glob(PACKAGE_CONTRACTS_GLOB)):
            if child.is_file():
                files[PACKAGE_CONTRACTS_PREFIX + child.name] = child
    return files


def _resolve(name: str) -> Path:
    """Map a lock key back to its file on disk."""
    if "/" in name:
        return REPO_ROOT / name
    return CONTRACTS_DIR / name


def _lock_paths() -> dict[str, str]:
    """Return {lock_key: sha256} for all files tracked by the lock."""
    return {name: _sha256(path) for name, path in _tracked_files().items()}


def _load_lock() -> dict | None:
    try:
        data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("version") != LOCK_VERSION:
        return None
    return data


def _dump_lock(files: dict[str, str]) -> None:
    lock = {"version": LOCK_VERSION, "files": files}
    LOCK_FILE.write_text(
        json.dumps(lock, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def cmd_verify() -> int:
    """Verify that every entry in contracts.lock matches the file on disk."""
    lock = _load_lock()
    if lock is None:
        print("error: contracts.lock not found or invalid format", file=sys.stderr)
        return 2

    expected = lock.get("files", {})
    if not expected:
        print("error: contracts.lock is empty", file=sys.stderr)
        return 2

    ok = True
    for name, stored_hash in sorted(expected.items()):
        path = _resolve(name)
        if not path.exists():
            print(f"  {name}  ... MISSING (expected)", file=sys.stderr)
            ok = False
            continue
        actual = _sha256(path)
        if actual == stored_hash:
            print(f"  {name}  ... OK")
        else:
            print(f"  {name}  ... MISMATCH (expected {stored_hash}, got {actual})", file=sys.stderr)
            ok = False

    # Check for untracked files
    tracked = set(expected.keys())
    for name in _tracked_files():
        if name not in tracked:
            print(f"  {name}  ... UNTRACKED", file=sys.stderr)
            ok = False

    if ok:
        print("All contracts pass integrity check.")
        return 0
    return 1


def cmd_generate() -> int:
    """Regenerate contracts.lock from files on disk."""
    files = _lock_paths()
    _dump_lock(files)
    print(f"contracts.lock regenerated ({len(files)} files)")
    return 0


def cmd_list() -> int:
    """List all tracked files and their SHA-256 hashes."""
    files = _lock_paths()
    print(f"{'File':<60} SHA-256")
    print("-" * 60 + "  " + "-" * 64)
    for name, digest in sorted(files.items()):
        print(f"{name:<60} {digest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mnesis_canonical.contracts_check",
        description="Verify contracts/ integrity against contracts.lock.",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Regenerate contracts.lock from current files.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List tracked files and their SHA-256 hashes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.generate:
        return cmd_generate()
    if args.list:
        return cmd_list()
    return cmd_verify()


if __name__ == "__main__":
    sys.exit(main())