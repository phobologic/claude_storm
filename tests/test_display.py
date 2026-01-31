"""Tests for display formatting."""

import re
from io import StringIO

from rich.console import Console

from claude_storm.config import SessionConfig
from claude_storm.display import Display

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _make_config():
    return SessionConfig(
        session_id="test123",
        topic="Design an API",
        goal="RESTful todo app",
        role_a="Architect",
        role_b="Critic",
        claude_session_a="a",
        claude_session_b="b",
        max_turns=10,
        auto_complete=True,
        interactive=True,
        model="sonnet",
        current_turn=0,
        started_at="2025-01-31T10:00:00+00:00",
        status="active",
    )


def _capture_display() -> tuple[Display, StringIO]:
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, no_color=True, width=120)
    return Display(console=console), buf


def _plain(buf: StringIO) -> str:
    """Strip ANSI escape sequences from buffer output."""
    return _ANSI_RE.sub("", buf.getvalue())


class TestDisplay:
    def test_show_header(self):
        display, buf = _capture_display()
        config = _make_config()
        display.show_header(config)
        output = buf.getvalue()
        assert "Claude Storm" in output
        assert "Design an API" in output
        assert "Architect" in output
        assert "Critic" in output

    def test_show_turn_start(self):
        display, buf = _capture_display()
        config = _make_config()
        display.show_turn_start(config, "a")
        output = _plain(buf)
        assert "Turn 1/10" in output
        assert "Architect" in output

    def test_show_agent_response(self):
        display, buf = _capture_display()
        config = _make_config()
        display.show_agent_response(config, "a", "Here is my analysis")
        output = buf.getvalue()
        assert "Architect" in output

    def test_show_status(self):
        display, buf = _capture_display()
        display.show_status("Processing...")
        assert "Processing..." in _plain(buf)

    def test_show_error(self):
        display, buf = _capture_display()
        display.show_error("Something failed")
        assert "Something failed" in buf.getvalue()

    def test_show_memory_save(self):
        display, buf = _capture_display()
        display.show_memory_save("a", "API Design Notes")
        assert "API Design Notes" in buf.getvalue()

    def test_show_artifact_save(self):
        display, buf = _capture_display()
        display.show_artifact_save("api-spec.yaml")
        assert "api-spec.yaml" in buf.getvalue()

    def test_show_done_signal(self):
        display, buf = _capture_display()
        display.show_done_signal("a", "Topic well explored")
        assert "DONE" in buf.getvalue()
        assert "Topic well explored" in buf.getvalue()

    def test_show_completion(self):
        display, buf = _capture_display()
        config = _make_config()
        config.current_turn = 8
        display.show_completion(config)
        assert "8 turns" in _plain(buf)

    def test_show_summary(self):
        display, buf = _capture_display()
        display.show_summary("## Summary\nKey ideas discussed.")
        output = buf.getvalue()
        assert "Summary" in output
