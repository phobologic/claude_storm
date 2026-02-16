---
id: claude_storm-0mn.4
status: closed
deps: []
links: []
created: 2026-02-06T10:09:54.103252-08:00
type: task
priority: 2
parent: claude_storm-0mn
---
# Session ID path traversal

MEDIUM: config.py:85-90, 98-111. SessionConfig.load() accepts session_id from CLI input and uses it directly in path construction: Path(storms_dir) / session_id / 'session.json'. A session_id containing ../ could read files from arbitrary directories. Fix: validate format with re.match(r'^[a-zA-Z0-9_-]+$', session_id).


