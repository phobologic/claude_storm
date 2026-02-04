"""Tests for StormApp Textual application."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from claude_storm.app import StormApp
from claude_storm.widgets import SelectableRichLog
from claude_storm.config import SessionConfig
from claude_storm.messages import ShowRenderable, SessionComplete


def _make_config(tmp_storms):
    config = SessionConfig(
        session_id="app-test",
        topic="Test topic",
        goal="Test goal",
        role_a="Architect",
        role_b="Critic",
        max_turns=10,
        interactive=False,
        storms_dir=str(tmp_storms),
    )
    config.ensure_dirs()
    config.save()
    return config


class TestStormApp:
    @pytest.mark.asyncio
    async def test_app_composes_widgets(self, tmp_storms):
        config = _make_config(tmp_storms)
        app = StormApp(config)
        # Patch session worker to avoid running real session
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                assert pilot.app.query_one("#output-log", SelectableRichLog) is not None
                assert pilot.app.query_one("#header-bar") is not None

    @pytest.mark.asyncio
    async def test_show_renderable_writes_to_log(self, tmp_storms):
        config = _make_config(tmp_storms)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                from rich.text import Text
                app.post_message(ShowRenderable(Text("Hello")))
                await pilot.pause()

    @pytest.mark.asyncio
    async def test_session_complete_exits_app(self, tmp_storms):
        config = _make_config(tmp_storms)
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                app.post_message(SessionComplete())
                await pilot.pause()

    @pytest.mark.asyncio
    async def test_interactive_mode_has_input_bar(self, tmp_storms):
        config = _make_config(tmp_storms)
        config.interactive = True
        app = StormApp(config)
        with patch.object(app, "_session_worker", return_value=None):
            async with app.run_test() as pilot:
                from claude_storm.widgets import InputBar
                assert pilot.app.query_one(InputBar) is not None
