---
id: claude_storm-3ig.3
status: closed
deps: []
links: []
created: 2026-02-07T06:30:15.250631-08:00
type: chore
priority: 3
parent: claude_storm-3ig
---
# Extract helper for revision title resolution

MED-READ-001: session.py:246-276 — The three-branch revision cascade (confirmed, pending, unknown) repeats create_proposal + display.show_revision_proposed three times. Extract a _resolve_revision_title() helper that looks up the title and handles pending removal, then call create_proposal and display once.


