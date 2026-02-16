---
id: claude_storm-bw6.4
status: open
deps: []
links: []
created: 2026-02-14T19:51:16.141947-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Minor: redundant event-is-not-None check in stream hot loop

**File**: /Users/mike/git/claude_storm/claude_storm/agents.py
**Line(s)**: 236-243
**Description**: The compaction detection block runs on every stream event in the `_read_stream` hot loop. It performs 4 chained `.get()` calls and dictionary lookups for every event, even though compaction events are extremely rare (at most once per session). Since `event` is already checked for `None` and for `type == "result"` just above, adding a second full conditional chain increases the per-event overhead slightly.

**Suggested Fix**: Short-circuit early by checking `event.get("type") == "stream_event"` first (cheapest check), and consider combining with the existing `event is not None` guard above using an `elif`:

```python
# Current: two separate if-blocks, both check event is not None
if event is not None and event.get("type") == "result":
    result_event = event

# Detect compaction events
if (
    event is not None
    and event.get("type") == "stream_event"
    ...
):

# Suggested: use elif to skip compaction check when event is a result
if event is not None and event.get("type") == "result":
    result_event = event
elif event is not None and event.get("type") == "stream_event":
    inner = event.get("event", {})
    if inner.get("type") == "content_block_delta":
        delta_obj = inner.get("delta", {})
        if delta_obj.get("type") == "compaction_delta":
            compaction_summary = delta_obj.get("summary", delta_obj.get("text", ""))
```

This avoids the redundant `event is not None` check and skips the compaction detection entirely for result events.



