---
id: claude_storm-r2f.1
status: closed
deps: []
links: []
created: 2026-02-07T06:30:27.202575-08:00
type: chore
priority: 3
parent: claude_storm-r2f
---
# Remove dead StreamStart.label and .color fields

MED-READ-002 (2/4 reviewers): app.py:124-126, display.py:449-452 — After Rule removal in commit 33cd87f, TextualDisplay still computes and posts label/color via StreamStart message but on_stream_start no longer uses them. Remove the dead fields from the StreamStart message class and stop computing them.


