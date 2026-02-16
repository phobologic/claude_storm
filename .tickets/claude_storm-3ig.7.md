---
id: claude_storm-3ig.7
status: closed
deps: []
links: []
created: 2026-02-07T06:30:22.596814-08:00
type: chore
priority: 4
parent: claude_storm-3ig
---
# Fix inconsistent REVISE placeholder text in proposal display

LOW-READ-003: agreements.py:351-353 — REVISE instruction uses bare words 'improved content' as placeholder while ACCEPT/REJECT use '"..."' style. Use consistent placeholder style: [REVISE id="..."]...revised content...[/REVISE].


