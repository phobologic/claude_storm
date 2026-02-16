---
id: claude_storm-csb.2
status: closed
deps: []
links: []
created: 2026-02-14T14:23:59.932114-08:00
type: task
priority: 2
parent: claude_storm-csb
---
# Duplicated conditional field-copying pattern for original_* fields

**File**: `/Users/mike/git/claude_storm/claude_storm/agreements.py`
**Line(s)**: 88-102, 131-146
**Description**: The pattern of conditionally copying `original_content`, `original_turn`, and `original_agent` fields from one dict to another is duplicated verbatim in both `create_proposal()` (lines 97-102) and `accept_proposal()` (lines 141-146). This trio of conditionals is identical in structure and purpose -- transferring optional revision metadata between dicts.

**Suggested Fix**: Extract a small helper that copies the optional original-fields in one place:

```python
_ORIGINAL_FIELDS = ("original_content", "original_turn", "original_agent")

def _copy_original_fields(source: dict, target: dict) -> None:
    """Copy optional original-revision fields from source to target."""
    for key in _ORIGINAL_FIELDS:
        if source.get(key) is not None:
            target[key] = source[key]
```

Then call `_copy_original_fields(proposal, agreement)` in `accept_proposal()` and build the proposal dict similarly in `create_proposal()`. This eliminates the duplication and makes it trivial to add future metadata fields.



