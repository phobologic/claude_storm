---
id: claude_storm-bw6.12
status: closed
deps: []
links: []
created: 2026-02-14T19:51:31.313856-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Debug writer assumes usage field is always a dict

**File**: /Users/mike/git/claude_storm/claude_storm/debug.py
**Line(s)**: 76-82
**Description**: The debug output checks for `total_cost_usd` as a key inside `raw_response`, but the cost field comes from the CLI result event at the top level. The check `if "total_cost_usd" in raw_response` works correctly for the raw result event. However, the debug writer accesses `raw_response["usage"]` without a guard on the value type -- if `raw_response["usage"]` were not a dict (e.g., `None`), the subsequent `.get()` calls would fail.

This is low-risk since the `if "usage" in raw_response` guard only passes when the key exists, and the CLI always provides a dict for this field. But it would be slightly more defensive to add a type check.

**Suggested Fix**: No action strictly required, but consider:
```python
usage = raw_response.get("usage")
if isinstance(usage, dict):
    ...
```



