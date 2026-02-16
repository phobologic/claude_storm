---
id: claude_storm-xhq.8
status: closed
deps: []
links: []
created: 2026-02-06T12:58:12.185898-08:00
type: chore
priority: 4
external-ref: LOW-LOGIC-004
parent: claude_storm-xhq
---
# Clear thinking indicator on first StreamDelta instead of StreamEnd

LOW-LOGIC-004: display.py:416-437 — UpdateThinking posted at stream start, ClearThinking at end. Timer ticks during active streaming when irrelevant. Also redundant with thinking_status context manager.


