---
id: claude_storm-8aj
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:03:45.460304-08:00
type: task
priority: 2
---
# Document --verbose flag requirement for stream-json

MED-LOGIC-003 (3 reviewers): --verbose added unconditionally with no comment. Either gate behind config.debug, add comment explaining it is required for stream-json, or filter stderr before including in error messages. File: agents.py:306


