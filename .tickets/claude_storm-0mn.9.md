---
id: claude_storm-0mn.9
status: closed
deps: []
links: []
created: 2026-02-06T10:09:56.822674-08:00
type: task
priority: 3
parent: claude_storm-0mn
---
# Plaintext session data permissions

LOW: config.py:92-96. .storms/ directory created with default permissions. All session data stored in plaintext including conversations, memories, agreements, and session UUIDs. Fix: use chmod 700 on .storms/ upon creation, document data sensitivity.


