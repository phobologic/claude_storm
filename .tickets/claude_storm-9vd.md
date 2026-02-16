---
id: claude_storm-9vd
status: closed
deps: []
links: []
created: 2026-02-06T11:37:24.264418-08:00
type: feature
priority: 3
---
# Epic: Switch agent IPC to stream-json for incremental output

## Overview

Currently invoke_agent() uses subprocess.communicate() with --output-format json,
which blocks until the entire Claude CLI process exits before returning any output.
This means long agent turns show no progress beyond a spinner/timer.

Switching to --output-format stream-json would allow incremental output: the CLI
emits newline-delimited JSON events as the model generates tokens. This enables
real-time streaming of agent responses in both the plain display and TUI.

## Goals

- Show agent output as it streams (token-by-token or chunk-by-chunk)
- Reduce perceived latency — users see progress immediately
- Maintain the same AgentResponse contract after the stream completes
- Keep timeout behavior (kill process if no output within timeout window)

## Key Design Decisions

1. **Stream format**: Claude CLI with --output-format stream-json emits NDJSON
   (one JSON object per line). Events include content_block_delta (text chunks),
   message_start, message_stop, etc.

2. **Reader architecture**: Replace communicate() with a line-by-line reader on
   stdout. A background thread or select-based loop reads lines, parses JSON,
   and dispatches text deltas to the display layer.

3. **Display protocol changes**: DisplayProtocol needs new methods for streaming:
   - show_agent_stream_start(config, agent) — begin a streaming response block
   - show_agent_stream_delta(text) — append incremental text
   - show_agent_stream_end() — finalize the response block
   PlainDisplay can print deltas directly. TextualDisplay updates a RichLog widget.

4. **Timeout semantics**: With streaming, "timeout" should mean "no new output
   within N seconds" (idle timeout) rather than "total wall clock". This prevents
   killing agents that are actively producing output but taking a long time.

5. **AgentResponse assembly**: Accumulate all text deltas into the final
   AgentResponse.text so downstream directive parsing and conversation logging
   remain unchanged.

6. **Thread safety**: The existing _process_lock / _active_process pattern stays.
   The stream reader must be interruptible via process.terminate().

## Non-Goals

- Changing the directive parsing model (still runs on complete response)
- Streaming artifacts mid-generation (artifacts are written as complete files)

## Risks

- stream-json format may vary across Claude CLI versions; need to pin or handle
  gracefully
- TUI widget updates from a worker thread need careful message passing (already
  the pattern in app.py)


