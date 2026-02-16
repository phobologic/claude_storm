---
id: claude_storm-ccf
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:03:05.493961-08:00
type: bug
priority: 1
---
# Handle BrokenPipeError on proc.stdin.write

HIGH-LOGIC-001 + MED-LOGIC-004: If the subprocess exits immediately (missing binary, bad args), proc.stdin.write(prompt) raises unhandled BrokenPipeError. Wrap in try/except OSError. Also add a test case for this edge case. File: agents.py:339-340


