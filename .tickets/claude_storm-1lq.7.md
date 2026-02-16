---
id: claude_storm-1lq.7
status: closed
deps: []
links: []
created: 2026-02-06T12:58:16.84689-08:00
type: chore
priority: 4
external-ref: LOW-READ-003
parent: claude_storm-1lq
---
# Remove redundant mkdir calls in TestRefSymlinks

LOW-READ-003: test_config.py:270-339 — every test calls session_dir().mkdir() before ensure_dirs(), but ensure_dirs already creates parent dirs. Redundant boilerplate.


