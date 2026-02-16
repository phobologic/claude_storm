---
id: claude_storm-29b.7
status: closed
deps: []
links: []
created: 2026-02-14T21:29:36.621264-08:00
type: task
priority: 2
parent: claude_storm-29b
---
# ended_at timestamp excludes compilation/summary duration

**File**: session.py (lines 516-534)
**Description**: ended_at is set in the finally block (line 521), but compilation and summary generation happen after the finally block (lines 525-527). This means total_duration_s underreports the true wall-clock time for completed sessions -- compilation can involve additional agent invocations.
**Suggested Fix**: Move the ended_at assignment to after compilation/summary completes (near line 529), or document explicitly that the duration excludes compilation time.
**Found by**: logic reviewer (Medium)


