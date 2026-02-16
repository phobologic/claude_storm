---
id: claude_storm-0mn.2
status: closed
deps: []
links: []
created: 2026-02-06T10:08:49.969671-08:00
type: task
priority: 2
parent: claude_storm-0mn
---
# Indirect prompt injection via agent strings

MEDIUM: prompts.py:284-293. Agent-supplied DONE reasons and response text interpolated into turn prompts without sanitization. A prompt-injected agent could craft a DONE reason containing instructions that override the system prompt. Also affects agreements.py:336-351 where proposal content is re-injected. Fix: truncate reason strings to 200 chars, strip directive-like patterns before embedding in prompts.


