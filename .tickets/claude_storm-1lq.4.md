---
id: claude_storm-1lq.4
status: closed
deps: []
links: []
created: 2026-02-06T12:57:51.85228-08:00
type: task
priority: 2
external-ref: MED-SEC-001
parent: claude_storm-1lq
---
# Add sensitive-path validation in _create_ref_symlinks

MED-SEC-001: config.py:179-202 — _create_ref_symlinks does not call _validate_reference_dir before creating symlinks. Defense-in-depth gap if SessionConfig constructed from tampered session.json.


