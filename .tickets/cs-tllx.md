---
id: cs-tllx
status: open
deps: []
links: []
created: 2026-02-23T02:38:04Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# watch_scroll_y calls super() which may trigger unexpected RichLog internal behavior

**File**: claude_storm/widgets.py
**Line(s)**: 42-46
**Description**: watch_scroll_y calls super().watch_scroll_y(old, new). RichLog's watch_scroll_y is an internal Textual method not part of the documented public API. Its behavior (and whether it exists) may change across Textual versions, and calling it unconditionally couples the scroll-lock feature tightly to Textual internals. If RichLog's parent implementation is removed or renamed in a future Textual release, this will raise AttributeError at runtime with no indication of what changed.
**Suggested Fix**: Check whether super().watch_scroll_y exists before calling it, or file a note in the codebase that this relies on a Textual internal and should be audited when Textual is upgraded. At minimum, pin the Textual version constraint to prevent silent breakage.

