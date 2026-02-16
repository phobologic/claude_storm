---
id: claude_storm-29b.3
status: closed
deps: []
links: []
created: 2026-02-14T21:29:02.818607-08:00
type: task
priority: 2
parent: claude_storm-29b
---
# Duplicated watermark aggregation logic in debug.py and display.py

**Files**: debug.py (lines 188-209) and display.py (lines 49-56)
**Description**: The watermark aggregation logic (iterating over agents "a"/"b", summing total_cost_usd, total_input_tokens, total_output_tokens) is duplicated between write_debug_summary and _format_session_totals. Both are called in the same session lifecycle, re-fetching and re-summing the same watermark data. If the watermark schema changes, both locations must be updated.
**Suggested Fix**: Extract a shared helper (e.g., aggregate_watermarks(config) -> WatermarkTotals) in config.py that returns aggregated totals. Both debug.py and display.py consume the pre-computed result.
**Found by**: All 3 reviewers (logic: Medium, perf: Low, readability: Medium)


