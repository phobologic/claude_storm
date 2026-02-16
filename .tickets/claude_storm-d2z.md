---
id: claude_storm-d2z
status: closed
deps: [claude_storm-9vd]
links: []
created: 2026-02-06T11:38:07.830345-08:00
type: task
priority: 3
---
# Add tests for stream-json parsing and idle timeout

Test the NDJSON stream reader with mock subprocess output: normal completion (multiple content_block_delta events), error events, idle timeout (no output within window), process killed mid-stream, and oversized responses. Test that on_delta callback is invoked for each text chunk. Test that the final AgentResponse.text matches the concatenation of all deltas. Test idle timeout resets on each chunk. Use unittest.mock.patch + MagicMock following existing test patterns.


