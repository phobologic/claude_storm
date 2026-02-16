---
id: claude_storm-2w5.1
status: closed
deps: []
links: []
created: 2026-02-07T06:47:27.415786-08:00
type: task
priority: 3
parent: claude_storm-2w5
---
# Extract config resolution from start() into a helper

Move the three-layer merge logic (defaults → TOML → CLI overrides) into a _resolve_start_config() helper that returns a SessionConfig. Leaves start() as a thin shell: parse args → resolve config → launch.


