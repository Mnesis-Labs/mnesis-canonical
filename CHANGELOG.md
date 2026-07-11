# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [SemVer-of-the-schema](README.md#compatibility-commitment)
— the **package version** (this changelog) and the **schema version** (SPEC.md §Versioning)
are decoupled:

> **Package 0.2.0** adds CLI, adapter, manifest, and type-distribution capabilities
> **without changing any wire fields.** The schema version remains `v0.1` (SPEC.md),
> so downstream consumers pinning `mnesis-canonical ~= 0.1` are unaffected.
> The version bump reflects the new *non-field* surface area, not a wire change.

## [0.2.0] — 2026-07-11

### Added

- **C1 — JSON Schema** (`canonical_frame.schema.json`, Draft 2020-12) with optional
  `jsonschema` backend (`validate_frame_jsonschema`). Bundled as a language-agnostic
  standard contract.
- **C2 — Validate CLI** (`python -m mnesis_canonical validate <path>`). Prints
  `total=.. valid=.. errors=..` summary, exit code 0 / 1 / 2 for CI gating.
- **C3 — LeRobot columnar adapter** (`to_lerobot` / `from_lerobot`). Pure transpose
  with no renaming or unit change; exact round-trip.
- **C4 — Multi-surface examples** (`examples/episode_quest`, `examples/episode_robot`)
  covering all three capture surfaces (phone, quest, robot). Strict-vocab validation
  guard against unknown `source.device` / `source.modality`.
- **C5 — Isaac / GR00T field mapping** documented in SPEC §Compatibility. Adapter
  does not change the wire format.
- **F1 — Episode manifest** (`build_manifest`, `manifest_for_episode`, `write_manifest`
  + `manifest` CLI subcommand). Produces `manifest.json` with `frameCount`,
  `episodeIndex`, `jsonlSizeBytes`, `videoPath`, `videoSizeBytes`, `durationMs`.
- **F2 — Isaac/GR00T export adapter** (`to_isaac` / `from_isaac`). Reorders
  quaternions scalar-last ↔ scalar-first; optional `world_transform` hook (defaults
  to identity). Exact round-trip. Adapter-only — wire format unchanged.
- **CONTRACTS.md** — cross-repo contract registry linking Mnesis-Iris / Eidolon /
  Daedalus / Ambrosia.
- **S2-1 — PEP 561 type distribution** (`py.typed` marker + `pyright` dev dependency).
  All public functions already annotated; zero pyright errors.

### Changed

- **Refactored to slim standard library** — removed demo/viz/synth machinery, keeping
  only the pure standard-library core: schema, validator, I/O, adapters, manifest,
  CLI. Zero runtime dependencies.
- LF-only `.gitattributes` for `*.jsonl`, `*.json`, `*.py`, `*.md`, `*.toml` to
  keep wire formats byte-stable across platforms.
- Version bumped from `0.1.0` → `0.2.0` (package); schema version stays `v0.1`.

### Fixed

- `write_jsonl` / `write_manifest` now write explicitly with `LF` newline
  (cross-platform determinism).

### Security

- No runtime dependencies in the core package (optional `jsonschema` in extras).

## [0.1.0] — 2026-06

### Added

- Initial scaffold: `CanonicalFrame` dataclass, `REQUIRED_KEYS`, `VECTOR_LENGTHS`,
  `validate_frame`, `validate_frames`, `read_jsonl`, `write_jsonl`.
- `examples/episode_0` (phone / ego_human).
- Dual-timestamp design, quaternion `{x,y,z,w}` scalar-last, relative-delta action.

[0.2.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.2.0
[0.1.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.1.0