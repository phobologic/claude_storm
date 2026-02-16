---
id: claude_storm-9t7
status: closed
deps: [claude_storm-x5v]
links: []
created: 2026-02-06T12:03:25.584832-08:00
type: task
priority: 1
---
# Use proper message types in TUI stream handlers

HIGH-READ-001 (3 reviewers): on_stream_start/delta/end handlers in app.py use object type with type:ignore. Import StreamStart/StreamDelta/StreamEnd and use as proper type annotations. File: app.py:116-130


