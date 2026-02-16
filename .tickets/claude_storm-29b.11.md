---
id: claude_storm-29b.11
status: closed
deps: []
links: []
created: 2026-02-14T21:30:01.834061-08:00
type: task
priority: 3
parent: claude_storm-29b
---
# Prompt size annotation grammar: "1 lines" instead of "1 line"

**File**: debug.py (lines 54-55, 59-60)
**Description**: The prompt size annotations use {sp_lines:,} lines and {tp_lines:,} lines which produces "1 lines" when there is a single line. The test at test_debug.py:118 also asserts "1 lines", confirming the grammar issue is baked into both code and tests.
**Suggested Fix**: Use a conditional plural: f"{sp_lines:,} {'line' if sp_lines == 1 else 'lines'}" or accept the minor inconsistency.
**Found by**: readability reviewer (Low)


