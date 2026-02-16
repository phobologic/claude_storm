---
id: claude_storm-0mn.6
status: closed
deps: []
links: []
created: 2026-02-06T10:09:55.194548-08:00
type: task
priority: 2
parent: claude_storm-0mn
---
# Unvalidated JSON deserialization from disk

MEDIUM: config.py:111,135 and memory.py:20,95-97. SessionConfig.load() passes all keys from session.json directly to cls(**data). Tampered file could set reference_dirs to sensitive paths. In memory.py, _index.json filenames used in path construction without validation -- tampered index could enable path traversal. Fix: validate deserialized fields, check filenames for path separators.


