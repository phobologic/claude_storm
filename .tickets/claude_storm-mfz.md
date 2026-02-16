---
id: claude_storm-mfz
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:04:12.491626-08:00
type: task
priority: 3
---
# Cap stderr accumulation size

LOW-SEC-001: _drain_stderr reads all stderr into memory with no size limit. Add a _MAX_STDERR_BYTES cap similar to _MAX_RESPONSE_BYTES. File: agents.py:252-264


