---
id: claude_storm-7dx.5
status: closed
deps: []
links: []
created: 2026-02-16T14:51:26.295506-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Redundant mkdir call inside artifact-saving loop

**File**: /Users/mike/git/claude_storm/claude_storm/session.py
**Line(s)**: 314
**Description**: Inside the artifact-saving loop, `artifact_path.parent.mkdir(parents=True, exist_ok=True)` is called for every artifact. Since `artifacts_dir` is the same directory for all artifacts, this issues a redundant `mkdir` syscall on every iteration after the first.

The cost is trivial (the OS handles `exist_ok=True` cheaply), but moving the `mkdir` call before the loop would be slightly cleaner and avoid repeated syscalls.

**Suggested Fix**: Move the directory creation before the loop:
```python
artifacts_dir = config.session_dir() / "artifacts"
artifacts_dir.mkdir(parents=True, exist_ok=True)  # create once
for filename, content in directives.artifacts:
    draft_filename = (
        f"draft-{filename}" if not filename.startswith("draft-") else filename
    )
    artifact_path = (artifacts_dir / draft_filename).resolve()
    ...
```



