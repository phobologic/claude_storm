---
id: claude_storm-bw6.15
status: open
deps: []
links: []
created: 2026-02-14T19:51:35.171572-08:00
type: task
priority: 3
parent: claude_storm-bw6
---
# Per-turn token counts hidden behind debug flag while cumulative totals always shown

**File**: /Users/mike/git/claude_storm/claude_storm/session.py
**Line(s)**: 180-183
**Description**: Token usage details (`In: X Out: Y`) are only shown to the user when `config.debug` is True, since `usage=response.usage if config.debug else None` is passed to `show_turn_stats`. The cost and duration are always shown, but the token breakdown requires debug mode.

This is a design choice, not a bug, but it may surprise users who want to see token counts without enabling full debug mode. The cumulative totals in `show_completion` always show tokens regardless of debug mode, creating an inconsistency -- you see totals at the end but not per-turn breakdowns unless debug is on.

**Suggested Fix**: Consider always showing token counts in `show_turn_stats`, or add a separate verbosity flag. Alternatively, document that per-turn token details require `--debug`.



