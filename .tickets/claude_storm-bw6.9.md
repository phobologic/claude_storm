---
id: claude_storm-bw6.9
status: closed
deps: []
links: []
created: 2026-02-14T19:51:23.399654-08:00
type: task
priority: 2
parent: claude_storm-bw6
---
# Fragile triple-listing of watermark fields in config.py

**File**: `/Users/mike/git/claude_storm/claude_storm/config.py`
**Line(s)**: 368-384

**Description**: `update_watermark` uses a read-modify-write pattern through `get_watermark()` that is fragile. It calls `get_watermark()` to get a dict with defaults merged in, mutates that dict, then builds a *new* dict for assignment -- selectively copying only some keys from the mutated dict. This means the watermark fields are listed in three places: the defaults dict in `get_watermark`, the mutation block in `update_watermark`, and the assignment dict in `update_watermark`. If a new tracking field is added, it must be updated in all three places or it will silently reset to zero on every turn.

**Suggested Fix**: Build the watermark dict once by starting from `get_watermark()`, updating the fields that change, and assigning the whole dict back:

```python
def update_watermark(self, agent: str, memory_count: int, ...) -> None:
    wm = self.get_watermark(agent)
    # Update cumulative fields
    if usage:
        wm["total_input_tokens"] += usage.get("input_tokens", 0)
        wm["total_output_tokens"] += usage.get("output_tokens", 0)
    if cost_usd is not None:
        wm["total_cost_usd"] += cost_usd
    if compacted:
        wm["compaction_count"] += 1
    # Update per-turn snapshot fields
    wm["memory_count"] = memory_count
    wm["agreement_count"] = len(self.accepted_agreements)
    wm["seen_proposal_ids"] = [p["id"] for p in self.pending_proposals]
    wm["last_turn"] = self.current_turn
    self.agent_watermarks[agent] = wm
```

This eliminates the third listing of field names entirely.



