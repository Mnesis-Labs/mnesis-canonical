# HANDOFF · Sprint S1 (mnesis-canonical)

> From: Developer (Claude Code, autonomous run on branch `claude/objective-haslett-0e818f`)
> To: Tech Lead (review) · QA (用户 + 真机)
> Status: **Sprint S1 complete (C1–C6) + F1/F2 follow-ups + D1–D4 demo, gate green.**
> Not merged to `main` (Tech Lead decides). Base commit: `33dedba`.

## Gate (real output)
```
$ ruff check .
All checks passed!

$ pytest -q
............................................                             [100%]
44 passed in 0.91s
```
Baseline was 8 tests → now **44**. Every example episode (phone / quest / robot)
validates, including under `--strict-vocab`, and ships a `manifest.json`. The
end-to-end `demo` command runs green and renders the trajectory plot.

## Investor demo — live command sheet
```bash
pip install -e ".[viz]"                 # one-time: core + matplotlib
python -m mnesis_canonical demo         # -> ./demo_out/ : data + LeRobot + Isaac + trajectories.png
```
Talking point: *one `head_pose_SE3` field, three real motions (handheld ego scan,
teleop reach, robot replay), all from identical canonical frames* — see
`docs/assets/demo_trajectories.png` (embedded at the top of the README).
Backup if a laptop has no matplotlib: `python -m mnesis_canonical demo` still
writes all data/LeRobot/Isaac artifacts and just skips the plot.

## What shipped (one commit per task)
| Task | Commit | Summary |
|---|---|---|
| C1 | `74e9816` | `canonical_frame.schema.json` (Draft 2020-12) + optional `jsonschema` backend (`validate_frame_jsonschema`, `load_json_schema`); shipped as package data |
| C2 | `4435860` | CLI `python -m mnesis_canonical validate <data.jsonl>` → `total/valid/errors`, exit 0/1/2; `mnesis-canonical` console script |
| C3 | `68b2d79` | LeRobot adapter `to_lerobot` / `from_lerobot` (columnar, exact round-trip) |
| C4 | `2e9706f` | `examples/episode_quest` (quest/teleop) + `examples/episode_robot` (robot/robot_replay); vocab/example drift guard |
| C5 | `da43b35` | SPEC §Compatibility: Isaac Lab / GR00T field-mapping table + open items |
| C6 | `6bdb63b` | Packaging verified (wheel+sdist ship schema; console script installs); README standard/compat commitment |
| F1 | `41d41d7`, `0ada08b` | Episode `manifest.json` writer (`build_manifest`/`manifest_for_episode`/`write_manifest`) + `manifest` CLI subcommand; manifests for all 3 examples; `.gitattributes` LF pin; library writes JSONL/manifest as LF |
| F2 | `253d4de` | Isaac/GR00T export adapter `mnesis_canonical.isaac` (`to_isaac`/`from_isaac`, quaternion scalar-last↔scalar-first, optional `world_transform` hook) — **adapter-only, wire format unchanged** |
| D1 | `c436bac` | Deterministic synthetic data generator `synth.py` (`synth_episode`/`demo_episodes`, pure stdlib) — believable phone/quest/robot trajectories, doubles as fixture |
| D2 | `218e63c` | End-to-end `demo` CLI: synth → validate → LeRobot + Isaac export → plot → summary table |
| D3 | `e25b0ab` | Trajectory plot `viz.py` + optional `[viz]` extra (matplotlib lazy; core stays zero-dep) |
| D4 | `d3b1fd7` | README 30-second demo + pitch narrative + committed `docs/assets/demo_trajectories.png` |

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
Recorded in `SPEC.md` §Compatibility → "Open items". F2 supplies a **reference
adapter** for 1–2 but changes **nothing** in the wire format; the calls below are
still yours:
1. **Quaternion order** — adapter `isaac.to_isaac` reorders on export; decide
   whether the canonical *wire* ever switches from `{x,y,z,w}` to `{w,x,y,z}`.
2. **World frame / up-axis** — ARCore Y-up vs Isaac Z-up. Adapter has an identity
   `world_transform` hook; supply the concrete transform + pin the canonical frame.
3. **Action rotation representation** — axis-angle (rad) vs GR00T/Isaac action
   space. Adapter passes `action` through verbatim — confirm before consuming it.
4. **Embodiment tagging** — `source.device`/`source.modality` → GR00T embodiment
   tag (not yet implemented in the adapter).

## Leftover / not in scope this sprint
- `manifest.json` is now generated for all 3 examples (F1). `video.mp4` is binary
  capture **data** — intentionally not produced or committed; the manifest only
  references it when present on disk.
- JSON Schema enforces structure/types only; cross-frame `frame_index` monotonicity
  and strict vocab remain in the pure-Python validator (by design).
- GR00T embodiment-tag mapping (open item 4) is not yet implemented in the adapter.

## Release dry-run (local, no external publish)
Built the wheel and installed it into a **fresh venv** with the `[viz]` extra;
the `mnesis-canonical demo` console script then ran end-to-end (incl. the plot),
confirming `pip install "mnesis-canonical[viz]"` works for a clean machine.
Publishing to (Test)PyPI is an outward action left for you to authorize.
