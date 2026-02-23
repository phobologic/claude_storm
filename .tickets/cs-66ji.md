---
id: cs-66ji
status: closed
deps: []
links: []
created: 2026-02-23T02:37:32Z
type: task
priority: 1
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# Bare except in on_request_user_input silently swallows all exceptions from InputBar query

**File**: claude_storm/app.py
**Line(s)**: 180-190
**Description**: The except Exception block in on_request_user_input is intended to handle the non-interactive case (no InputBar mounted), but it catches all exceptions including genuine errors like AttributeError or query failures unrelated to the widget being absent. A real bug in InputBar or GrowingTextArea would be silently swallowed and the session would be unblocked with an empty response, producing silent incorrect behavior instead of a surfaced error. This is an overly defensive pattern that masks real problems.
**Suggested Fix**: Use the specific Textual exception for missing widgets (NoMatches from textual.css.query) rather than bare Exception. Only catch the case where the widget genuinely does not exist.

