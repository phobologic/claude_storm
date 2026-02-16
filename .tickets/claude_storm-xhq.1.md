---
id: claude_storm-xhq.1
status: closed
deps: []
links: []
created: 2026-02-06T12:57:43.379567-08:00
type: bug
priority: 1
external-ref: HIGH-LOGIC-001
parent: claude_storm-xhq
---
# Add text=response.text to generate_summary stream end call

HIGH-LOGIC-001: compilation.py:176 — show_agent_stream_end missing text=response.text. The TUI fallback fix was applied to 2/3 call sites but missed summary generation. One-line fix.


