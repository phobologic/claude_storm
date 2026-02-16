---
id: claude_storm-csb.6
status: closed
deps: []
links: []
created: 2026-02-14T14:24:12.921573-08:00
type: task
priority: 3
parent: claude_storm-csb
---
# Original revision fields can be partially present

**File**: `/Users/mike/git/claude_storm/claude_storm/agreements.py`
**Line(s)**: 88-96 (create_proposal), 141-146 (accept_proposal)
**Description**: The `original_content`, `original_turn`, and `original_agent` fields are conditionally added to proposal/agreement dicts with separate `if is not None` checks. This means the three fields can be independently present or absent. For example, if someone passes `original_content="text"` but leaves `original_turn=None`, the dict will have `original_content` but not `original_turn`.

While the rendering code handles missing fields gracefully (defaults to `"?"` for turn, empty string for agent), this partial presence pattern is fragile. The three fields form a logical group -- they should either all be present or all be absent.

**Suggested Fix**: Treat the three original_* fields as an atomic group:

```python
if original_content is not None:
    proposal["original_content"] = original_content
    proposal["original_turn"] = original_turn  # may be None, that's fine
    proposal["original_agent"] = original_agent  # may be None, that's fine
```

This keeps the dict shape consistent: either all three keys exist or none do, making downstream code easier to reason about.



