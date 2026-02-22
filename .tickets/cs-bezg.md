---
id: cs-bezg
status: closed
deps: []
links: [cs-3ds5]
created: 2026-02-22T00:24:32Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:perf]
---
# Stale _thinking_cleared flag retained after refactor creates misleading state

**File**: claude_storm/display.py
**Line(s)**: 624, 634-635
**Description**: After the refactor, `_thinking_cleared` is still set to True inside show_agent_stream_delta() (line 635) and reset to False inside show_agent_stream_start() (line 624), but it is no longer read anywhere in the updated code paths. The only remaining consumer was the removed guard in show_agent_stream_end(). Carrying a boolean that is written but never read wastes a state-tracking assignment on every first-chunk call and creates cognitive overhead when reading the code, with a small risk that a future developer resurrects a stale guard against it.
**Suggested Fix**: Remove the `_thinking_cleared` instance variable and its two assignment sites entirely. The `_stream_responding` flag now fully covers the state previously tracked by `_thinking_cleared`.


## Notes

**2026-02-22T00:25:44Z**

Duplicate of cs-3ds5
