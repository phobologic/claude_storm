---
id: claude_storm-bw6.5
status: closed
deps: []
links: []
created: 2026-02-14T19:51:17.393265-08:00
type: task
priority: 2
parent: claude_storm-bw6
---
# Duplicated cost/token aggregation in PlainDisplay and TextualDisplay show_completion

**File**: `/Users/mike/git/claude_storm/claude_storm/display.py`
**Line(s)**: 190-205 (PlainDisplay) and 431-445 (TextualDisplay)

**Description**: The cost/token aggregation logic in `show_completion` is completely duplicated between `PlainDisplay` and `TextualDisplay`. Both implementations contain identical logic: initialize counters, loop over agents, sum watermark values, build parts list, format output. The only difference is the final render call (`self.console.print` vs `self._show(Text(...))`). This is a maintenance risk -- any change to the summary format or aggregation logic must be made in two places.

**Suggested Fix**: Extract the aggregation into a standalone helper function (not a method on either class) that returns the formatted string, then call it from both implementations:

```python
def _format_session_totals(config: SessionConfig) -> str | None:
    """Aggregate cost/token totals across agents and return a formatted string.

    Returns None if there are no stats to display.
    """
    total_cost = 0.0
    total_in = 0
    total_out = 0
    for agent_key in ("a", "b"):
        wm = config.get_watermark(agent_key)
        total_cost += wm.get("total_cost_usd", 0.0)
        total_in += wm.get("total_input_tokens", 0)
        total_out += wm.get("total_output_tokens", 0)
    if not (total_cost > 0 or total_in > 0):
        return None
    parts = []
    if total_cost > 0:
        parts.append(f"${total_cost:.4f}")
    if total_in > 0 or total_out > 0:
        parts.append(f"In: {total_in:,} Out: {total_out:,}")
    return f"Total: {' · '.join(parts)}"
```

Then in each display class:
```python
totals = _format_session_totals(config)
if totals:
    self.console.print(f"[dim]{totals}[/dim]")  # PlainDisplay
    # or
    self._show(Text(totals, style="dim"))  # TextualDisplay
```



