---
id: claude_storm-7dx.7
status: closed
deps: []
links: []
created: 2026-02-16T14:51:29.941416-08:00
type: task
priority: 2
parent: claude_storm-7dx
---
# draft- prefix applied to full path, not just basename

**File**: `/Users/mike/git/claude_storm/claude_storm/session.py`
**Line(s)**: 307-309
**Description**: The `draft-` prefixing uses simple string concatenation. If an agent produces an artifact with a subdirectory path like `subdir/chapter1.md`, the result would be `draft-subdir/chapter1.md` — a file literally named `draft-subdir` followed by a path separator, which would fail or create unexpected directory structures.

Currently the path traversal check on line 311 would likely catch this (since `draft-subdir/chapter1.md` resolved under `artifacts_dir` would need `draft-subdir/` to exist as a directory). But the failure mode is silent — the security check catches it as "unsafe" when really it's just a naming issue.

**Suggested Fix**: Apply the `draft-` prefix to only the basename portion of the filename:

```python
from pathlib import PurePosixPath

base = PurePosixPath(filename)
draft_filename = str(base.parent / f"draft-{base.name}") if not base.name.startswith("draft-") else filename
```

Or, more simply, reject filenames containing path separators before the prefix logic (the security check already handles this, but an explicit early check would be clearer).



