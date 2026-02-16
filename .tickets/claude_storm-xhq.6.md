---
id: claude_storm-xhq.6
status: closed
deps: []
links: []
created: 2026-02-06T12:58:07.161735-08:00
type: chore
priority: 4
external-ref: LOW-LOGIC-002
parent: claude_storm-xhq
---
# Note TUI fallback rendering asymmetry with streamed content

LOW-LOGIC-002: app.py:140-141 — streamed content goes through join+Markdown, fallback goes directly to Markdown. If they ever differ, user sees different output depending on path. Acceptable but worth noting.


