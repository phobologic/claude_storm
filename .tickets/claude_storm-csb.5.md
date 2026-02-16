---
id: claude_storm-csb.5
status: closed
deps: []
links: []
created: 2026-02-14T14:24:11.608629-08:00
type: task
priority: 2
parent: claude_storm-csb
---
# Use NamedTuple for _resolve_revision_context return type

**File**: `/Users/mike/git/claude_storm/claude_storm/session.py`
**Line(s)**: 188
**Description**: `_resolve_revision_context` returns a bare 4-tuple `tuple[str, str | None, int | None, str | None] | None`. The call site at line 315 unpacks this as `title, original_content, original_turn, original_agent = ctx`, which is readable only because the reader remembers (or checks) the return type annotation. This is the same pattern that was flagged and fixed for `_read_stream` in issue `claude_storm-w86` (replaced bare tuple with NamedTuple).

**Suggested Fix**: Define a `_RevisionContext` NamedTuple to give each field a name:

```python
class _RevisionContext(NamedTuple):
    title: str
    original_content: str | None
    original_turn: int | None
    original_agent: str | None
```

This is consistent with the existing precedent set by the `_StreamResult` NamedTuple fix and makes the return value self-documenting.



