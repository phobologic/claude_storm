---
id: claude_storm-csb.8
status: closed
deps: []
links: []
created: 2026-02-14T14:24:18.664868-08:00
type: task
priority: 2
parent: claude_storm-csb
---
# Use NamedTuple for _resolve_revision_context return type

**File**: `/Users/mike/git/claude_storm/claude_storm/session.py`
**Line(s)**: 188
**Description**: The return type `tuple[str, str | None, int | None, str | None] | None` is a positional 4-tuple where three of the four elements are optional. This is the same pattern that was flagged and fixed in a previous code review for `_read_stream` (issue `claude_storm-w86`), which was refactored to use a `NamedTuple`.

Positional tuples with multiple optional fields are error-prone -- callers must remember the order and it's easy to confuse `original_turn` with `original_agent` since both can be `None`.

**Suggested Fix**: Define a `NamedTuple` or `dataclass`:

```python
class _RevisionContext(NamedTuple):
    title: str
    original_content: str | None
    original_turn: int | None
    original_agent: str | None
```

Then return `_RevisionContext(...)` instead of a bare tuple. The unpacking at the call site still works identically.



