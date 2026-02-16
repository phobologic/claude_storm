---
id: claude_storm-0mn.8
status: closed
deps: []
links: []
created: 2026-02-06T10:09:56.315226-08:00
type: task
priority: 3
parent: claude_storm-0mn
---
# No response size limits on agent output

LOW: agents.py:145-184. communicate() reads entire stdout into memory with no size limit. A runaway or adversarial agent response could exhaust memory. Fix: add a maximum response size limit to the stdout read.


