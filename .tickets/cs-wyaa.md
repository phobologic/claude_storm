---
id: cs-wyaa
status: closed
deps: []
links: []
created: 2026-02-20T05:33:07Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-kmv6
---
# Split test_cli.py into module-aligned test files

test_cli.py is a 1319-line monolith testing 7+ modules. Split it:

1. Create tests/test_directives.py — move TestParseDirectives (lines 26-207), TestParseAttrs, TestRemoveSpans from test_cli.py. These test functions from directives.py.

2. Move to tests/test_session.py — move TestCheckStop (lines 252-281), TestMergeUserInput, TestProcessDirectivesRevisions, TestProcessDirectivesAskUser, TestConsensus, TestDraftPrefixBasename. These test functions from session.py.

3. Merge into tests/test_compilation.py — move TestCompileDeliverables (lines 873-983), TestCompileDeliverablesDebug, TestFindMatchingArtifacts (lines 1083-1115). Deduplicate TestFindMatchingArtifacts with existing version in test_compilation.py (keep more thorough version, add any unique cases from test_cli.py).

4. Move TestStopReason into tests/test_config.py.

5. Keep only CLI-specific tests in test_cli.py: TestCLICommands, TestLoadAndMigrateToml, TestResolveStartConfig.

6. Run full test suite to verify nothing breaks.

Files touched: test_cli.py, test_directives.py (new), test_session.py, test_compilation.py, test_config.py

