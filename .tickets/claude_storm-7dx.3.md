---
id: claude_storm-7dx.3
status: closed
deps: []
links: []
created: 2026-02-16T14:51:17.133039-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Warning message uses original filename instead of draft-prefixed name

**File**: `/Users/mike/git/claude_storm/claude_storm/session.py`
**Line(s)**: 307-309
**Description**: The `draft-` prefix logic in `process_directives` only checks `filename.startswith("draft-")` to avoid double-prefixing. However, the path traversal security check on line 311 uses the *modified* `draft_filename` but the warning message on line 312 reports the *original* `filename`. If an agent produces a malicious filename like `../evil.md`, the warning will say `"../evil.md"` but the actual path checked was `draft-../evil.md`. This is a minor inconsistency — the security check still works correctly since `draft-../evil.md` would also fail `is_relative_to` — but the warning message is misleading.

**Suggested Fix**: Use `draft_filename` in the warning message for consistency:

```python
display.show_warning(f"Blocked artifact with unsafe filename: {draft_filename!r}")
```



