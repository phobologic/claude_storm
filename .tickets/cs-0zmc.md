---
id: cs-0zmc
status: closed
deps: []
links: [cs-ktdo]
created: 2026-02-23T02:37:41Z
type: task
priority: 4
assignee: Michael Barrett
parent: cs-ohde
---
# FollowingChanged carries unnecessary widget reference

FollowingChanged message stores self.log (the SelectableRichLog widget), keeping it alive while in the message queue. The app handler never uses message.log — it calls query_one instead. Removing self.log from the message avoids unintended retention of the widget (and its _line_cache). File: claude_storm/widgets.py line 33


## Notes

**2026-02-23T02:51:04Z**

Duplicate of cs-ktdo. Both describe removing self.log from FollowingChanged; cs-0zmc additionally notes widget retention concern but fix is identical.
