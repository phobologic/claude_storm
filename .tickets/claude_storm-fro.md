---
id: claude_storm-fro
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:03:32.360175-08:00
type: task
priority: 2
---
# Harden stream reader robustness

MED-LOGIC-001 + MED-LOGIC-002 + MED-SEC-001: (1) Selector/readline buffering mismatch — sel.select() reports ready but readline() may block on partial lines. Document assumption or use raw reads. (2) _parse_stream_event silently swallows malformed JSON — add debug logging. (3) on_delta callback exceptions abort stream reader and leave process running — wrap in try/except. Files: agents.py:155-158, 206-214, 233-234


