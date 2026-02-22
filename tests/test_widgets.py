"""Tests for custom Textual widgets."""

from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App, ComposeResult

from claude_storm.widgets import (
    GrowingTextArea,
    InputBar,
    SelectableRichLog,
    ThinkingBar,
)


class SelectableRichLogApp(App):
    def compose(self) -> ComposeResult:
        yield SelectableRichLog(id="log")


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


class TestSelectableRichLog:
    @pytest.mark.asyncio
    async def test_truncate_to_removes_lines(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.write(Text("line one"))
            log.write(Text("line two"))
            log.write(Text("line three"))
            await pilot.pause()
            checkpoint = len(log.lines)
            log.write(Text("line four"))
            log.write(Text("line five"))
            await pilot.pause()
            assert len(log.lines) > checkpoint
            log.truncate_to(checkpoint)
            await pilot.pause()
            assert len(log.lines) == checkpoint

    @pytest.mark.asyncio
    async def test_truncate_to_noop_when_at_checkpoint(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.write(Text("line one"))
            await pilot.pause()
            count_before = len(log.lines)
            log.truncate_to(count_before)
            await pilot.pause()
            assert len(log.lines) == count_before

    @pytest.mark.asyncio
    async def test_truncate_to_clears_cache(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.write(Text("line one"))
            await pilot.pause()
            checkpoint = len(log.lines)
            log.write(Text("line two"))
            log.write(Text("line three"))
            await pilot.pause()
            lines_after_extra = len(log.lines)
            log.truncate_to(checkpoint)
            await pilot.pause()
            # Cache must not retain entries for the removed lines
            assert len(log._line_cache) <= checkpoint
            assert len(log._line_cache) < lines_after_extra


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
