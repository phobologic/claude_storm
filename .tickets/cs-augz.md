---
id: cs-augz
status: open
deps: []
links: []
created: 2026-02-22T00:24:41Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:readability]
---
# show_agent_stream_start docstring does not mention the new 'is thinking' label convention

**File**: claude_storm/display.py
**Line(s)**: 618
**Description**: The docstring for show_agent_stream_start() says only 'Post a StreamStart message to the TUI.' It does not mention that it also posts UpdateThinking with a formatted 'is thinking' label, stores _stream_label for use by subsequent delta calls, or resets _stream_responding. The two-phase flow (thinking -> responding) is a non-obvious contract between show_agent_stream_start, show_agent_stream_delta, and show_agent_stream_end, and is not documented anywhere.
**Suggested Fix**: Expand the docstring to describe the full lifecycle: that this method begins the 'thinking' phase, that show_agent_stream_delta() will transition to 'responding', and that show_agent_stream_end() terminates the bar. A short note on _stream_label and _stream_responding as stateful bridges would help maintainers.

