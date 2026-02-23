---
id: cs-60jg
status: closed
deps: []
links: [cs-l1bt]
created: 2026-02-23T02:37:02Z
type: task
priority: 1
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# watch_scroll_y re-engagement logic is unreliable: position-based rather than intent-based

**File**: claude_storm/widgets.py
**Line(s)**: 42-46
**Description**: watch_scroll_y re-engages scroll-lock whenever is_vertical_scroll_end is True, even during programmatic scrolls (e.g. auto_scroll writes, truncate_to). This means a user who scrolled up, then a new line is appended and Textual internally scrolls the virtual viewport, could see following unexpectedly flip back to True even though the user is still reading. The trigger should be user-initiated navigation to the bottom, not any scroll position check.
**Suggested Fix**: Track user intent more explicitly. Consider re-engaging following only inside on_key (e.g. End key) and on_mouse_scroll_down events, not in the position watcher which fires for all scroll changes regardless of source.

