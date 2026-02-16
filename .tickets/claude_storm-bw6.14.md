---
id: claude_storm-bw6.14
status: closed
deps: []
links: []
created: 2026-02-14T19:51:34.05722-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Unnecessary intermediate dict allocation in update_watermark

**File**: /Users/mike/git/claude_storm/claude_storm/config.py
**Line(s)**: 368-385
**Description**: `update_watermark` calls `get_watermark(agent)` which creates a fresh defaults dict via `{**defaults, **wm}` every time, only to immediately read cumulative values from it and then overwrite `self.agent_watermarks[agent]` with a new dict. This creates two throwaway dicts per turn. While not a hot path (called once per turn), it is an unnecessary allocation pattern that could be simplified.

**Suggested Fix**: Read directly from `self.agent_watermarks.get(agent, {})` and accumulate into local variables, avoiding the intermediate defaults-merge dict:

```python
def update_watermark(self, agent, memory_count, usage=None, cost_usd=None, compacted=False):
    existing = self.agent_watermarks.get(agent, {})
    total_in = existing.get("total_input_tokens", 0)
    total_out = existing.get("total_output_tokens", 0)
    total_cost = existing.get("total_cost_usd", 0.0)
    compaction_count = existing.get("compaction_count", 0)

    if usage:
        total_in += usage.get("input_tokens", 0)
        total_out += usage.get("output_tokens", 0)
    if cost_usd is not None:
        total_cost += cost_usd
    if compacted:
        compaction_count += 1

    self.agent_watermarks[agent] = {
        "memory_count": memory_count,
        "agreement_count": len(self.accepted_agreements),
        "seen_proposal_ids": [p["id"] for p in self.pending_proposals],
        "last_turn": self.current_turn,
        "total_cost_usd": total_cost,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "compaction_count": compaction_count,
    }
```

This eliminates the intermediate dict allocation from `get_watermark` and is also clearer about intent.



