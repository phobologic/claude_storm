---
id: cs-dqkj
status: closed
deps: []
links: []
created: 2026-02-20T05:06:52Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-st02
---
# Turn prompt size guard

truncate_conversation only applies to compilation/summary prompts. Per-turn prompts have no size guard — a very long agent response gets passed as other_response into the next turn prompt with no limit. Add a truncation strategy for other_response in build_turn_prompt() to prevent context blowout on long sessions.

