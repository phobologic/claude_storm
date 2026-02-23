---
id: cs-xmuh
status: closed
deps: []
links: []
created: 2026-02-23T02:38:00Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:readability]
---
# _make_scroll_up_event helper belongs in a shared test fixture, not a module-level function

**File**: tests/test_widgets.py | **Line(s)**: 151-163 | **Description**: _make_scroll_up_event is a module-level helper that constructs a MouseScrollUp event. The project convention (CLAUDE.md) places shared test helpers in tests/conftest.py as fixtures. As a bare module-level function it cannot be reused from test_app.py or future test files without duplication. The lazy import of MouseScrollUp inside the function body is also inconsistent with the module-level import style used throughout the rest of the test file. **Suggested Fix**: Move to conftest.py as a pytest fixture (or a plain helper imported from a shared test utilities module), and hoist the MouseScrollUp import to the top of the file.


## Notes

**2026-02-23T05:39:49Z**

Closing as won't-fix. Description is inaccurate — MouseScrollUp is imported at call sites, not lazily inside the function body. More importantly, conftest.py is for cross-file fixtures; a helper only used in test_widgets.py belongs there. Moving it would be wrong, not an improvement.
