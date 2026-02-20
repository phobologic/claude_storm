---
id: cs-f9vd
status: closed
deps: []
links: []
created: 2026-02-20T05:33:16Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-kmv6
---
# Add shared test helpers to conftest.py

Add reusable helpers to tests/conftest.py to reduce boilerplate across test files:

1. Move _make_response from test_session.py (lines 11-29) into conftest.py as a module-level helper or fixture. It constructs AgentResponse objects with sensible defaults. Currently test_cli.py and test_compilation.py construct AgentResponse inline — they should use this helper instead.

2. Add _make_agreement and _make_proposal factory helpers:
   def _make_agreement(id='a3f2', title='Use REST', content='REST API.', proposed_by='a', proposed_turn=4, accepted_turn=5, revises=None, summary=None): ...
   def _make_proposal(id='c4e8', title='Add GraphQL', content='Add gateway.', proposed_by='a', turn=9, revises=None, summary=None): ...

These are used extensively in test_agreements.py and test_cli.py (dozens of inline dict constructions).

3. Run tests to verify nothing breaks.

Files touched: conftest.py only (consumers adopt in their own tickets)

