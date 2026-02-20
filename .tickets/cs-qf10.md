---
id: cs-qf10
status: closed
deps: []
links: []
created: 2026-02-20T05:33:28Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-kmv6
---
# Clean up test_agents.py: extract mock helpers, add missing coverage

Three issues in test_agents.py:

1. REPEATED MOCK SETUP — Multiple test classes repeat identical selector + Popen mock setup (create MagicMock selector, set select.return_value = [(None, None)], patch _SEL_PATCH and _POPEN_PATCH). Appears in TestResponseSizeLimit, TestInvokeAgent, TestUsageExtraction, TestBrokenPipeError, TestUnparseableLine. Extract a shared fixture or module-level helper that patches both and yields mock objects. TestInvokeAgent._invoke_with_events is a good starting point — generalize and share it.

2. DUPLICATED _validate_reference_dir TESTS — TestValidateReferenceDir in test_agents.py (lines 24-40) duplicates tests from test_config.py's TestValidateReferenceDirConfig. Remove TestValidateReferenceDir from test_agents.py entirely (the function lives in config.py and should only be tested there).

3. MISSING COVERAGE — invoke_agent with session_id override (agents.py lines 331-335, the elif session_id is not None branch) has no test. Add a test to TestInvokeAgent verifying correct CLI args when session_id is passed without system_prompt.

Files touched: test_agents.py only

