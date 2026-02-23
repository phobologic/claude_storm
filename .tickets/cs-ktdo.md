---
id: cs-ktdo
status: closed
deps: []
links: [cs-91g8, cs-0zmc]
created: 2026-02-23T02:37:24Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# FollowingChanged message exposes internal widget reference via self.log

**File**: claude_storm/widgets.py
**Line(s)**: 24-30
**Description**: The FollowingChanged message stores a direct reference to the SelectableRichLog widget (self.log). The app handler on_selectable_rich_log_following_changed does not use message.log at all — it queries by ID instead. Exposing the widget reference in the message is unnecessary coupling and invites callers to mutate widget state from message handlers, bypassing Textual's reactive system.
**Suggested Fix**: Remove the log parameter from FollowingChanged.__init__ and the self.log attribute. If the sender identity is ever needed, callers can use message.control (the standard Textual Message attribute that already points to the posting widget).

