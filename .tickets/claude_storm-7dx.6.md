---
id: claude_storm-7dx.6
status: closed
deps: []
links: []
created: 2026-02-16T14:51:27.940463-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Duplicated extension-stripping regex in compilation.py

**File**: /Users/mike/git/claude_storm/claude_storm/compilation.py
**Line(s)**: 43, 155
**Description**: The regex `r"\.\w{1,5}$"` for stripping file extensions is duplicated in two places within the same file -- once in `find_matching_artifacts` (line 43) and once in `compile_deliverables` (line 155). If the extension-stripping logic needs to change (e.g., supporting longer extensions), both sites must be updated in lockstep.

**Suggested Fix**: Extract a small helper function:

```python
def _strip_extension(name: str) -> str:
    """Remove a trailing file extension (up to 5 chars) from a name."""
    return re.sub(r"\.\w{1,5}$", "", name)
```

Then call `_strip_extension(deliverable_name)` and `_strip_extension(deliverable)` at lines 43 and 155 respectively.



