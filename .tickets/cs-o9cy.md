---
id: cs-o9cy
status: closed
deps: []
links: []
created: 2026-02-23T02:37:56Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# TestScrollLock calls on_mouse_scroll_up directly, bypassing Textual event dispatch

**File**: tests/test_widgets.py
**Line(s)**: 185, 199, 211, 225
**Description**: Several TestScrollLock tests call log.on_mouse_scroll_up(event) directly as a plain method call rather than dispatching the event through Textual's event system (e.g. pilot.mouse_scroll_up()). This bypasses event bubbling, prevent_default, and stop() semantics. The tests therefore verify the handler method in isolation but do not confirm the feature works end-to-end through Textual's event pipeline. A regression in event routing would not be caught.
**Suggested Fix**: Use pilot.mouse_scroll_up(widget=log) or post_message to dispatch through Textual's event system for at least one integration-level test. Keep direct method calls only for pure unit tests clearly labelled as such.

