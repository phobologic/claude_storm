---
id: claude_storm-3ig.2
status: closed
deps: []
links: []
created: 2026-02-07T06:30:12.629087-08:00
type: bug
priority: 2
parent: claude_storm-3ig
---
# Log warning for unknown REVISE target IDs

MED-LOGIC-001 (2/4 reviewers): session.py:273-276 — REVISE targeting a nonexistent ID silently creates an orphaned proposal with a dangling revises reference and generic title. Add a display.show_warning() call before the fallback to help diagnose LLM hallucinations or stale references.


