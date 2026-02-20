---
id: cs-5vvh
status: open
deps: []
links: []
created: 2026-02-20T05:06:53Z
type: chore
priority: 2
assignee: Michael Barrett
parent: cs-st02
---
# Migrate config migration to tomlkit

migrate_config() in project.py does raw string manipulation on TOML text (regex find/replace, insertion-point slicing). This is fragile and will get worse with each new migration step. Switch to tomlkit which preserves comments and formatting while giving proper TOML parsing. Would make future migrations straightforward and less error-prone.

