---
id: claude_storm-0mn.7
status: closed
deps: []
links: []
created: 2026-02-06T10:09:55.735048-08:00
type: task
priority: 3
parent: claude_storm-0mn
---
# Memory filename sanitization

LOW: memory.py:31-35. _slugify() uses r'[^\w\s-]' regex which implicitly removes /, \, . -- reasonably safe but implicit rather than explicit. Fix: add an explicit path separator check on the final filename before using it in path construction.


