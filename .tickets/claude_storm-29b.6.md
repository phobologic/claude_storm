---
id: claude_storm-29b.6
status: open
deps: []
links: []
created: 2026-02-14T21:29:26.557599-08:00
type: task
priority: 3
parent: claude_storm-29b
---
# Cross-module import of private _-prefixed functions from display.py in cli.py

**File**: cli.py (lines 460-470)
**Description**: _format_duration and _format_session_totals are imported from display.py into cli.py. Both are prefixed with _, signaling they are private to their module. Using them cross-module breaks that convention. Additionally, they are imported via two separate lazy imports within the function body, though cli.py already imports from display at the top level.
**Suggested Fix**: Either rename to format_duration / format_session_totals (drop leading underscore) to signal public API, or consolidate into a single top-level import since cli.py is already allowed to import display.
**Found by**: logic reviewer (Low), readability reviewer (Low)


