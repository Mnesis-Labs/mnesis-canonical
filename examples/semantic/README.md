# Golden samples — dual-endpoint semantic perception (C12 / PS0)

Four validated 8442 messages, one per shape a consumer has to handle. Use them as
fixtures on either end; they are checked on every CI run by
`tests/test_semantic.py`, so a sample that stops matching the contract fails the
build here rather than on a headset.

| File | Type | Shows |
|---|---|---|
| `semantic_label.json` | `semantic_label` (up) | **`source: "headset"`** recognition + a `source: "human"` adjudication, batched into one message |
| `scene_graph.json` | `scene_graph` (down) | all four states, including **`disputed`** (`robot: cup` vs `headset: bottle`) and **`stale`** |
| `colocalization.json` | `colocalization` | a healthy `T_map_headset` with quality metrics |
| `colocalization_stale.json` | `colocalization` | the **`colocalization_stale`** event — same message type, non-`ok` state |

Authoritative definition: [`SPEC.md` §Dual-endpoint semantic
perception](../../SPEC.md). JSON Schema for non-Python consumers:
`mnesis_canonical/semantic.schema.json`.

```python
from mnesis_canonical import validate_ps_message
import json
assert validate_ps_message(json.load(open("scene_graph.json"))) == []
```
