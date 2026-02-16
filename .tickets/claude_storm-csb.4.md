---
id: claude_storm-csb.4
status: closed
deps: []
links: []
created: 2026-02-14T14:24:05.176032-08:00
type: task
priority: 2
parent: claude_storm-csb
---
# Chained revisions lose root original content

**File**: `/Users/mike/git/claude_storm/claude_storm/session.py`
**Line(s)**: 204-214
**Description**: When revising an accepted agreement that was itself a revision (chained revisions, e.g., A→B→C), `_resolve_revision_context` captures `original["content"]` -- which is the *revision's* content, not the *root original's* content. If the accepted agreement already has `original_content` (because it was itself a revision), that deeper original is lost.

For example:
1. Agent A proposes "v1" (id=abc)
2. Agent B revises to "v2" (id=def, revises=abc, original_content="v1")
3. Agent A revises accepted agreement def to "v3" -- now original_content="v2", and "v1" is lost

This may be acceptable as a design choice (only preserve one level of history), but it's worth noting that the "original" label in the rendered output can be misleading for multi-hop revisions. Consider either documenting this as intentional single-level preservation, or threading the root original through the chain.

**Suggested Fix**: At minimum, add a comment documenting this is single-level preservation. For full history:

```python
if original:
    # For chained revisions, preserve the deepest original
    orig_content = original.get("original_content", original["content"])
    orig_turn = original.get("original_turn", original.get("proposed_turn"))
    orig_agent = original.get("original_agent", original.get("proposed_by"))
    return (original["title"], orig_content, orig_turn, orig_agent)
```



