---
id: claude_storm-csb.7
status: closed
deps: []
links: []
created: 2026-02-14T14:24:14.248369-08:00
type: task
priority: 3
parent: claude_storm-csb
---
# Agreement/proposal dicts lack typed schema definition

**File**: `/Users/mike/git/claude_storm/claude_storm/agreements.py`
**Line(s)**: 88, 131
**Description**: Both `create_proposal()` and `accept_proposal()` annotate their dict as `proposal: dict` and `agreement: dict` respectively. This is a bare `dict` with no indication of what keys are expected. These dicts are the core data structures for the agreement protocol (used across `agreements.py`, `session.py`, `config.py`, and tests), yet there is no TypedDict or documented schema defining the expected shape.

Adding `original_content`, `original_turn`, and `original_agent` as optional keys exacerbates this -- it is impossible to know the full set of keys without reading every code path that constructs or reads these dicts.

**Suggested Fix**: Define `ProposalDict` and `AgreementDict` as TypedDicts (or at minimum, document the schema in the module docstring). For example:

```python
class ProposalDict(TypedDict):
    id: str
    title: str
    content: str
    proposed_by: str
    turn: int
    revises: str | None
    summary: str
    original_content: NotRequired[str]
    original_turn: NotRequired[int]
    original_agent: NotRequired[str]
```

This is a larger refactor but would significantly improve maintainability as the schema grows. At minimum, a docstring enumerating the keys would help.



