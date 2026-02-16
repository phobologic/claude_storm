---
id: claude_storm-1lq.1
status: closed
deps: []
links: []
created: 2026-02-06T12:57:45.879609-08:00
type: bug
priority: 1
external-ref: HIGH-LOGIC-002
parent: claude_storm-1lq
---
# Fix silent OSError catch in _create_ref_symlinks

HIGH-LOGIC-002: config.py:201-202 — except OSError swallows all errors but prompt still references nonexistent symlink paths. Either fail fast (preferred) or track failures and fall back to raw paths in prompt. Also log the exception object.


