"""Tests for InputBuffer."""

from claude_storm.input_buffer import InputBuffer


class TestInputBuffer:
    def test_drain_returns_none_when_empty(self):
        buf = InputBuffer()
        assert buf.drain() is None

    def test_drain_returns_joined_messages(self):
        buf = InputBuffer()
        # Manually push lines (bypassing the reader thread)
        buf._lines.append("focus on security")
        buf._lines.append("also consider performance")
        result = buf.drain()
        assert result == "focus on security\nalso consider performance"

    def test_drain_consumes_messages(self):
        buf = InputBuffer()
        buf._lines.append("first nudge")
        assert buf.drain() == "first nudge"
        assert buf.drain() is None

    def test_empty_and_whitespace_lines_ignored(self):
        """The reader loop strips and skips empty lines."""
        buf = InputBuffer()
        # Simulate what the reader loop does: only non-empty stripped lines
        for line in ["  ", "", "  hello  ", "\t"]:
            stripped = line.strip()
            if stripped:
                buf._lines.append(stripped)
        assert buf.drain() == "hello"

    def test_has_pending_false_when_empty(self):
        buf = InputBuffer()
        assert buf.has_pending() is False

    def test_has_pending_true_when_queued(self):
        buf = InputBuffer()
        buf._lines.append("nudge")
        assert buf.has_pending() is True

    def test_pending_count_zero(self):
        buf = InputBuffer()
        assert buf.pending_count == 0

    def test_pending_count_matches_lines(self):
        buf = InputBuffer()
        buf._lines.append("one")
        buf._lines.append("two")
        buf._lines.append("three")
        assert buf.pending_count == 3

    def test_pending_count_after_drain(self):
        buf = InputBuffer()
        buf._lines.append("nudge")
        buf.drain()
        assert buf.pending_count == 0
