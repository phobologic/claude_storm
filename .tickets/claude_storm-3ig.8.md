---
id: claude_storm-3ig.8
status: closed
deps: []
links: []
created: 2026-02-07T06:30:24.377982-08:00
type: chore
priority: 3
parent: claude_storm-3ig
---
# Add REVISE precedence test for confirmed vs pending coexistence

LOW-READ-004: tests/test_cli.py:820-897 — No test covers the case where both accepted_agreements and pending_proposals have entries and REVISE targets a pending-only ID. Add a test confirming the lookup order (confirmed first, then pending) to document intended precedence.


