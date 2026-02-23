---
id: cs-ees6
status: closed
deps: []
links: []
created: 2026-02-23T02:37:11Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# scroll_to_bottom sets following=True before scroll_end, risking double FollowingChanged message

**File**: claude_storm/widgets.py
**Line(s)**: 48-51
**Description**: scroll_to_bottom() sets self.following = True first, which synchronously fires watch_following → posts FollowingChanged(following=True) and sets auto_scroll = True. Then scroll_end(animate=False) triggers a scroll_y change, which enters watch_scroll_y. At that point is_vertical_scroll_end is True and following is already True, so the second branch is skipped — but only by coincidence. If Textual defers the scroll, watch_scroll_y may fire before the position is updated, leaving a window where both code paths interact unexpectedly. More importantly, the indicator is hidden via the message before the scroll actually reaches the bottom, which could produce a brief visual flicker if the scroll fails.
**Suggested Fix**: Set following = True only after confirming the scroll completed (e.g., inside watch_scroll_y when is_vertical_scroll_end is True), or suppress the watch_scroll_y re-engagement path when scroll_to_bottom is in progress via a guard flag.

