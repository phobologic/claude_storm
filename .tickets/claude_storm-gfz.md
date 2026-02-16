---
id: claude_storm-gfz
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:03:19.396694-08:00
type: bug
priority: 1
---
# Add proc.wait() timeout and process lifecycle hardening

HIGH-PERF-002 + LOW-SEC-002 + LOW-LOGIC-001: (1) proc.wait() at agents.py:354 has no timeout — can block indefinitely. Add proc.wait(timeout=30) with fallback kill. (2) proc.kill() in _read_stream doesn't wait — zombie risk. (3) Daemon stderr thread join may timeout silently losing errors. File: agents.py:344-358


