---
id: claude_storm-3ux
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:03:12.4833-08:00
type: bug
priority: 1
---
# Fix streaming display rendering (markdown, TUI fragmentation, backpressure)

HIGH-LOGIC-002 + HIGH-LOGIC-003 + HIGH-PERF-001: Three related display issues: (1) PlainDisplay streams raw text instead of rendered Markdown. (2) TUI RichLog.write() per delta creates fragmented vertical lines instead of flowing text. (3) No backpressure on StreamDelta messages — unbounded queue could cause TUI lag. Need to buffer/batch deltas and render accumulated text as Markdown. Files: session.py:149-158, app.py:122-124, display.py


