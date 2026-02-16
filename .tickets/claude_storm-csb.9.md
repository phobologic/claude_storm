---
id: claude_storm-csb.9
status: closed
deps: []
links: []
created: 2026-02-14T14:24:25.507305-08:00
type: task
priority: 3
parent: claude_storm-csb
---
# Multiple return paths in _format_agreement_block reduce readability

**File**: `/Users/mike/git/claude_storm/claude_storm/agreements.py`
**Line(s)**: 184-211
**Description**: The `_format_agreement_block` function has grown with the revision changes and now has two separate `return` statements inside the `if a.get("revises")` branch (lines 199-203 and 204) plus the general return at line 211 that is only reachable via the `else` branch. The early return at line 204 combined with the `else` at line 205 creates a structure where the final `return` at line 211 appears to serve both branches but actually only serves the `else`. This is correct but confusing to read.

**Suggested Fix**: Restructure so each branch has a single, clear return path. One approach:

```python
def _format_agreement_block(a: dict) -> str:
    label = "Agent A" if a["proposed_by"] == "a" else "Agent B"
    if a.get("revises"):
        header = f"## [{a['revises']} -> {a['id']}] {a['title']} (revised)"
        # ... build meta ...
        body = (
            f"### Original proposal\n{a['original_content']}\n\n"
            f"### Revisions\n{a['content']}"
            if a.get("original_content")
            else a["content"]
        )
    else:
        header = f"## [{a['id']}] {a['title']}"
        # ... build meta ...
        body = a["content"]
    return f"{header}\n{meta}\n\n{body}"
```

This gives a single return point and makes the structure uniform.



