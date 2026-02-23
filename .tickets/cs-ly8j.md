---
id: cs-ly8j
status: open
deps: []
links: []
created: 2026-02-23T02:38:11Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:readability]
---
# Undocumented interaction between scroll_to_bottom and watch_scroll_y

**File**: claude_storm/widgets.py **Line(s)**: 48-51 and 42-46 **Description**: scroll_to_bottom sets following=True then calls scroll_end. When scroll_end resolves, watch_scroll_y fires and the is_vertical_scroll_end branch sets following=True again, triggering a second FollowingChanged post (a no-op but a double-fire). This is invisible from reading either method alone. A comment in scroll_to_bottom noting that watch_scroll_y will also fire would prevent future confusion if either method is modified. **Suggested Fix**: Add an inline comment: following=True here prevents a flash of the scroll indicator before watch_scroll_y also fires at the bottom.

