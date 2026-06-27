# HANDOFF · Sprint S1 (mnesis-canonical)

> From: Developer (Claude Code, autonomous run on branch `claude/objective-haslett-0e818f`)
> To: Tech Lead (review) · QA (用户 + 真机)
> Status: **Sprint S1 complete — C1–C6 all done, gate green.** Not merged to `main`
> (Tech Lead decides). Base commit: `33dedba`.

## Gate (real output)
```
$ ruff check .
All checks passed!

$ pytest -q
........................                                                 [100%]
24 passed in 0.10s
```
Baseline was 8 tests → now **24** (+16). Every example episode (phone / quest /
robot) validates, including under `--strict-vocab`.

## What shipped (one commit per task)
| Task | Commit | Summary |
|---|---|---|
| C1 | `74e9816` | `canonical_frame.schema.json` (Draft 2020-12) + optional `jsonschema` backend (`validate_frame_jsonschema`, `load_json_schema`); shipped as package data |
| C2 | `4435860` | CLI `python -m mnesis_canonical validate <data.jsonl>` → `total/valid/errors`, exit 0/1/2; `mnesis-canonical` console script |
| C3 | `68b2d79` | LeRobot adapter `to_lerobot` / `from_lerobot` (columnar, exact round-trip) |
| C4 | `2e9706f` | `examples/episode_quest` (quest/teleop) + `examples/episode_robot` (robot/robot_replay); vocab/example drift guard |
| C5 | `da43b35` | SPEC §Compatibility: Isaac Lab / GR00T field-mapping table + open items |
| C6 | `6bdb63b` | Packaging verified (wheel+sdist ship schema; console script installs); README standard/compat commitment |

## Files changed (vs `33dedba`)
- **New:** `mnesis_canonical/canonical_frame.schema.json`, `mnesis_canonical/__main__.py`,
  `mnesis_canonical/lerobot.py`, `examples/episode_quest/data.jsonl`,
  `examples/episode_robot/data.jsonl`, `tests/test_cli.py`,
  `tests/test_examples.py`, `tests/test_lerobot.py`.
- **Edited:** `mnesis_canonical/__init__.py` (exports), `mnesis_canonical/validate.py`
  (jsonschema backend), `pyproject.toml` (jsonschema extra, console script,
  package-data), `SPEC.md` (§Compatibility), `README.md`, `tests/test_validate.py`.

## Contract / field changes
**None.** No field added, removed, or re-typed — the wire format is byte-identical
to `33dedba`. C1 only *re-expresses* the existing contract as JSON Schema (a drift
test asserts `schema["required"] == REQUIRED_KEYS`). `DEVICES`/`MODALITIES` were
already frozen in `schema.py` and already match `SPEC.md` §Fields; C4 only adds a
guard test. So no downstream field migration is required by this sprint.

## ⬇️ Downstream sync items (for Tech Lead to route)
These are **adapter / doc** alignment items, not wire-format changes:
1. **Ambrosia ingest** can now reuse the CLI exit-code contract (0 valid / 1 errors
   / 2 I/O) and the same JSON Schema file for a language-agnostic ingest gate.
   → Confirm Ambrosia adopts `canonical_frame.schema.json` rather than a fork.
2. **EgoWear / ProdigyHelper / TeleOP-Alohamini** producers: no field change needed.
   Optional: adopt the `mnesis-canonical validate` CLI in their CI to gate emitted
   episodes against the standard.
3. **LeRobot export**: `to_lerobot` carries the 7 native features 1:1 and lets the
   extra canonical columns ride along — confirm the Ambrosia/training side tolerates
   the extra columns (`head_pose_SE3`, `t_hw_ns`, `source.*`, `tracking_state`).

## ⚠️ Open questions (need Tech Lead / Parthenon `03 §3.2`, do NOT freeze unilaterally)
Recorded in `SPEC.md` §Compatibility → "Open items":
1. **Quaternion order** for Isaac/GR00T export — Canonical `{x,y,z,w}` scalar-last
   vs Isaac/USD `{w,x,y,z}` scalar-first. Adapter-only, or does wire change?
2. **World frame / up-axis** — ARCore Y-up vs Isaac Z-up (both right-handed). Pin
   the canonical world frame + export transform.
3. **Action rotation representation** — axis-angle (rad) vs GR00T/Isaac action space.
4. **Embodiment tagging** — `source.device`/`source.modality` → GR00T embodiment tag.

## Leftover / not in scope this sprint
- `manifest.json` per the SPEC episode layout is documented but not generated for the
  new examples (only `data.jsonl` shipped). A `manifest`/`video.mp4` writer could be a
  follow-up if Ambrosia needs it for ingest demos.
- JSON Schema enforces structure/types only; cross-frame `frame_index` monotonicity
  and strict vocab remain in the pure-Python validator (by design).
