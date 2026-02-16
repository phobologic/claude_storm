---
id: claude_storm-0mn.5
status: closed
deps: []
links: []
created: 2026-02-06T10:09:54.665558-08:00
type: task
priority: 2
parent: claude_storm-0mn
---
# Debug log exposure

MEDIUM: debug.py:9-71. Full CLI commands (including --system-prompt content and --session-id UUIDs) and raw JSON responses written to plaintext log file with default filesystem permissions (typically 0644). If .storms/ is shared, session identifiers and prompt/response content could be exposed. Fix: use os.open(..., 0o600) for restrictive permissions, add .gitignore entry for .storms/.


