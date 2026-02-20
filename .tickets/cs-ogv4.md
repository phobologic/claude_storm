---
id: cs-ogv4
status: closed
deps: []
links: []
created: 2026-02-20T05:34:05Z
type: task
priority: 1
assignee: Michael Barrett
parent: cs-kmv6
---
# Add test coverage for TextualDisplay

TextualDisplay (display.py lines 447-665, ~220 lines) has ZERO test coverage. test_app.py mocks out _session_worker so TextualDisplay methods are never called. test_display.py only tests PlainDisplay.

Key methods needing tests:
- prompt_user: uses threading.Event for ASK_USER flow — verify it posts PromptUserMessage and blocks until event is set
- show_agent_stream_start/delta/end: verify correct Message subclasses are posted
- thinking_status: verify it's a no-op or posts appropriate message
- show_turn_header: verify TurnHeaderMessage is posted
- show_error: verify ErrorMessage is posted

APPROACH: Unit test TextualDisplay methods by instantiating it with a mock app (or by capturing _post calls). Don't need a full Textual app running — just verify the right Messages are created/posted. For prompt_user, test the threading.Event lifecycle.

Create tests/test_textual_display.py (separate file to avoid conflating with PlainDisplay tests in test_display.py).

Files touched: test_textual_display.py (new)

