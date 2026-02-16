---
id: claude_storm-0mn.3
status: closed
deps: []
links: []
created: 2026-02-06T10:08:51.776286-08:00
type: task
priority: 2
parent: claude_storm-0mn
---
# Untrusted subprocess args from config

MEDIUM: agents.py:86-144. Values from SessionConfig (loaded from session.json on disk) injected into subprocess command-line args. reference_dirs validated at creation but not on session resume. A tampered session.json could grant Claude CLI read access to arbitrary filesystem paths. Fix: re-validate reference_dirs on session resume, add blocklist for sensitive system paths, validate model against known identifiers.


