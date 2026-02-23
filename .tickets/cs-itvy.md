---
id: cs-itvy
status: closed
deps: []
links: [cs-m5cn]
created: 2026-02-23T02:37:47Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:readability]
---
# scroll-lock only intercepts mouse scroll up, not keyboard Page Up / arrow keys

**File**: claude_storm/widgets.py | **Line(s)**: 37-40 | **Description**: on_mouse_scroll_up disengages the scroll-lock when the user scrolls up with the mouse wheel. However, RichLog also responds to keyboard navigation (Page Up, arrow keys, Home). If a user scrolls up via keyboard the scroll-lock is not disengaged, so auto_scroll stays True and immediately snaps back to the bottom, creating confusing UX. The docstring says 'User scrolled up' but only handles mouse events. **Suggested Fix**: Also hook on_key (or override scroll_up / on_scroll_up) to disengage following on upward keyboard navigation, or add a comment clearly documenting the known limitation so the next developer understands the gap.


## Notes

**2026-02-23T02:51:05Z**

Duplicate of cs-m5cn. Both describe keyboard navigation not disengaging scroll-lock; cs-m5cn has higher priority and more specific fix.
