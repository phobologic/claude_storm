---
id: claude_storm-bw6.10
status: open
deps: []
links: []
created: 2026-02-14T19:51:25.054423-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Multiple compaction events per turn silently overwritten

**File**: /Users/mike/git/claude_storm/claude_storm/agents.py
**Line(s)**: 231-241
**Description**: If multiple `compaction_delta` events arrive in a single stream (which could happen if the CLI compacts multiple times during a long agentic turn), only the last compaction summary is retained because `compaction_summary` is overwritten unconditionally on each match.

This may be intentional (only the final compaction state matters), but it is worth noting that intermediate compaction summaries are silently lost. If compaction happens multiple times, the count tracked in `config.update_watermark(compacted=True)` will also only increment by 1, since `compaction_summary is not None` is a single boolean check.

**Suggested Fix**: If multiple compactions per turn should be tracked, accumulate into a list or concatenate summaries. If only the last matters, add a brief comment documenting the intent.

```python
# If intentional, document:
# NOTE: Multiple compaction events are possible; we keep only the latest summary.
compaction_summary = delta_obj.get("summary", delta_obj.get("text", ""))
```



