"""Tests for StormApp Textual application."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from claude_storm.app import StormApp
from claude_storm.messages import SessionComplete, ShowRenderable
from claude_storm.widgets import SelectableRichLog


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
                from claude_storm.widgets import InputBar

                assert pilot.app.query_one(InputBar) is not None
