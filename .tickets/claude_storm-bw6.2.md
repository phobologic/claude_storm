---
id: claude_storm-bw6.2
status: closed
deps: []
links: []
created: 2026-02-14T19:51:10.299841-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Missing docstrings on new DisplayProtocol methods

**File**: /Users/mike/git/claude_storm/claude_storm/display.py
**Line(s)**: 85-92
**Description**: The two new methods added to `DisplayProtocol` (`show_compaction` and `show_turn_stats`) lack docstrings, unlike every other method in the protocol. The protocol serves as the interface contract, so its docstrings are the primary documentation for implementors.

**Suggested Fix**: Add docstrings to both protocol method stubs, consistent with the existing pattern (e.g., `show_agent_stream_end` has a full docstring with Args).

```python
def show_compaction(self, agent: str, summary: str) -> None:
    """Display a warning that agent context was compacted.

    Args:
        agent: Which agent ('a' or 'b').
        summary: Human-readable compaction summary, may be empty.
    """
    ...

def show_turn_stats(
    self,
    agent: str,
    cost_usd: float | None,
    duration_ms: int | None,
    usage: dict | None = None,
) -> None:
    """Display per-turn cost, duration, and token usage.

    Args:
        agent: Which agent ('a' or 'b').
        cost_usd: Cost in USD for this turn, or None.
        duration_ms: Wall-clock duration in milliseconds, or None.
        usage: Token usage dict with input_tokens/output_tokens keys.
    """
    ...
```



