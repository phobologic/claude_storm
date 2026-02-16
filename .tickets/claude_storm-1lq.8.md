---
id: claude_storm-1lq.8
status: closed
deps: []
links: []
created: 2026-02-06T12:58:19.619611-08:00
type: chore
priority: 4
external-ref: LOW-READ-004
parent: claude_storm-1lq
---
# Show last 2 path components in reference section Actual Directory column

LOW-READ-004: prompts.py:173 — Path(raw_path).name shows only leaf name. If two ref dirs share leaf name (e.g. /a/docs and /b/docs), they are indistinguishable. Show last 2 components.


