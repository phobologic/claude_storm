---
id: claude_storm-1lq.6
status: closed
deps: []
links: []
created: 2026-02-06T12:58:14.555479-08:00
type: task
priority: 3
external-ref: LOW-SEC-001
parent: claude_storm-1lq
---
# Verify symlink target exists before creation in _create_ref_symlinks

LOW-SEC-001: config.py:191-200 — no target.is_dir() check before symlink_to. On resume after dir deleted, creates dangling symlinks. Add existence check and log warning.


