---
id: cs-l1bt
status: closed
deps: []
links: [cs-60jg]
created: 2026-02-23T02:37:41Z
type: bug
priority: 2
assignee: Michael Barrett
parent: cs-ohde
---
# watch_scroll_y fires on every scroll tick during streaming

watch_scroll_y is a Textual reactive watcher that triggers on every incremental scroll_y change. During active streaming this fires dozens of times per second (new output → auto-scroll → watcher → is_vertical_scroll_end check → conditional FollowingChanged message post → DOM query_one in handler). Fix: move re-engagement logic out of watch_scroll_y into explicit user-gesture handlers so it only runs on intentional user actions, not every scroll position change. File: claude_storm/widgets.py lines 40-45


## Notes

**2026-02-23T02:51:07Z**

Duplicate of cs-60jg. Both describe watch_scroll_y re-engagement being position-based rather than intent-based; cs-60jg is p1 with more complete UX analysis. Performance concern (fires on every tick) is implicit in moving logic to gesture handlers.
