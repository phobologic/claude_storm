---
id: claude_storm-csb.10
status: closed
deps: []
links: []
created: 2026-02-14T14:24:27.901305-08:00
type: task
priority: 3
parent: claude_storm-csb
---
# create_proposal has too many parameters -- consider RevisionContext dataclass

**File**: `/Users/mike/git/claude_storm/claude_storm/agreements.py`
**Line(s)**: 63-96
**Description**: `create_proposal` now accepts 9 parameters (config, title, content, agent, turn, revises, original_content, original_turn, original_agent). This is at the threshold where a parameter object would improve readability and reduce the chance of argument ordering mistakes.

The last 4 parameters (revises + 3 original_* fields) form a logical "revision context" group. Bundling them would align with the broader codebase pattern of using dataclasses for structured data.

**Suggested Fix**: Consider accepting a revision context object:

```python
@dataclass
class RevisionContext:
    revises: str
    original_content: str | None = None
    original_turn: int | None = None
    original_agent: str | None = None

def create_proposal(
    config, title, content, agent, turn,
    revision: RevisionContext | None = None,
) -> str:
```

This would also simplify `accept_proposal` which currently copies fields individually.



