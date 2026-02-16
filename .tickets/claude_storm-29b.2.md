---
id: claude_storm-29b.2
status: closed
deps: []
links: []
created: 2026-02-14T21:28:55.923157-08:00
type: task
priority: 2
parent: claude_storm-29b
---
# Duplicated _format_duration function in debug.py and display.py

**Files**: debug.py (lines 151-157) and display.py (lines 25-37)
**Description**: _format_duration() is defined identically in both debug.py and display.py, violating DRY. cli.py imports from display.py while debug.py uses its own copy. Future format changes must be applied in two places, and tests are also duplicated across test_debug.py and test_display.py.
**Suggested Fix**: Move the function into a shared leaf module (e.g., config.py) and import from there in both modules. debug.py is a leaf module with no local imports, so importing from display.py would change the dependency hierarchy.
**Found by**: All 3 reviewers (logic: Medium, perf: Low, readability: Medium)


