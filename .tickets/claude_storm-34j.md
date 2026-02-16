---
id: claude_storm-34j
status: closed
deps: [claude_storm-9vd]
links: []
created: 2026-02-06T11:37:55.790496-08:00
type: task
priority: 3
---
# Implement idle-timeout semantics for streaming

With streaming, the timeout should reset on each received chunk (idle timeout) rather than being a total wall-clock limit. If no output is received within the timeout window, kill the process and return a timed_out AgentResponse. This prevents killing agents that are actively producing output on long turns. Consider using select/poll on the stdout pipe with a per-iteration timeout, or a watchdog thread that resets on each line read.


