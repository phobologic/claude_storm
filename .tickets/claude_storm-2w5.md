---
id: claude_storm-2w5
status: closed
deps: []
links: []
created: 2026-02-07T06:47:23.200351-08:00
type: epic
priority: 3
---
# Refactor cli.py start() command

cli.py:start() is ~175 lines handling CLI options, three-layer config merging, TOML migration, path validation, and session launching. Break it into focused helpers.


