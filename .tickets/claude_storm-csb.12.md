---
id: claude_storm-csb.12
status: closed
deps: []
links: []
created: 2026-02-14T14:24:32.552015-08:00
type: task
priority: 3
parent: claude_storm-csb
---
# REVISE directive instructions could clarify 'original is kept as context'

**File**: `/Users/mike/git/claude_storm/claude_storm/prompts.py`
**Line(s)**: 99-105
**Description**: The updated REVISE instruction says 'the original is kept as context but the agreement is easier to use when the revision is self-contained.' This is slightly ambiguous -- it could be read as 'the original is kept somewhere else as context for you' (implying the agent should not include it) or 'the original is preserved in the record.' Since the intent is to instruct agents to write complete revised text, consider being more explicit about what 'kept as context' means.

**Suggested Fix**: Rephrase to something like: 'Include the COMPLETE revised text, not just your changes. The system stores the original for comparison, but the revision should stand on its own as the current version of the agreement.'


