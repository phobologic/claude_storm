---
id: cs-6zjv
status: closed
deps: []
links: [cs-2fqp]
created: 2026-02-23T02:37:23Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:readability]
---
# Inline 'from textual.widgets import Static' inside test methods is inconsistent with project import style

**File**: tests/test_app.py
**Line(s)**: 67, 78, 92
**Description**: Three new test methods each contain an inline 'from textual.widgets import Static' import. The rest of the test file (and the project's CLAUDE.md conventions) place all imports at the module top-level. The module already imports from 'textual' in other tests; Static should be added to the top-level imports alongside the existing 'from claude_storm.widgets import InputBar, SelectableRichLog' line.
**Suggested Fix**: Remove the three inline import statements and add 'from textual.widgets import Static' at the top of test_app.py, grouped with the other third-party imports.

