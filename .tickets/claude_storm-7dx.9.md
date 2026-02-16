---
id: claude_storm-7dx.9
status: closed
deps: []
links: []
created: 2026-02-16T14:51:40.117024-08:00
type: task
priority: 1
parent: claude_storm-7dx
---
# find_matching_artifacts matches both draft and compiled files on re-compilation

**File**: `/Users/mike/git/claude_storm/claude_storm/compilation.py`
**Line(s)**: 54
**Description**: The `draft-` prefix stripping in `find_matching_artifacts` uses `re.sub(r"^draft-", "", path.stem)` which only strips a single `draft-` prefix. This is correct. However, if the same deliverable name is used across multiple sessions or re-compilations, the matching logic will now match *both* `draft-design_document.md` and `design_document.md` (the compiled output), causing the compiled text to be fed back into the compilation prompt as "existing artifact content." This means re-running compilation would include the previous compilation's output in the context, potentially causing the compiler to produce a worse result (echo chamber effect) or an unnecessarily large prompt.

**Suggested Fix**: When finding matching artifacts for compilation, either:
1. Prefer non-draft files over draft files when both exist for the same stem, or
2. Only match `draft-*` files (since those are the agent-produced ones that need compiling)

```python
# Option 2: only consider draft files during compilation
for path in sorted(artifacts_dir.glob("draft-*.md")):
    stem = re.sub(r"^draft-", "", path.stem)
    ...
```



