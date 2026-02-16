---
id: claude_storm-4m2
status: closed
deps: [claude_storm-9vd]
links: []
created: 2026-02-06T11:38:04.085993-08:00
type: task
priority: 3
---
# Wire streaming callbacks through session.py and compilation.py

Update _run_turn() in session.py and compile_deliverables()/generate_summary() in compilation.py to pass an on_delta callback to invoke_agent(). The callback should call display.show_agent_stream_delta(). Replace the thinking_status context manager with show_agent_stream_start/end bracketing. Ensure the full response text is still available for directive parsing, conversation logging, and debug output after the stream completes.


