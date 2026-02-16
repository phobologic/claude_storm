---
id: claude_storm-bw6.7
status: closed
deps: []
links: []
created: 2026-02-14T19:51:21.114235-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Duplicated show_compaction and show_turn_stats logic across display classes

**File**: `/Users/mike/git/claude_storm/claude_storm/display.py`
**Line(s)**: 208-236 (PlainDisplay) and 448-479 (TextualDisplay)

**Description**: `show_compaction` and `show_turn_stats` have identical business logic duplicated between `PlainDisplay` and `TextualDisplay`. The `show_turn_stats` method in particular has the same parts-building logic (cost formatting, duration conversion, token formatting, dot-joined output) copied verbatim. Only the final render differs. This follows the same pattern as the `show_completion` duplication but applies to two additional methods.

**Suggested Fix**: Extract the formatting logic into module-level helper functions:

```python
def _format_turn_stats(
    cost_usd: float | None,
    duration_ms: int | None,
    usage: dict | None,
) -> str | None:
    """Format per-turn stats into a display string. Returns None if no stats."""
    parts: list[str] = []
    if cost_usd is not None:
        parts.append(f"${cost_usd:.4f}")
    if duration_ms is not None:
        parts.append(f"{duration_ms / 1000:.1f}s")
    if usage:
        parts.append(f"In: {usage.get('input_tokens', 0):,} Out: {usage.get('output_tokens', 0):,}")
    return f"  {' · '.join(parts)}" if parts else None
```

Each display class then just calls the formatter and renders the result.



