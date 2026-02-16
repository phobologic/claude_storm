---
id: claude_storm-bw6.3
status: open
deps: []
links: []
created: 2026-02-14T19:51:13.643302-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Fragile nested dict access in compaction event parsing

**File**: /Users/mike/git/claude_storm/claude_storm/agents.py
**Line(s)**: 236-243
**Description**: The compaction event detection uses a chain of `.get()` calls on untrusted data from the subprocess JSON stream. While the subprocess is the Claude CLI (a controlled dependency), if the stream ever emits malformed events where `event["event"]` is not a dict (e.g., a string or list), line 240 would raise an `AttributeError` since `.get()` is only available on dicts. The current code already handles `event.get("event", {})` safely but then accesses `event["event"]` directly on line 242 without the same fallback, creating an inconsistency. If the outer condition passes (line 240 succeeds), line 242 will also succeed, so this is not exploitable -- but it reflects a fragile parsing pattern.

**Suggested Fix**: Consider extracting the nested dict once and reusing it, or wrapping the compaction detection block in a try/except for `(KeyError, TypeError, AttributeError)` to be defensive against unexpected stream event shapes. This is consistent with how `on_delta` failures are already caught on line 228.

```python
# Current code
if (
    event is not None
    and event.get("type") == "stream_event"
    and event.get("event", {}).get("type") == "content_block_delta"
    and event["event"].get("delta", {}).get("type") == "compaction_delta"
):
    delta_obj = event["event"]["delta"]
    compaction_summary = delta_obj.get("summary", delta_obj.get("text", ""))

# Suggested: extract once, defensive
try:
    inner = event.get("event", {}) if event else {}
    delta_obj = inner.get("delta", {})
    if (
        event is not None
        and event.get("type") == "stream_event"
        and inner.get("type") == "content_block_delta"
        and delta_obj.get("type") == "compaction_delta"
    ):
        compaction_summary = delta_obj.get("summary", delta_obj.get("text", ""))
except (KeyError, TypeError, AttributeError):
    pass
```



