---
id: claude_storm-29b.8
status: closed
deps: []
links: []
created: 2026-02-14T21:29:42.501134-08:00
type: task
priority: 3
parent: claude_storm-29b
---
# _format_duration lacks hour-level formatting

**File**: display.py (lines 25-37) and debug.py (lines 151-157)
**Description**: _format_duration only handles minutes and seconds. For sessions exceeding one hour, the output would be e.g. "75m 30s" rather than "1h 15m 30s". Minor readability concern for long-running sessions.
**Suggested Fix**: Add an hour tier: divmod(minutes, 60) for hours, with conditional formatting.
**Found by**: logic reviewer (Low)


