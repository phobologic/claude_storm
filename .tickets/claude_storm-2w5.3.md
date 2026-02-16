---
id: claude_storm-2w5.3
status: closed
deps: []
links: []
created: 2026-02-07T06:47:29.566313-08:00
type: task
priority: 3
parent: claude_storm-2w5
---
# Move reference dir validation closer to SessionConfig

Reference dir existence checks are domain validation, not a CLI concern. Move into SessionConfig.create() or a validation step there.


