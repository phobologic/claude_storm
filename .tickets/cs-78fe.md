---
id: cs-78fe
status: closed
deps: []
links: []
created: 2026-02-22T00:24:48Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:readability]
---
# Test setup directly mutates private state (_stream_responding, _stream_label) instead of calling the public API

**File**: tests/test_textual_display.py
**Line(s)**: 113-114, 128-129, 143-144
**Description**: Multiple tests set display._stream_responding = False and display._stream_label = 'Agent A' directly rather than calling display.show_agent_stream_start() to establish that state. This pattern tightly couples tests to the internal field names, which means a refactor of those internals (e.g. renaming the fields or moving them into a dataclass) will silently break or require touching many test sites. It also means the tests do not exercise the real initialization path.
**Suggested Fix**: Call show_agent_stream_start(config, agent) in the test setup, then assert only on the behaviour of the method under test. If isolating the method is necessary, use a mock or a helper fixture rather than directly mutating private attributes.

