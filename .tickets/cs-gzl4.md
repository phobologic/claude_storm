---
id: cs-gzl4
status: closed
deps: []
links: []
created: 2026-02-20T05:06:40Z
type: feature
priority: 2
assignee: Michael Barrett
parent: cs-o05c
---
# TUI streaming display

In TUI mode, StreamDelta messages accumulate in _stream_parts but only render on StreamEnd. The ThinkingBar covers the UX gap, but showing the response word-by-word as it streams would be a much better experience. Requires incremental rendering in StormApp.on_stream_delta() — likely writing to the RichLog progressively. Need to handle the Markdown rendering challenge (partial markdown is hard to render).

