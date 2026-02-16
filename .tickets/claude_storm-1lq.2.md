---
id: claude_storm-1lq.2
status: closed
deps: []
links: []
created: 2026-02-06T12:57:48.43571-08:00
type: task
priority: 2
external-ref: MED-LOGIC-001
parent: claude_storm-1lq
---
# Extract symlink path logic into shared SessionConfig method

MED-LOGIC-001: config.py:191-192 and prompts.py:168-171 both independently compute refs_dir/ref_N. Extract to a ref_symlink_paths property on SessionConfig to establish single source of truth.


