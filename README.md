# mnesis-canonical

> **Mnesis Canonical Schema** — the open standard for embodied spatial-action data.
> The "USB-C of robot-trainable data": one format every capture surface emits and
> the Mnesis Ambrosia platform ingests. **Apache-2.0** — free to adopt, by design.

This is Mnesis Labs' **open layer** (Open-Core strategy, Parthenon `01 §2`): the
schema + reference validator + device-abstraction SDK are open so they become the
de-facto standard; the proprietary core (high-fidelity data, 4DGS physics, eval)
lives in Mnesis Ambrosia.

## What's here
- [`SPEC.md`](SPEC.md) — the authoritative specification (field-by-field).
- `mnesis_canonical/` — reference Python implementation: typed `CanonicalFrame`,
  `validate_frame` / `validate_frames`, `read_jsonl` / `write_jsonl`.
- `examples/` — tiny valid episodes across capture surfaces: `episode_0`
  (phone / `ego_human`), `episode_quest` (Quest / `teleop`), `episode_robot`
  (robot / `robot_replay`).

## Install / use
```bash
pip install -e ".[dev]"
```
```python
from mnesis_canonical import read_jsonl, validate_frames
report = validate_frames(read_jsonl("episodes/ep_0/data.jsonl"))
print(report.ok, report.total, report.errors)
```

## Test / lint (what CI runs)
```bash
ruff check . && pytest -q
```

## Who depends on this
`EgoWear` (phone) · `ProdigyHelper` (Quest) · `TeleOP-Alohamini` (robot) all emit
this schema; `mnesis-ambrosia` validates ingest against it. Change the schema **here
first** (SPEC + reference impl), then sync consumers — never fork the fields per repo.

## Status
v0.1 scaffold (seeded from EgoWear `schema/CanonicalFrame`). Roadmap → `docs/SPRINT_S1.md`.
Cross-repo plan → Parthenon `research/platform-and-repo-roadmap.md`.
