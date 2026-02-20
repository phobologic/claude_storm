---
id: cs-pbbw
status: open
deps: []
links: []
created: 2026-02-20T05:06:41Z
type: feature
priority: 3
assignee: Michael Barrett
parent: cs-o05c
---
# Multi-agent topologies

The current architecture is hardcoded for two agents (a/b) with strict alternation. Explore generalizing to N agents with different interaction topologies: round-robin, moderator+panel, directed graph. This is a big architectural lift — touches session.py turn loop, config, prompts, display, agreements. Scope and design before implementing.

