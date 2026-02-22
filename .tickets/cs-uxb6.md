---
id: cs-uxb6
status: open
deps: []
links: []
created: 2026-02-22T00:24:34Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kt8x
tags: [code-review, reviewer:readability]
---
# ThinkingBar.render() appends '...' regardless of phase, now inconsistent with label content

**File**: claude_storm/widgets.py
**Line(s)**: 108
**Description**: ThinkingBar.render() always appends '...' to the label: f'  [bold]{self._label}... ({elapsed}s / {self._timeout}s)[/bold]'. Now that the label itself already ends with a verb phrase ('Agent A is responding'), the rendered output becomes 'Agent A is responding... (5s / 300s)' — the ellipsis is semantically odd when the agent is actively responding. The widget has no awareness of which phase it is in; this is a readability / UX consistency issue introduced by the label-update approach.
**Suggested Fix**: Either strip the hardcoded '...' from render() and let the caller include it in the label when appropriate, or give ThinkingBar a concept of phase (thinking vs responding) so it can choose its own punctuation. The former is simpler and keeps the widget dumb.

