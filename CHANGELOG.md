# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [SemVer-of-the-schema](README.md#compatibility-commitment)
— the **package version** (this changelog) and the **schema version** (SPEC.md §Versioning)
are decoupled:

> **Package 0.3.0** introduces the **profile mechanism** (v0.2 schema) for additive
> schema evolution. `ego_v1` = v0.1 backward-compatible default; `robot_v2` adds
> variable-length vectors, open camera keys, and optional `eef_pose`. All existing
> data and examples validate without modification.

## [Unreleased]

### Added

- **D-18 — C8 gripper channel** (v0.2 schema, additive-only). Optional
  first-class gripper opening as a continuous scalar in `[0, 1]` (0=closed,
  1=open): `observation.gripper` (single/main, any profile) and
  `observation.gripper.{left,right}` (bimanual robot_v2). Semantics align 1:1
  with the C3 xr_bridge wire field `arms[].gripper`. Frames without a gripper
  key validate unchanged.
  - `GRIPPER_KEYS`, `GRIPPER_MIN`, `GRIPPER_MAX` constants; `CanonicalFrame`
    extended with `gripper` / `gripper_left` / `gripper_right`.
  - JSON Schema `observation.gripper[.left|.right]` (`number`, `[0,1]`);
    validator range/finite check.
  - `examples/episode_gripper` — robot_v2 teleop example carrying a gripper.
  - `tests/test_gripper.py` conformance cases.
- **D-18 — C3 xr_bridge v1.6** (contract, additive). Camera-control negotiation
  (`C3_CameraControl` headset→robot `{camera_id,width,height,fps,bitrate,codec}`,
  OPEN_CAMERA-style over our ws envelope + `C3_CameraStatus` reply) and video
  transport capability declaration (`C3_Info.video_capabilities`,
  `transports: webrtc|mjpeg`, reserved for the DQ-1 WebRTC line). `≤v1.5`
  clients ignore the new messages/field — wire format unchanged. Specified in
  `contracts/XR_ROBOT_CONTRACT.md` + `contracts/xr_bridge_SPEC.md`; consumer
  `contracts.lock` upgrade path documented in `CONTRACTS.md`.
  - `contracts.lock` regenerated; `tests/test_contracts.py` pins the spec.

## [0.3.0] — 2026-07-21

### Added

- **D-9a — Profile mechanism** (v0.2 schema, additive-only). Frame top-level
  optional `profile` (default `ego_v1`) and `embodiment_id` fields. v0.1 frames
  without these fields pass all validation unchanged (regression covered).
  - `PROFILES`, `DEFAULT_PROFILE`, `ROBOT_V2_VARIABLE_VECTORS` constants.
  - `required_keys_for_profile()` helper function.
- **D-9a — robot_v2 profile**: `observation.state` and `action` are
  variable-length float[N] (no fixed-size check); `observation.images.<cam>`
  open key set (at least one required, no single camera mandatory); optional
  `observation.eef_pose.{left,right}` (each float[7]).
- **D-9a — `examples/episode_dual_airbot`** — robot_v2 profile example with
  14-DoF dual-arm state/action, wrist_left/wrist_right cameras, and optional
  eef_pose left/right. Validates via `validate_frames` (strict).
- **SPEC v0.2** — rewritten with profile table, robot_v2 field documentation,
  backward-compatibility guarantee.
- **JSON Schema v0.2** — `$id` bumped to `v0.2.json`; conditional validation
  via `if/then/else` for profile-specific requirements.

### Changed

- `CanonicalFrame` dataclass extended with `profile`, `embodiment_id`,
  `observation_images` (extra camera keys), `eef_pose_left`, `eef_pose_right`.
- `REQUIRED_KEYS` split into `_REQUIRED_KEYS_EGO_V1` and `_REQUIRED_KEYS_ROBOT_V2`;
  base `REQUIRED_KEYS` constant kept as ego_v1 for backward compat.

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

[0.3.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.3.0
[0.2.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.2.0
[0.1.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.1.0