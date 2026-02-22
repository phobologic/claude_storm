---
id: cs-mb4l
status: open
deps: []
links: []
created: 2026-02-22T00:24:38Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:perf]
---
# update_label() calls refresh() unconditionally even when label is unchanged

**File**: claude_storm/widgets.py
**Line(s)**: 139-142
**Description**: ThinkingBar.update_label() sets self._label and immediately calls self.refresh() without checking whether the new label differs from the current one. Although update_label() is currently only called once per stream (when the first delta arrives), the method's contract does not prevent future callers from invoking it repeatedly with the same value. Each unnecessary refresh() schedules a widget repaint in Textual's render loop.
**Suggested Fix**: Add an early-return guard:
```python
def update_label(self, label: str) -> None:
    if label == self._label:
        return
    self._label = label
    self.refresh()
```
This is a cheap string comparison that avoids a render cycle when the value has not changed.

