---
id: cs-m5cn
status: closed
deps: []
links: [cs-itvy]
created: 2026-02-23T02:37:17Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# on_mouse_scroll_up only detects upward scroll; keyboard Page Up / arrow up do not disengage scroll-lock

**File**: claude_storm/widgets.py
**Line(s)**: 37-40
**Description**: The scroll-lock disengagement is triggered only by MouseScrollUp events. Users who scroll up using keyboard navigation (Page Up, Up arrow, Home key) will not disengage following, so new output will keep auto-scrolling them back to the bottom while they are trying to read. This is a significant UX gap since keyboard navigation is a common pattern in terminal/TUI apps.
**Suggested Fix**: Also handle on_key for Page Up, Up arrow, and Home keys to disengage following, mirroring the same guard (if self.following: self.following = False).

