---
id: claude_storm-3ig.5
status: closed
deps: []
links: []
created: 2026-02-07T06:30:19.025123-08:00
type: chore
priority: 3
parent: claude_storm-3ig
---
# Add proposed_by assertion to revision test

LOW-LOGIC-001: tests/test_cli.py:852-881 — test_revise_pending_proposal does not assert proposal['proposed_by'] == 'b'. Since format_agreements_for_prompt uses proposed_by for routing, this is a meaningful coverage gap. Add the assertion.


