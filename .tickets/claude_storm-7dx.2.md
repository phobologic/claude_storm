---
id: claude_storm-7dx.2
status: open
deps: []
links: []
created: 2026-02-16T14:51:12.693001-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Repeated regex compilation in find_matching_artifacts hot loop

**File**: /Users/mike/git/claude_storm/claude_storm/compilation.py
**Line(s)**: 43-55
**Description**: The function calls `re.sub()` with string patterns inside the loop on every artifact file (line 54-55) and outside the loop for the deliverable name (lines 43-46). While `re` caches compiled patterns internally, the cache lookup is repeated on every call. In the loop body, `re.sub(r"^draft-", "", path.stem)` and `re.sub(r"[_\-]", " ", stem)` are called for every `.md` file in the artifacts directory.

This is a **Low** impact issue because the artifacts directory is small in practice (tens of files at most), so the overhead is negligible. However, precompiling the patterns as module-level constants would be marginally cleaner and avoids repeated cache lookups.

**Suggested Fix**: Precompile regex patterns as module-level constants:
```python
_RE_DRAFT_PREFIX = re.compile(r"^draft-")
_RE_SEPARATORS = re.compile(r"[_\-]")
_RE_EXTENSION = re.compile(r"\.\w{1,5}$")
_RE_NON_WORD = re.compile(r"[^\w\s-]")
```
Then use `.sub()` on the compiled objects instead of `re.sub()`.


