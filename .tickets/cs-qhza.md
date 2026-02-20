---
id: cs-qhza
status: closed
deps: []
links: []
created: 2026-02-20T05:33:48Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-kmv6
---
# Reduce brittle prompt assertions in test_prompts.py

Several tests assert on exact English phrases from prompt text, making them brittle to copywriting changes:

- test_revise_anti_amendment_guideline (line 91): asserts 'rather than accepting and then proposing', 'separate amendments'
- test_includes_agreement_guidelines (line 99): asserts 4 specific phrases like 'verbal agreement', 'does NOT create a shared record'
- test_revise_mentions_pending_proposals (line 85): asserts exact wording

FIX: Refocus assertions on structural requirements:
- Verify sections exist (REVISE section present, agreement guidelines section present)
- Verify variable data is interpolated correctly (topic, role, goal, deliverables) 
- For instructional copy, assert section presence rather than exact phrases
- Keep assertions on dynamic content (agreement titles, proposal IDs, role names)
- Consider consolidating multiple 'right content appears' tests into fewer structural tests

Do NOT remove the tests for variable interpolation — those are valuable. Only relax the assertions on static prose.

Files touched: test_prompts.py only

