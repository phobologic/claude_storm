---
id: claude_storm-7dx.4
status: open
deps: []
links: []
created: 2026-02-16T14:51:25.084466-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Draft artifacts not cleaned up after compilation

**File**: `/Users/mike/git/claude_storm/claude_storm/compilation.py`
**Line(s)**: 153-161
**Description**: The compiled output is written to the "clean" filename (e.g., `design_document.md`) while agent drafts now live at `draft-design_document.md`. However, `compile_deliverables` does not clean up the old `draft-*` files after writing the final compiled version. Over multiple compilation runs or when users inspect the artifacts directory, they'll see both `draft-design_document.md` and `design_document.md` side by side with no indication of which is current.

This isn't a bug per se, but it creates a confusing user experience since the artifacts directory will accumulate both drafts and finals without clear lifecycle management.

**Suggested Fix**: After writing the compiled artifact, optionally remove or rename the matched draft files:

```python
if not response.is_error:
    # ... write compiled artifact ...
    
    # Clean up draft files that were compiled into this artifact
    for draft_name in matching_artifacts:
        if draft_name.startswith("draft-"):
            (artifacts_dir / draft_name).unlink(missing_ok=True)
```

Alternatively, document this as intentional behavior (drafts are preserved for reference).



