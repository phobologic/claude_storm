---
id: cs-bhsi
status: open
deps: []
links: []
created: 2026-02-22T00:24:24Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:perf]
---
# Repeated lazy imports inside hot streaming path allocate module lookup overhead per chunk

**File**: claude_storm/display.py
**Line(s)**: 630
**Description**: show_agent_stream_delta() is called once per streamed text chunk — potentially hundreds or thousands of times per agent turn. Each call executes `from claude_storm.messages import StreamDelta, UpdateThinkingLabel` as a lazy import inside the method body. Although Python caches module objects in sys.modules after the first import, the attribute lookup on the module object and the local name binding still occur on every single call to this method. For a method on the hot streaming path this is avoidable overhead.
**Suggested Fix**: Hoist the imports to module level (or to class level) for the message types used in the streaming hot path (StreamDelta, UpdateThinkingLabel). The lazy-import pattern is documented in CLAUDE.md as necessary only to avoid circular dependencies; verify whether these two message types actually create a cycle before keeping them lazy. If they do not, move them to the top of the file.

