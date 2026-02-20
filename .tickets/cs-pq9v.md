---
id: cs-pq9v
status: closed
deps: []
links: []
created: 2026-02-20T05:33:55Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kmv6
---
# Remove duplicate format_duration tests from test_display.py and test_debug.py

format_duration (from config.py) is tested in THREE files:
- test_config.py lines 636-658: 7 tests (most thorough) — KEEP
- test_display.py lines 223-230: 3 tests (subset) — REMOVE
- test_debug.py lines 351-363: 4 tests (subset) — REMOVE

FIX: Delete TestFormatDuration class from test_display.py and test_debug.py. The function lives in config.py so test_config.py is the canonical location.

Verify no unique edge cases exist in the removed copies before deleting. If any test case from display/debug is not covered by config, add it to test_config.py's TestFormatDuration first.

Files touched: test_display.py, test_debug.py

