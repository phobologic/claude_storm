"""Tests for custom Textual widgets."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from claude_storm.widgets import GrowingTextArea, InputBar, ThinkingBar


class ThinkingBarApp(App):
    def compose(self) -> ComposeResult:
        yield ThinkingBar()


class InputBarApp(App):
    def compose(self) -> ComposeResult:
        yield InputBar()


class GrowingTextAreaApp(App):
    def __init__(self):
        super().__init__()
        self.submitted_values: list[str] = []

    def compose(self) -> ComposeResult:
        yield GrowingTextArea()

    def on_growing_text_area_submitted(self, event: GrowingTextArea.Submitted) -> None:
        self.submitted_values.append(event.value)


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
            assert "Author A..." in content, f"render() returned: {content!r}"

    @pytest.mark.asyncio
    async def test_start_with_multiline_label(self):
        async with ThinkingBarApp().run_test(size=(80, 5)) as pilot:
            bar = pilot.app.query_one(ThinkingBar)
            bar.start("\nAuthor A\nSome long description\n", timeout=300)
            await pilot.pause()
            content = str(bar.render())
            assert "Author A" in content and "0s / 300s" in content

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
            assert "nudge" in input_bar._input.border_title.lower()

    @pytest.mark.asyncio
    async def test_set_ask_mode(self):
        async with InputBarApp().run_test() as pilot:
            input_bar = pilot.app.query_one(InputBar)
            input_bar.set_ask_mode("What framework?")
            assert "What framework?" in input_bar._input.border_title

    @pytest.mark.asyncio
    async def test_set_nudge_mode_restores(self):
        async with InputBarApp().run_test() as pilot:
            input_bar = pilot.app.query_one(InputBar)
            input_bar.set_ask_mode("Question?")
            input_bar.set_nudge_mode()
            assert "nudge" in input_bar._input.border_title.lower()


class TestGrowingTextArea:
    @pytest.mark.asyncio
    async def test_submit_on_enter(self):
        app = GrowingTextAreaApp()
        async with app.run_test(size=(80, 10)) as pilot:
            ta = pilot.app.query_one(GrowingTextArea)
            ta.focus()
            await pilot.press("h", "i")
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.submitted_values) == 1
            assert app.submitted_values[0] == "hi"

    @pytest.mark.asyncio
    async def test_clear_resets_height(self):
        app = GrowingTextAreaApp()
        async with app.run_test(size=(80, 10)) as pilot:
            ta = pilot.app.query_one(GrowingTextArea)
            ta.text = "line1\nline2\nline3"
            await pilot.pause()
            ta.clear()
            await pilot.pause()
            assert ta.text == ""
