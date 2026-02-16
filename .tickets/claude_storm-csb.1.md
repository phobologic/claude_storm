---
id: claude_storm-csb.1
status: closed
deps: []
links: []
created: 2026-02-14T14:23:55.145527-08:00
type: task
priority: 3
parent: claude_storm-csb
---
# Truthiness vs None check inconsistency in _format_agreement_block

**File**: `/Users/mike/git/claude_storm/claude_storm/agreements.py`
**Line(s)**: 198
**Description**: `_format_agreement_block` uses `a.get("original_content")` as a truthiness check to decide whether to render the "Original proposal" section. If `original_content` is an empty string `""`, this evaluates to falsy and the section is silently skipped -- the same behavior as if original_content were absent. This is a semantic difference: an empty string means "the original existed but had no content" vs. `None`/absent meaning "we don't have the original."

While unlikely in practice (proposals probably always have content), this is inconsistent with the rest of the code which uses `is not None` checks (lines 141, 143, 145 in the same file).

**Suggested Fix**: Use `a.get("original_content") is not None` for consistency:

```python
# Current
if a.get("original_content"):
    return (...)
return f"{header}\n{meta}\n\n{a['content']}"

# Suggested
if a.get("original_content") is not None:
    return (...)
return f"{header}\n{meta}\n\n{a['content']}"
```



