---
id: cs-2fqp
status: closed
deps: []
links: [cs-6zjv]
created: 2026-02-23T02:37:49Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# Test imports Static from textual.widgets instead of textual.widgets._static

**File**: tests/test_app.py
**Line(s)**: 71, 86, 100
**Description**: The new tests import Static inside the async with block using 'from textual.widgets import Static'. While this works, it is inconsistent with the top-level import of SelectableRichLog and could be simplified. More importantly, the import is repeated in each test body rather than at module level, which adds minor noise and could cause confusion about why it is deferred. This appears to be a copy-paste from older test code that moved the import out of the async context in a previous refactor (visible in the diff hunk for test_interactive_mode).
**Suggested Fix**: Move 'from textual.widgets import Static' to the module-level import block alongside the other widget imports.


## Notes

**2026-02-23T02:51:08Z**

Duplicate of cs-6zjv. Both describe inline Static imports in test_app.py; cs-6zjv is more precise about the affected lines and fix.
