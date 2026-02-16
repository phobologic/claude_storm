---
id: claude_storm-29b.9
status: closed
deps: []
links: []
created: 2026-02-14T21:29:48.881661-08:00
type: task
priority: 3
parent: claude_storm-29b
---
# Redundant total_duration_s recomputation in _format_session_totals

**File**: display.py (line 57)
**Description**: _format_session_totals calls config.total_duration_s which parses ISO timestamps via datetime.fromisoformat() each time. In the show CLI command, total_duration_s is computed once for the duration display, then _format_session_totals computes it again internally. The property is not cached, so every access re-parses both timestamp strings.
**Suggested Fix**: Either cache with @functools.cached_property (careful about mutability), or pass the pre-computed duration into _format_session_totals as a parameter.
**Found by**: perf reviewer (Low)


