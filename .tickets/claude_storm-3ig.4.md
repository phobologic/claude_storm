---
id: claude_storm-3ig.4
status: closed
deps: []
links: []
created: 2026-02-07T06:30:17.111102-08:00
type: bug
priority: 3
parent: claude_storm-3ig
---
# Validate REVISE body is non-empty

LOW-SEC-001: directives.py:189-192 — An empty [REVISE id="abc"][/REVISE] creates a proposal with empty content and removes the original pending proposal. Add body.strip() check alongside the existing id_ check.


