---
id: claude_storm-bw6.1
status: closed
deps: []
links: []
created: 2026-02-14T19:51:08.683692-08:00
type: task
priority: 2
parent: claude_storm-bw6
---
# DisplayProtocol methods show_compaction and show_turn_stats missing docstrings

**File**: `/Users/mike/git/claude_storm/claude_storm/display.py`
**Line(s)**: 85-92

**Description**: The two new `DisplayProtocol` methods (`show_compaction` and `show_turn_stats`) lack docstrings in the Protocol definition, unlike every other method in the Protocol class which has a proper docstring with Args documentation. This breaks the established pattern where the Protocol serves as the canonical documentation for all display methods.

**Suggested Fix**: Add docstrings consistent with the other Protocol methods:

```python
def show_compaction(self, agent: str, summary: str) -> None:
    """Display a warning that an agent's context was compacted.

    Args:
        agent: Which agent ('a' or 'b').
        summary: Human-readable compaction summary text.
    """
    ...

def show_turn_stats(
    self,
    agent: str,
    cost_usd: float | None,
    duration_ms: int | None,
    usage: dict | None = None,
) -> None:
    """Display per-turn cost and performance statistics.

    Args:
        agent: Which agent ('a' or 'b').
        cost_usd: Cost in USD for this turn, if available.
        duration_ms: Duration of the turn in milliseconds, if available.
        usage: Token usage dict with input_tokens/output_tokens keys.
    """
    ...
```



