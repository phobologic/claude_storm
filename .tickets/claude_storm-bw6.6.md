---
id: claude_storm-bw6.6
status: closed
deps: []
links: []
created: 2026-02-14T19:51:18.719697-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Duplicated cost/stats formatting across PlainDisplay and TextualDisplay

**File**: /Users/mike/git/claude_storm/claude_storm/display.py
**Line(s)**: 190-205 (PlainDisplay) and 431-446 (TextualDisplay)
**Description**: The cumulative cost/token summary logic in `show_completion` is duplicated verbatim between `PlainDisplay` and `TextualDisplay`. The same watermark-aggregation loop and formatting logic appears in both classes. Similarly, `show_compaction` and `show_turn_stats` have near-identical implementations differing only in the final render call (`self.console.print(...)` vs `self._show(Text(...))`).

This is a maintainability concern -- any change to the formatting or aggregation logic must be made in two places.

**Suggested Fix**: Extract the watermark aggregation into a standalone helper function (e.g., `_format_cumulative_stats(config) -> str | None`) and the turn stats formatting into `_format_turn_stats(cost_usd, duration_ms, usage) -> str | None`. Each display class calls the helper and renders the result string through its own output mechanism.

```python
def _format_cumulative_stats(config: SessionConfig) -> str | None:
    """Format cumulative cost/token summary from watermarks."""
    total_cost = 0.0
    total_in = 0
    total_out = 0
    for agent_key in ("a", "b"):
        wm = config.get_watermark(agent_key)
        total_cost += wm.get("total_cost_usd", 0.0)
        total_in += wm.get("total_input_tokens", 0)
        total_out += wm.get("total_output_tokens", 0)
    if total_cost <= 0 and total_in <= 0:
        return None
    parts = []
    if total_cost > 0:
        parts.append(f"${total_cost:.4f}")
    if total_in > 0 or total_out > 0:
        parts.append(f"In: {total_in:,} Out: {total_out:,}")
    return f"Total: {' · '.join(parts)}"
```



