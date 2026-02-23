"""Tests for StormApp Textual application."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from textual.widgets import Static

from claude_storm.app import StormApp
from claude_storm.messages import (
    SessionComplete,
    ShowRenderable,
    StreamDelta,
    StreamEnd,
    StreamStart,
)
from claude_storm.widgets import InputBar, SelectableRichLog


class TestStormApp:
    @pytest.mark.asyncio
    async def test_app_composes_widgets(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                assert pilot.app.query_one("#output-log", SelectableRichLog) is not None
                assert pilot.app.query_one("#header-bar") is not None

    @pytest.mark.asyncio
    async def test_show_renderable_writes_to_log(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                from rich.text import Text

                app.post_message(ShowRenderable(Text("Hello")))
                await pilot.pause()
                log = pilot.app.query_one("#output-log", SelectableRichLog)
                assert len(log.lines) > 0

    @pytest.mark.asyncio
    async def test_session_complete_exits_app(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                app.post_message(SessionComplete())
                await pilot.pause()
                assert app._session_finished is True

    @pytest.mark.asyncio
    async def test_interactive_mode_has_input_bar(self, make_config):
        config = make_config(interactive=True, save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                assert pilot.app.query_one(InputBar) is not None

    @pytest.mark.asyncio
    async def test_scroll_indicator_hidden_by_default(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                indicator = pilot.app.query_one("#scroll-indicator", Static)
                assert indicator.display is False

    @pytest.mark.asyncio
    async def test_scroll_indicator_shows_when_not_following(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test(size=(80, 24)) as pilot:
                log = pilot.app.query_one("#output-log", SelectableRichLog)
                log.following = False
                await pilot.pause()
                indicator = pilot.app.query_one("#scroll-indicator", Static)
                assert indicator.display is True

    @pytest.mark.asyncio
    async def test_scroll_indicator_hides_when_following_resumes(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test(size=(80, 24)) as pilot:
                log = pilot.app.query_one("#output-log", SelectableRichLog)
                log.following = False
                await pilot.pause()
                log.following = True
                await pilot.pause()
                indicator = pilot.app.query_one("#scroll-indicator", Static)
                assert indicator.display is False

    @pytest.mark.asyncio
    async def test_stream_delta_writes_to_log(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test(size=(80, 24)) as pilot:
                app.post_message(StreamStart())
                await pilot.pause()
                log = pilot.app.query_one("#output-log", SelectableRichLog)
                lines_before = len(log.lines)
                # Newline terminates the buffered chunk and flushes a log entry
                app.post_message(StreamDelta("Hello world\n"))
                await pilot.pause()
                assert len(log.lines) > lines_before

    @pytest.mark.asyncio
    async def test_stream_delta_buffers_until_newline(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test(size=(80, 24)) as pilot:
                app.post_message(StreamStart())
                await pilot.pause()
                log = pilot.app.query_one("#output-log", SelectableRichLog)
                lines_before = len(log.lines)
                # No newline — chunk stays in buffer, nothing written to log yet
                app.post_message(StreamDelta("no newline here"))
                await pilot.pause()
                assert len(log.lines) == lines_before

    @pytest.mark.asyncio
    async def test_stream_end_truncates_and_rewrites(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test(size=(80, 24)) as pilot:
                log = pilot.app.query_one("#output-log", SelectableRichLog)
                # Write a sentinel line before streaming starts
                from rich.text import Text

                log.write(Text("sentinel"))
                await pilot.pause()
                checkpoint = len(log.lines)

                app.post_message(StreamStart())
                await pilot.pause()
                # Newline-terminated deltas flush complete lines to the log
                app.post_message(StreamDelta("chunk one\n"))
                app.post_message(StreamDelta("chunk two\n"))
                await pilot.pause()
                assert len(log.lines) > checkpoint

                # StreamEnd truncates back and writes Markdown
                app.post_message(StreamEnd(text="chunk one\nchunk two"))
                await pilot.pause()
                # Lines should be back near checkpoint (markdown + blank line)
                assert len(log.lines) >= checkpoint

    @pytest.mark.asyncio
    async def test_stream_end_error_writes_error_text(self, make_config):
        config = make_config(save=True)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test(size=(80, 24)) as pilot:
                app.post_message(StreamStart())
                await pilot.pause()
                app.post_message(StreamEnd(error=True, text=""))
                await pilot.pause()
                log = pilot.app.query_one("#output-log", SelectableRichLog)
                # At least the blank line is written on stream end
                assert len(log.lines) > 0
