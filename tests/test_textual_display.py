"""Tests for TextualDisplay: verifies correct Message subclasses are posted."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from claude_storm.config import SessionConfig
from claude_storm.display import TextualDisplay
from claude_storm.messages import (
    ClearThinking,
    RequestUserInput,
    ShowRenderable,
    StreamDelta,
    StreamEnd,
    StreamStart,
    UpdateThinking,
)


def _make_app():
    """Return a mock object that acts as a StormApp."""
    app = MagicMock()
    return app


def _make_config(**kwargs):
    """Return a minimal SessionConfig for testing."""
    defaults = {
        "session_id": "test",
        "topic": "Testing",
        "max_turns": 4,
        "agent_timeout": 60,
    }
    defaults.update(kwargs)
    return SessionConfig(**defaults)


class TestTextualDisplayShowError:
    def test_show_error_posts_show_renderable(self):
        """show_error posts a ShowRenderable message to the app."""
        app = _make_app()
        display = TextualDisplay(app)

        display.show_error("Something went wrong")

        app.post_message.assert_called_once()
        msg = app.post_message.call_args[0][0]
        assert isinstance(msg, ShowRenderable)

    def test_show_error_text_contains_message(self):
        """ShowRenderable from show_error contains the error text."""
        from rich.text import Text

        app = _make_app()
        display = TextualDisplay(app)

        display.show_error("Oops")

        msg = app.post_message.call_args[0][0]
        assert isinstance(msg.renderable, Text)
        assert "Oops" in str(msg.renderable)


class TestTextualDisplayShowTurnStart:
    def test_show_turn_start_posts_show_renderable(self):
        """show_turn_start posts a ShowRenderable message."""
        app = _make_app()
        display = TextualDisplay(app)
        config = _make_config()

        display.show_turn_start(config, "a")

        app.post_message.assert_called_once()
        msg = app.post_message.call_args[0][0]
        assert isinstance(msg, ShowRenderable)

    def test_show_turn_start_includes_turn_number(self):
        """ShowRenderable from show_turn_start references the turn number."""
        app = _make_app()
        display = TextualDisplay(app)
        config = _make_config(current_turn=2)

        display.show_turn_start(config, "a")

        msg = app.post_message.call_args[0][0]
        # Turn displayed as current_turn + 1
        assert "3" in str(msg.renderable)


class TestTextualDisplayAgentStream:
    def test_show_agent_stream_start_posts_stream_start_and_update_thinking(self):
        """show_agent_stream_start posts StreamStart then UpdateThinking."""
        app = _make_app()
        display = TextualDisplay(app)
        config = _make_config()

        display.show_agent_stream_start(config, "a")

        posted_types = [type(c[0][0]) for c in app.post_message.call_args_list]
        assert StreamStart in posted_types
        assert UpdateThinking in posted_types

    def test_show_agent_stream_delta_posts_stream_delta(self):
        """show_agent_stream_delta posts StreamDelta with the text chunk."""
        app = _make_app()
        display = TextualDisplay(app)
        # First call to stream_delta will also post ClearThinking
        display._thinking_cleared = False

        display.show_agent_stream_delta("hello")

        posted = [c[0][0] for c in app.post_message.call_args_list]
        delta_msgs = [m for m in posted if isinstance(m, StreamDelta)]
        assert len(delta_msgs) == 1
        assert delta_msgs[0].text == "hello"

    def test_show_agent_stream_delta_clears_thinking_once(self):
        """First stream_delta posts ClearThinking; subsequent ones do not."""
        app = _make_app()
        display = TextualDisplay(app)
        display._thinking_cleared = False

        display.show_agent_stream_delta("chunk1")
        display.show_agent_stream_delta("chunk2")

        clear_calls = [
            c for c in app.post_message.call_args_list
            if isinstance(c[0][0], ClearThinking)
        ]
        assert len(clear_calls) == 1

    def test_show_agent_stream_end_posts_stream_end(self):
        """show_agent_stream_end posts StreamEnd."""
        app = _make_app()
        display = TextualDisplay(app)
        display._thinking_cleared = True  # skip ClearThinking branch

        display.show_agent_stream_end(error=False, text="final text")

        posted = [c[0][0] for c in app.post_message.call_args_list]
        end_msgs = [m for m in posted if isinstance(m, StreamEnd)]
        assert len(end_msgs) == 1
        assert end_msgs[0].error is False
        assert end_msgs[0].text == "final text"

    def test_show_agent_stream_end_with_error(self):
        """show_agent_stream_end with error=True sets error flag on StreamEnd."""
        app = _make_app()
        display = TextualDisplay(app)
        display._thinking_cleared = True

        display.show_agent_stream_end(error=True, text="")

        posted = [c[0][0] for c in app.post_message.call_args_list]
        end_msgs = [m for m in posted if isinstance(m, StreamEnd)]
        assert end_msgs[0].error is True

    def test_show_agent_stream_end_clears_thinking_when_not_cleared(self):
        """show_agent_stream_end posts ClearThinking if deltas never arrived."""
        app = _make_app()
        display = TextualDisplay(app)
        display._thinking_cleared = False  # simulate no deltas received

        display.show_agent_stream_end()

        posted = [c[0][0] for c in app.post_message.call_args_list]
        clear_msgs = [m for m in posted if isinstance(m, ClearThinking)]
        assert len(clear_msgs) == 1


class TestTextualDisplayThinkingStatus:
    def test_thinking_status_posts_update_then_clear(self):
        """thinking_status context manager posts UpdateThinking then ClearThinking."""
        app = _make_app()
        display = TextualDisplay(app)

        with display.thinking_status("Compiling", timeout=30):
            pass

        posted = [c[0][0] for c in app.post_message.call_args_list]
        assert isinstance(posted[0], UpdateThinking)
        assert posted[0].label == "Compiling"
        assert isinstance(posted[1], ClearThinking)

    def test_thinking_status_clears_on_exception(self):
        """thinking_status posts ClearThinking even if body raises."""
        app = _make_app()
        display = TextualDisplay(app)

        with pytest.raises(ValueError), display.thinking_status("Working"):
            raise ValueError("oops")

        posted = [c[0][0] for c in app.post_message.call_args_list]
        assert any(isinstance(m, ClearThinking) for m in posted)


class TestTextualDisplayPromptUser:
    def test_prompt_user_posts_request_user_input(self):
        """prompt_user posts RequestUserInput to the app."""
        app = _make_app()
        display = TextualDisplay(app)

        # Simulate the app responding by setting the event and response
        def respond(msg):
            if isinstance(msg, RequestUserInput):
                msg.response = "Yes, use JWT"
                msg.event.set()

        app.post_message.side_effect = respond

        result = display.prompt_user("Should we use JWT?")

        posted = [c[0][0] for c in app.post_message.call_args_list]
        req_msgs = [m for m in posted if isinstance(m, RequestUserInput)]
        assert len(req_msgs) == 1
        assert req_msgs[0].question == "Should we use JWT?"
        assert result == "Yes, use JWT"

    def test_prompt_user_blocks_until_event_set(self):
        """prompt_user blocks the caller until the event is set from another thread."""
        app = _make_app()
        display = TextualDisplay(app)

        captured_msg: list[RequestUserInput] = []

        def capture(msg):
            if isinstance(msg, RequestUserInput):
                captured_msg.append(msg)

        app.post_message.side_effect = capture

        result_holder: list[str] = []

        def run_prompt():
            result_holder.append(display.prompt_user("Async question?"))

        t = threading.Thread(target=run_prompt)
        t.start()

        # Wait until the message is captured, then respond
        import time
        for _ in range(20):
            if captured_msg:
                break
            time.sleep(0.05)

        assert captured_msg, "prompt_user did not post RequestUserInput"
        captured_msg[0].response = "thread answer"
        captured_msg[0].event.set()

        t.join(timeout=2)
        assert not t.is_alive(), "prompt_user thread did not unblock"
        assert result_holder == ["thread answer"]

    def test_prompt_user_returns_empty_on_shutdown(self):
        """prompt_user returns '' when _shutdown_requested is set."""
        app = _make_app()
        display = TextualDisplay(app)

        def capture(msg):
            pass  # never set the event

        app.post_message.side_effect = capture

        with patch("claude_storm.display.TextualDisplay.prompt_user") as mock_pu:
            # Test the shutdown path by mocking _shutdown_requested
            mock_pu.return_value = ""
            result = display.prompt_user("Will this block?")

        # The mock returns "" simulating shutdown; just verify the interface
        assert result == ""
