---
id: claude_storm-0mn.1
status: closed
deps: []
links: []
created: 2026-02-06T10:08:47.93757-08:00
type: task
priority: 1
parent: claude_storm-0mn
---
# Path traversal via artifact filenames

HIGH: session.py:207-210. Agent-controlled filenames in [ARTIFACT filename="..."] directives can write outside artifacts/ dir via ../ sequences. mkdir(parents=True) creates intermediate dirs, write_text writes outside intended directory. Fix: validate resolved path stays within artifacts/ dir using PurePosixPath(filename).name, reject if name differs from filename.


