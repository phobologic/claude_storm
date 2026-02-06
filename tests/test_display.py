"""Tests for display formatting."""

import re
from io import StringIO

from claude_storm.display import PlainDisplay, DisplayProtocol, _truncate_label

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(buf: StringIO) -> str:
    """Strip ANSI escape sequences from buffer output."""
    return _ANSI_RE.sub("", buf.getvalue())


class TestDisplay:
    def test_show_header(self, make_config, capture_display):
        display, buf = capture_display
        config = make_config(ensure_dirs=False)
        display.show_header(config)
        output = buf.getvalue()
        assert "Claude Storm" in output
        assert "Test topic" in output
        assert "Architect" in output
        assert "Critic" in output

    def test_show_turn_start(self, make_config, capture_display):
        display, buf = capture_display
        config = make_config(ensure_dirs=False)
        display.show_turn_start(config, "a")
        output = _plain(buf)
        assert "Turn 1/10" in output
        assert "Architect" in output
        assert "·" in output

    def test_show_agent_response(self, make_config, capture_display):
        display, buf = capture_display
        config = make_config(ensure_dirs=False)
        display.show_agent_response(config, "a", "Here is my analysis")
        output = buf.getvalue()
        assert "Architect" in output
        assert "Here is my analysis" in output

    def test_show_status(self, capture_display):
        display, buf = capture_display
        display.show_status("Processing...")
        assert "Processing..." in _plain(buf)

    def test_show_error(self, capture_display):
        display, buf = capture_display
        display.show_error("Something failed")
        assert "Something failed" in buf.getvalue()

    def test_show_memory_save(self, capture_display):
        display, buf = capture_display
        display.show_memory_save("a", "API Design Notes")
        assert "API Design Notes" in buf.getvalue()

    def test_show_artifact_save(self, capture_display):
        display, buf = capture_display
        display.show_artifact_save("api-spec.yaml")
        assert "api-spec.yaml" in buf.getvalue()

    def test_show_done_signal(self, capture_display):
        display, buf = capture_display
        display.show_done_signal("a", "Topic well explored")
        assert "DONE" in buf.getvalue()
        assert "Topic well explored" in buf.getvalue()

    def test_show_completion(self, make_config, capture_display):
        display, buf = capture_display
        config = make_config(ensure_dirs=False, current_turn=8)
        display.show_completion(config)
        assert "8 turns" in _plain(buf)

    def test_show_deliverable_compile(self, capture_display):
        display, buf = capture_display
        display.show_deliverable_compile("Chapter Summaries")
        output = buf.getvalue()
        assert "Chapter Summaries" in output
        assert "Compiling" in output

    def test_show_summary(self, capture_display):
        display, buf = capture_display
        display.show_summary("## Summary\nKey ideas discussed.")
        output = buf.getvalue()
        assert "Summary" in output
        assert "Key ideas discussed" in output

    def test_show_done_disagreement(self, capture_display):
        display, buf = capture_display
        display.show_done_disagreement("b", "a")
        output = buf.getvalue()
        assert "disagrees" in output
        assert "A" in output
        assert "DONE" in output

    def test_show_proposal(self, capture_display):
        display, buf = capture_display
        display.show_proposal("a", "Use REST API", "a3f2")
        output = buf.getvalue()
        assert "a3f2" in output
        assert "Use REST API" in output
        assert "A" in output

    def test_show_agreement_accepted(self, capture_display):
        display, buf = capture_display
        display.show_agreement_accepted("a3f2", "Use REST API")
        output = buf.getvalue()
        assert "a3f2" in output
        assert "Use REST API" in output
        assert "accepted" in output.lower()

    def test_show_agreement_rejected(self, capture_display):
        display, buf = capture_display
        display.show_agreement_rejected("a3f2", "Too complex")
        output = buf.getvalue()
        assert "a3f2" in output
        assert "Too complex" in output
        assert "rejected" in output.lower()

    def test_show_revision_proposed(self, capture_display):
        display, buf = capture_display
        display.show_revision_proposed("b", "a3f2", "e9d4")
        output = buf.getvalue()
        assert "a3f2" in output
        assert "e9d4" in output
        assert "B" in output

    def test_plain_display_satisfies_protocol(self):
        """PlainDisplay satisfies DisplayProtocol."""
        display = PlainDisplay()
        assert isinstance(display, DisplayProtocol)


class TestTruncateLabel:
    def test_short_passthrough(self):
        assert _truncate_label("Architect") == "Architect"

    def test_long_truncated(self):
        long = "A" * 60
        result = _truncate_label(long, max_len=40)
        assert len(result) == 40
        assert result.endswith("…")

    def test_multiline_first_line_only(self):
        label = "First line\nSecond line\nThird line"
        assert _truncate_label(label) == "First line"
