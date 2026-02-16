---
id: claude_storm-bw6.11
status: closed
deps: []
links: []
created: 2026-02-14T19:51:27.113099-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Repeated isinstance guard for response.raw extraction in session.py

**File**: `/Users/mike/git/claude_storm/claude_storm/session.py`
**Line(s)**: 171-182

**Description**: The `cost_usd` and `duration_ms` extraction from `response.raw` uses repeated `isinstance(response.raw, dict)` guard checks. This pattern appears twice in close succession and again later in `run_session` (line ~487). The inline conditional expressions are harder to read than a simple helper or early extraction.

**Suggested Fix**: Extract once at the top of the block:

```python
raw = response.raw if isinstance(response.raw, dict) else {}
cost_usd = raw.get("total_cost_usd")
duration_ms = raw.get("duration_ms")
```

This is already partially done in `run_session` (line 487: `raw = response.raw`) but the guard is repeated on the next line. Being consistent would improve readability.



