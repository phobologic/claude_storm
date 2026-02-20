---
id: cs-kmv6
status: open
deps: []
links: []
created: 2026-02-20T05:32:40Z
type: epic
priority: 2
assignee: Michael Barrett
---
# Testing Anti-Patterns Cleanup

Audit found 14 anti-patterns across the test suite: duplicated tests, monolith test files, excessive mock boilerplate, missing coverage, brittle prompt assertions, and lack of shared test helpers. Split into per-file tickets for parallel agent execution. Phase 1 (blocking): split test_cli.py and add shared conftest helpers. Phase 2 (parallel): per-file cleanups.

