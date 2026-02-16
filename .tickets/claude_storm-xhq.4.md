---
id: claude_storm-xhq.4
status: closed
deps: []
links: []
created: 2026-02-06T12:58:00.860783-08:00
type: chore
priority: 3
external-ref: LOW-READ-001
parent: claude_storm-xhq
---
# Add comment explaining fallback logic in StormApp.on_stream_end

LOW-READ-001: app.py:139-141 — fallback logic not obvious without stream-json migration context. Add comment explaining when _stream_parts would be empty while message.text is populated.


