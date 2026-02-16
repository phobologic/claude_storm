---
id: claude_storm-ge3
status: closed
deps: [claude_storm-9vd]
links: []
created: 2026-02-06T11:37:59.891674-08:00
type: task
priority: 3
---
# Add streaming display methods to DisplayProtocol

Extend DisplayProtocol with three new methods: show_agent_stream_start(config, agent) to begin a streaming response block, show_agent_stream_delta(text) to append incremental text, and show_agent_stream_end() to finalize the block. Implement in PlainDisplay (print deltas to console directly, replacing the thinking_status spinner once streaming starts) and TextualDisplay (post messages to update a RichLog or similar scrolling widget). The existing show_agent_response() should still be called after stream completes for any post-processing, or be made optional if streaming handles it.


