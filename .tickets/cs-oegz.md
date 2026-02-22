---
id: cs-oegz
status: open
deps: []
links: []
created: 2026-02-22T00:24:26Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:readability]
---
# Label strings 'is thinking' / 'is responding' are hardcoded inline rather than as constants

**File**: claude_storm/display.py
**Line(s)**: 626, 633
**Description**: The status suffix strings 'is thinking' and 'is responding' are constructed inline with f-strings. Tests then assert on substrings of these strings (e.g. 'is thinking' in thinking_msgs[0].label). This couples tests to exact formatting prose and makes it harder to change the wording or extend the states without hunting across both source and test files.
**Suggested Fix**: Define module-level constants, e.g. _THINKING_SUFFIX = 'is thinking' and _RESPONDING_SUFFIX = 'is responding', and reference them in both the display methods and the test assertions. This also makes the test intent clearer.

