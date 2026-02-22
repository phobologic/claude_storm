---
id: cs-3ds5
status: open
deps: []
links: [cs-bezg, cs-yv6q]
created: 2026-02-22T00:24:20Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:logic]
---
# _thinking_cleared flag is now a dead write in display.py

**File**: claude_storm/display.py
**Line(s)**: 624, 635
**Description**: After the refactor, `_thinking_cleared` is still assigned in both `show_agent_stream_start` (line 624, set to False) and `show_agent_stream_delta` (line 635, set to True), but it is never read anywhere in the updated code. The guard `if not self._thinking_cleared` was removed from `show_agent_stream_end`, and the old `if not self._thinking_cleared` guard in `show_agent_stream_delta` was replaced by `_stream_responding`. The field now exists and is written but provides no value, adding noise and potential confusion for future maintainers.
**Suggested Fix**: Remove the `self._thinking_cleared` attribute entirely — delete the assignment in `__init__`, `show_agent_stream_start`, and `show_agent_stream_delta`.

