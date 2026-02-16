---
id: claude_storm-l6u
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:03:38.98068-08:00
type: bug
priority: 2
---
# Fix _active_process TOCTOU race condition

MED-SEC-002 (2 reviewers): After Popen created under _process_lock, line 336 reads proc=_active_process outside the lock. Move assignment inside the with block. File: agents.py:327-336


