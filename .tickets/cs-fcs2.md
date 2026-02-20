---
id: cs-fcs2
status: open
deps: []
links: []
created: 2026-02-20T05:06:36Z
type: feature
priority: 2
assignee: Michael Barrett
parent: cs-o05c
---
# Configurable compilation model

Allow users to specify a different (e.g. stronger) model for the compilation phase vs brainstorming. Currently both phases share the same model from SessionConfig. Add a compilation_model field to storm.toml and SessionConfig, defaulting to the brainstorming model. Wire it through compile_deliverables() and generate_summary() in compilation.py.

