---
id: claude_storm-bw6.8
status: closed
deps: []
links: []
created: 2026-02-14T19:51:22.240436-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Inconsistent None check for usage dict in update_watermark

**File**: /Users/mike/git/claude_storm/claude_storm/config.py
**Line(s)**: 369
**Description**: The check `if usage:` uses truthiness to guard token accumulation. This means a usage dict like `{"input_tokens": 0, "output_tokens": 0}` (which is truthy) would be processed fine, but an empty dict `{}` would be skipped silently. More importantly, this is inconsistent with `cost_usd` which uses `if cost_usd is not None:` (explicit None check).

While unlikely to cause a bug in practice (the CLI should always include token counts when it includes usage), the inconsistency could mask a future issue if usage is passed as `{}`.

**Suggested Fix**: Use `if usage is not None:` for consistency with the `cost_usd` guard.

```python
# Current
if usage:
    wm["total_input_tokens"] += usage.get("input_tokens", 0)

# Suggested
if usage is not None:
    wm["total_input_tokens"] += usage.get("input_tokens", 0)
```



