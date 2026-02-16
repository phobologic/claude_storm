---
id: claude_storm-bw6.16
status: closed
deps: []
links: []
created: 2026-02-14T19:51:52.354668-08:00
type: task
priority: 2
parent: claude_storm-bw6
---
# Duplicated watermark aggregation logic in both display classes

**File**: /Users/mike/git/claude_storm/claude_storm/display.py
**Line(s)**: 190-205 and 431-445
**Description**: The watermark aggregation logic in `show_completion` is duplicated verbatim between `PlainDisplay` and `TextualDisplay`. Both implementations iterate over agents, call `config.get_watermark()` (which allocates a merged dict each time), sum up costs/tokens, build the same parts list, and format the same output string. This means every `show_completion` call allocates 2 extra dicts (from `get_watermark`) and runs the same loop twice if both displays are somehow invoked. More importantly, if a third display implementation is added, this logic would need to be copied again.

**Suggested Fix**: Extract the aggregation into a standalone helper function (or a method on `SessionConfig`) that returns the totals, so both display classes call the helper:

```python
def _aggregate_session_stats(config: SessionConfig) -> tuple[float, int, int]:
    """Sum cost and token totals across all agents."""
    total_cost = 0.0
    total_in = 0
    total_out = 0
    for agent_key in ("a", "b"):
        wm = config.get_watermark(agent_key)
        total_cost += wm.get("total_cost_usd", 0.0)
        total_in += wm.get("total_input_tokens", 0)
        total_out += wm.get("total_output_tokens", 0)
    return total_cost, total_in, total_out
```

This also reduces the chance of the two implementations drifting apart.



