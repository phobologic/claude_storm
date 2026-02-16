---
id: claude_storm-csb.11
status: closed
deps: []
links: []
created: 2026-02-14T14:24:31.958836-08:00
type: task
priority: 3
parent: claude_storm-csb
---
# Inline imports and duplicated assertions in revision context tests

**File**: `/Users/mike/git/claude_storm/tests/test_agreements.py`
**Line(s)**: 906-926, 928-947
**Description**: The two test methods `test_revision_of_accepted_agreement_preserves_content` and `test_revision_of_pending_proposal_preserves_content` both import `MagicMock` and `_resolve_revision_context` inline (lines 915-917 and 934-936). These imports should be at the top of the file or at minimum at the class level, consistent with the rest of the test file which imports test dependencies at the module level.

Additionally, both tests share nearly identical assertion blocks (lines 921-926 and 940-945) checking the same four tuple fields. A small helper or parametrized approach would reduce repetition.

**Suggested Fix**: Move the imports to the top of the file alongside other test imports. Consider a shared assertion helper within the test class:

```python
def _assert_revision_context(self, ctx, title, content, turn, agent):
    assert ctx is not None
    t, oc, ot, oa = ctx
    assert t == title
    assert oc == content
    assert ot == turn
    assert oa == agent
```



