---
id: claude_storm-7dx.14
status: closed
deps: []
links: []
created: 2026-02-16T14:52:04.673773-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Test removed negative assertion without replacement for new naming scheme

**File**: /Users/mike/git/claude_storm/tests/test_compilation.py
**Line(s)**: 94
**Description**: The test `test_no_draft_backup_when_no_preexisting` removed the assertion `assert not (artifacts_dir / "new_document.draft.md").exists()` but did not add a replacement assertion verifying no `draft-` prefixed file exists either. The test now only checks the positive case (compiled file exists) without verifying the negative case (no spurious draft files), which was the original intent of the test.

**Suggested Fix**: Add a negative assertion consistent with the new naming scheme:

```python
assert (artifacts_dir / "new_document.md").read_text() == "fresh content\n"
assert not list(artifacts_dir.glob("draft-new_document*"))
```



