"""Tests for custom Textual widgets."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from claude_storm.widgets import ThinkingBar, InputBar


class ThinkingBarApp(App):
    def compose(self) -> ComposeResult:
        yield ThinkingBar()


class InputBarApp(App):
    def compose(self) -> ComposeResult:
        yield InputBar()


class TestThinkingBar:
    @pytest.mark.asyncio
    async def test_start_makes_active(self):
        async with ThinkingBarApp().run_test() as pilot:
            bar = pilot.app.query_one(ThinkingBar)
            bar.start("Agent A")
            assert bar.active is True
            assert bar.label == "Agent A"

    @pytest.mark.asyncio
    async def test_start_shows_timer_text(self):
        async with ThinkingBarApp().run_test(size=(80, 5)) as pilot:
            bar = pilot.app.query_one(ThinkingBar)
            bar.start("Author A", timeout=300)
            await pilot.pause()
            content = str(bar.render())
            assert "is thinking" in content, f"render() returned: {content!r}"

    @pytest.mark.asyncio
    async def test_start_with_multiline_label(self):
        async with ThinkingBarApp().run_test(size=(80, 5)) as pilot:
            bar = pilot.app.query_one(ThinkingBar)
            bar.start("\nAuthor A\nSome long description\n", timeout=300)
            await pilot.pause()
            content = str(bar.render())
            assert "is thinking" in content

    @pytest.mark.asyncio
    async def test_stop_returns_elapsed(self):
        async with ThinkingBarApp().run_test() as pilot:
            bar = pilot.app.query_one(ThinkingBar)
            bar.start("Agent A")
            elapsed = bar.stop()
            assert isinstance(elapsed, int)
            assert elapsed >= 0
            assert bar.active is False


class TestInputBar:
    @pytest.mark.asyncio
    async def test_default_nudge_mode(self):
        async with InputBarApp().run_test() as pilot:
            input_bar = pilot.app.query_one(InputBar)
            assert "nudge" in input_bar._input.placeholder.lower()

    @pytest.mark.asyncio
    async def test_set_ask_mode(self):
        async with InputBarApp().run_test() as pilot:
            input_bar = pilot.app.query_one(InputBar)
            input_bar.set_ask_mode("What framework?")
            assert input_bar._input.placeholder == "What framework?"

    @pytest.mark.asyncio
    async def test_set_nudge_mode_restores(self):
        async with InputBarApp().run_test() as pilot:
            input_bar = pilot.app.query_one(InputBar)
            input_bar.set_ask_mode("Question?")
            input_bar.set_nudge_mode()
            assert "nudge" in input_bar._input.placeholder.lower()
