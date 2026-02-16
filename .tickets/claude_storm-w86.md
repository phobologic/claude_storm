---
id: claude_storm-w86
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:03:58.809486-08:00
type: task
priority: 2
---
# Use NamedTuple for _read_stream return type

MED-READ-001: _read_stream returns bare 4-tuple (str, dict|None, bool, bool) where two positional booleans must be remembered. Define a _StreamResult NamedTuple. File: agents.py:177-249


