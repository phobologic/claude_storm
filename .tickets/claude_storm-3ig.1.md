---
id: claude_storm-3ig.1
status: closed
deps: []
links: []
created: 2026-02-07T06:30:09.81572-08:00
type: bug
priority: 2
parent: claude_storm-3ig
---
# Add self-revision guard for pending proposals

MED-SEC-001 (3/4 reviewers): session.py:260-271 — No check that the revising agent differs from the original proposer. An agent can revise its own pending proposal, bypassing two-party negotiation. The prompt layer filters by proposed_by but the enforcement layer does not. Add a guard: if pending['proposed_by'] == agent, skip with a warning.


