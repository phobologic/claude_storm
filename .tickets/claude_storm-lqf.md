---
id: claude_storm-lqf
status: closed
deps: [claude_storm-9vd]
links: []
created: 2026-02-06T11:37:51.868694-08:00
type: task
priority: 3
---
# Add NDJSON stream reader to agents.py

Replace subprocess.communicate() in invoke_agent() with a line-by-line stdout reader that parses stream-json NDJSON events. Accumulate content_block_delta text into the final AgentResponse. Keep the existing blocking API signature (returns AgentResponse) but read incrementally internally. Add a callback parameter (e.g. on_delta: Callable[[str], None] | None = None) so callers can optionally receive incremental text. Handle message_start, content_block_delta, message_stop, and error events. Respect _process_lock and _active_process for cancel_active() support. Update --output-format json to --output-format stream-json in cmd construction.


