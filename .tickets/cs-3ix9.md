---
id: cs-3ix9
status: closed
deps: []
links: []
created: 2026-02-23T02:37:43Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:logic]
---
# Bare except in on_growing_text_area_submitted silently ignores set_nudge_mode failure

**File**: claude_storm/app.py
**Line(s)**: 222-226
**Description**: The try/except Exception: pass in on_growing_text_area_submitted silently ignores errors from query_one(InputBar) and input_bar.set_nudge_mode(). If set_nudge_mode fails due to a real bug, the input bar will be stuck in ask mode with no indication, and the next user submission would be incorrectly routed as an ASK_USER response rather than a nudge.
**Suggested Fix**: Narrow the catch to NoMatches for the non-interactive path only.

