---
id: claude_storm-1lq.5
status: closed
deps: []
links: []
created: 2026-02-06T12:58:04.420427-08:00
type: task
priority: 3
external-ref: LOW-LOGIC-001
parent: claude_storm-1lq
---
# Clean up stale ref symlinks when reference_dirs list shrinks

LOW-LOGIC-001: config.py:179-202 — _create_ref_symlinks never removes old symlinks. If session resumes with fewer dirs, stale ref_N symlinks remain. Scan and remove after creation loop.


