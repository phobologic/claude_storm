---
id: claude_storm-u89
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:04:20.205047-08:00
type: task
priority: 3
---
# Handle stream_end gracefully on error responses

LOW-LOGIC-002: show_agent_stream_start/end called regardless of error. On error, partial content appears with no error indication. Have stream_end accept an error flag or display interrupted message. Files: session.py:149-158, compilation.py


