---
id: cs-f3ir
status: closed
deps: []
links: []
created: 2026-02-20T05:06:50Z
type: task
priority: 1
assignee: Michael Barrett
parent: cs-st02
---
# Integration test for run_session()

The core turn loop in session.py has no dedicated test. Everything around it is well-tested (directives, agreements, check_stop, merge_user_input), but run_session() itself — the most critical ~200 lines — isn't exercised end-to-end with mocked agents. Write an integration test that mocks invoke_agent() and verifies the full loop: turn alternation, directive processing, watermark updates, stop conditions, compilation trigger.

