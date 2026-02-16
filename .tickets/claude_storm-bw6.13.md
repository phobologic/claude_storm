---
id: claude_storm-bw6.13
status: closed
deps: []
links: []
created: 2026-02-14T19:51:32.78463-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Missing comment on expected raw_response shape in debug.py usage summary

**File**: `/Users/mike/git/claude_storm/claude_storm/debug.py`
**Line(s)**: 74-83

**Description**: The debug usage summary references `raw_response["total_cost_usd"]` as a top-level key in the raw response dict, while `usage` is also a top-level key. However, there is no comment explaining the expected shape of this dict or where these keys come from (the Claude CLI result event). A brief comment documenting the expected structure would help future readers understand what fields are available and where they originate.

**Suggested Fix**: Add a brief inline comment:

```python
# Fields from Claude CLI result event: usage.input_tokens, usage.output_tokens,
# total_cost_usd (top-level), usage.iterations (when compaction occurs)
if "usage" in raw_response:
    ...
```



