---
id: claude_storm-1lq.3
status: closed
deps: [claude_storm-1lq.1]
links: []
created: 2026-02-06T12:57:50.362754-08:00
type: bug
priority: 2
external-ref: MED-LOGIC-002
parent: claude_storm-1lq
---
# Add symlink existence check in _build_reference_section

MED-LOGIC-002: prompts.py:168-174 — constructs symlink paths without verifying they exist. If symlink creation failed, prompt directs agents to nonexistent paths. Fall back to raw path if symlink missing.


