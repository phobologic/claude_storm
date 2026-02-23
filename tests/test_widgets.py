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


def _make_mouse_event(cls, widget):
    return cls(
        widget=widget,
        x=0,
        y=0,
        delta_x=0,
        delta_y=1,
        button=0,
        shift=False,
        meta=False,
        ctrl=False,
    )


class TestScrollLock:
    # ── Default state ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_default_following_is_true(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            assert log.following is True

    @pytest.mark.asyncio
    async def test_default_auto_scroll_is_true(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            assert log.auto_scroll is True

    # ── Mouse event handlers set the _user_scrolling flag ─────────

    @pytest.mark.asyncio
    async def test_mouse_scroll_up_sets_user_scrolling_flag(self):
        from textual.events import MouseScrollUp

        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.on_mouse_scroll_up(_make_mouse_event(MouseScrollUp, log))
            assert log._user_scrolling is True

    @pytest.mark.asyncio
    async def test_mouse_scroll_down_sets_user_scrolling_flag(self):
        from textual.events import MouseScrollDown

        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.on_mouse_scroll_down(_make_mouse_event(MouseScrollDown, log))
            assert log._user_scrolling is True

    @pytest.mark.asyncio
    async def test_mouse_scroll_up_via_post_message_sets_user_scrolling_flag(self):
        """Verify scroll-up handler wiring via Textual's message pump.

        Unlike the direct on_mouse_scroll_up() call above, this dispatches through
        post_message so that Textual's event routing and handler lookup are exercised.
        """
        from textual.events import MouseScrollUp

        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.post_message(_make_mouse_event(MouseScrollUp, log))
            await pilot.pause()
            assert log._user_scrolling is True

    # ── watch_scroll_y guards on _user_scrolling flag ─────────────

    @pytest.mark.asyncio
    async def test_watch_scroll_y_without_flag_does_not_change_following(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log._user_scrolling = False
            log.watch_scroll_y(1000.0, 900.0)
            await pilot.pause()
            assert log.following is True  # unchanged — no user scroll flag

    @pytest.mark.asyncio
    async def test_watch_scroll_y_with_flag_not_at_bottom_disengages(self, monkeypatch):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            monkeypatch.setattr(
                type(log), "is_vertical_scroll_end", property(lambda self: False)
            )
            log._user_scrolling = True
            log.watch_scroll_y(1000.0, 900.0)
            await pilot.pause()
            assert log.following is False

    @pytest.mark.asyncio
    async def test_watch_scroll_y_with_flag_at_bottom_re_engages(self, monkeypatch):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.following = False
            monkeypatch.setattr(
                type(log), "is_vertical_scroll_end", property(lambda self: True)
            )
            log._user_scrolling = True
            log.watch_scroll_y(900.0, 1000.0)
            await pilot.pause()
            assert log.following is True

    @pytest.mark.asyncio
    async def test_watch_scroll_y_clears_flag_after_processing(self, monkeypatch):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            monkeypatch.setattr(
                type(log), "is_vertical_scroll_end", property(lambda self: False)
            )
            log._user_scrolling = True
            log.watch_scroll_y(1000.0, 900.0)
            assert log._user_scrolling is False

    # ── watch_following syncs auto_scroll ─────────────────────────

    @pytest.mark.asyncio
    async def test_watch_following_syncs_auto_scroll(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.following = False
            await pilot.pause()
            assert log.auto_scroll is False
            log.following = True
            await pilot.pause()
            assert log.auto_scroll is True

    @pytest.mark.asyncio
    async def test_watch_following_posts_following_changed(self):
        messages: list[SelectableRichLog.FollowingChanged] = []

        class TrackingApp(SelectableRichLogApp):
            def on_selectable_rich_log_following_changed(
                self, message: SelectableRichLog.FollowingChanged
            ) -> None:
                messages.append(message)

        async with TrackingApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.following = False
            await pilot.pause()
            assert any(not m.following for m in messages)

    # ── scroll_to_bottom ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_scroll_to_bottom_re_engages_following(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.following = False
            await pilot.pause()
            log.scroll_to_bottom()
            await pilot.pause()
            assert log.following is True

    @pytest.mark.asyncio
    async def test_scroll_to_bottom_re_enables_auto_scroll(self):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.following = False
            await pilot.pause()
            log.scroll_to_bottom()
            await pilot.pause()
            assert log.auto_scroll is True

    # ── Keyboard scroll keys set _user_scrolling flag ─────────────

    @pytest.mark.asyncio
    async def test_key_up_sets_user_scrolling_flag(self):
        from textual.events import Key

        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            await log._on_key(Key("up", character=None))
            assert log._user_scrolling is True

    @pytest.mark.asyncio
    async def test_key_pageup_sets_user_scrolling_flag(self):
        from textual.events import Key

        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            await log._on_key(Key("pageup", character=None))
            assert log._user_scrolling is True

    @pytest.mark.asyncio
    async def test_key_end_sets_user_scrolling_flag(self):
        from textual.events import Key

        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            await log._on_key(Key("end", character=None))
            assert log._user_scrolling is True

    @pytest.mark.asyncio
    async def test_non_scroll_key_does_not_set_user_scrolling_flag(self):
        from textual.events import Key

        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            await log._on_key(Key("a", character="a"))
            assert log._user_scrolling is False

    # ── _maybe_reengage_following ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_maybe_reengage_clears_stale_user_scrolling_flag(self, monkeypatch):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log._user_scrolling = True
            monkeypatch.setattr(
                type(log), "is_vertical_scroll_end", property(lambda self: True)
            )
            log._maybe_reengage_following()
            assert log._user_scrolling is False

    @pytest.mark.asyncio
    async def test_maybe_reengage_re_engages_at_bottom(self, monkeypatch):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            log.following = False
            await pilot.pause()
            monkeypatch.setattr(
                type(log), "is_vertical_scroll_end", property(lambda self: True)
            )
            log._maybe_reengage_following()
            assert log.following is True

    @pytest.mark.asyncio
    async def test_maybe_reengage_does_not_disengage_when_not_at_bottom(
        self, monkeypatch
    ):
        async with SelectableRichLogApp().run_test(size=(80, 24)) as pilot:
            log = pilot.app.query_one("#log", SelectableRichLog)
            monkeypatch.setattr(
                type(log), "is_vertical_scroll_end", property(lambda self: False)
            )
            log._maybe_reengage_following()
            assert (
                log.following is True
            )  # unchanged — only re-engages, never disengages


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
    async def test_shift_enter_inserts_newline(self):
        # macOS terminals send shift+enter as ctrl+j; test both code paths.
        app = GrowingTextAreaApp()
        async with app.run_test(size=(80, 10)) as pilot:
            ta = pilot.app.query_one(GrowingTextArea)
            ta.focus()
            await pilot.press("a", "ctrl+j", "b")
            await pilot.pause()
            assert ta.text == "a\nb"
            assert len(app.submitted_values) == 0

    @pytest.mark.asyncio
    async def test_shift_enter_inserts_newline_non_mac(self):
        # Terminals that send a distinct shift+enter key (non-macOS).
        app = GrowingTextAreaApp()
        async with app.run_test(size=(80, 10)) as pilot:
            ta = pilot.app.query_one(GrowingTextArea)
            ta.focus()
            await pilot.press("a", "shift+enter", "b")
            await pilot.pause()
            assert ta.text == "a\nb"
            assert len(app.submitted_values) == 0

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
