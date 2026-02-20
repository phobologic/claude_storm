---
id: cs-e8jb
status: open
deps: []
links: []
created: 2026-02-20T05:06:38Z
type: feature
priority: 2
assignee: Michael Barrett
parent: cs-o05c
---
# Content-aware memory search

search_memory() in memory.py only searches title, tags, and the one-line summary — not the actual note body. For sessions with many memories, agents miss notes whose titles don't mention the search terms but whose content does. Extend search to grep the .md file content as well.

