---
id: cs-i8cr
status: open
deps: []
links: []
created: 2026-02-22T00:24:56Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:readability]
---
# test_show_agent_stream_end_always_clears_thinking creates two separate app instances instead of using parameterize

**File**: tests/test_textual_display.py
**Line(s)**: 182-208
**Description**: The test test_show_agent_stream_end_always_clears_thinking tests two scenarios (no deltas received; deltas received) by creating app and app2 / display and display2 inside a single test function. This is harder to read and debug than separate parameterized or split test cases, because a failure in the second scenario produces a traceback in the middle of a long function body with no clear label.
**Suggested Fix**: Split into two focused test functions with descriptive names, or use @pytest.mark.parametrize with a fixture. The existing convention in the test file is one scenario per function.

