---
id: claude_storm-29b.5
status: closed
deps: []
links: []
created: 2026-02-14T21:29:18.235582-08:00
type: task
priority: 2
parent: claude_storm-29b
---
# Import of datetime inside finally block in session.py

**File**: session.py (lines 519-520)
**Description**: from datetime import UTC, datetime is imported lazily inside the finally block of run_session. The datetime module is stdlib with no circular dependency risk, and config.py already imports it at the top level. Importing inside finally is unconventional, marginally slower, and if the import were to fail it would mask the original exception from the try block.
**Suggested Fix**: Move the import to the top-level imports of session.py, alongside other stdlib imports.
**Found by**: perf reviewer (Medium), readability reviewer (Low). Also noted by logic reviewer as part of ended_at timing finding.


