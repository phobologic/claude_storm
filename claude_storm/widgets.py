"""Custom Textual widgets for StormApp."""

from __future__ import annotations

import contextlib
import time

from rich.text import Text
from textual.events import Key, MouseScrollDown, MouseScrollUp
from textual.message import Message
from textual.reactive import var
from textual.selection import Selection
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import RichLog, TextArea

_SCROLL_KEYS: frozenset[str] = frozenset(
    {"up", "down", "pageup", "pagedown", "home", "end"}
)


class SelectableRichLog(RichLog):
    """RichLog subclass that supports text selection, copy, and scroll-lock."""

    following: var[bool] = var(True)
    """True when auto-scrolling follows new output; False when user has scrolled up."""

    # Set by mouse scroll handlers; consumed and cleared in watch_scroll_y.
    # Prevents programmatic auto-scrolls from falsely re-engaging scroll-lock.
    _user_scrolling: bool = False

    class FollowingChanged(Message):
        """Posted when the following state changes."""

        def __init__(self, following: bool) -> None:
            super().__init__()
            self.following = following

    def watch_following(self, following: bool) -> None:
        """Sync auto_scroll with following state and notify the app."""
        self.auto_scroll = following
        self.post_message(self.FollowingChanged(following))

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        """Mark that a user scroll event is in progress."""
        self._user_scrolling = True

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        """Mark that a user scroll event is in progress."""
        self._user_scrolling = True

    async def _on_key(self, event: Key) -> None:
        """Mark scroll-key events as user-initiated before they update scroll_y."""
        if event.key in _SCROLL_KEYS:
            self._user_scrolling = True
            await super()._on_key(event)
            # If the scroll landed exactly at the bottom, scroll_y may not have
            # changed (already clamped), so watch_scroll_y won't fire.  Schedule
            # a post-render check to re-engage following in that case.
            self.call_after_refresh(self._maybe_reengage_following)
        else:
            await super()._on_key(event)

    def _maybe_reengage_following(self) -> None:
        """Re-engage following if a keyboard scroll landed at the bottom."""
        self._user_scrolling = False  # Clear stale flag if watch_scroll_y didn't run
        if self.is_vertical_scroll_end and not self.following:
            self.following = True

    def watch_scroll_y(self, old: float, new: float) -> None:
        """Update scrollbar; disengage or re-engage scroll-lock on user scrolls.

        The _user_scrolling flag gates all following-state changes so that
        programmatic auto-scrolls (write → scroll_end) and virtual_size
        clamping from truncate_to() never falsely mutate following.

        Args:
            old: Previous scroll_y value.
            new: New scroll_y value.
        """
        # super().watch_scroll_y drives Textual's scrollbar position update and
        # must be called first. It relies on a RichLog internal (not public API);
        # audit this call when upgrading Textual.
        super().watch_scroll_y(old, new)
        if not self._user_scrolling:
            return
        self._user_scrolling = False
        if self.is_vertical_scroll_end:
            if not self.following:
                self.following = True
        else:
            if self.following:
                self.following = False

    def scroll_to_bottom(self) -> None:
        """Jump to the bottom and re-engage scroll-lock."""
        # Set following=True eagerly so the scroll indicator hides immediately;
        # watch_scroll_y will also set it True once scroll_end resolves (benign double-fire).
        self.following = True
        self.scroll_end(animate=False)

    def _render_line(self, y: int, scroll_x: int, width: int) -> Strip:
        if y >= len(self.lines):
            return Strip.blank(width, self.rich_style)

        selection = self.text_selection

        # Use the LRU cache only when there is no active selection.
        key = (y + self._start_line, scroll_x, width, self._widest_line_width)
        if selection is None and key in self._line_cache:
            return self._line_cache[key]

        line = self.lines[y]

        # Apply selection highlighting if a span covers this line.
        if selection is not None:
            span = selection.get_span(y)
            if span is not None:
                start, end = span
                # Reconstruct a Text object preserving per-segment Rich styles.
                line_text = Text()
                for segment in line:
                    line_text.append(segment.text, style=segment.style)
                if end == -1:
                    end = len(line_text)
                selection_style = self.screen.get_component_rich_style(
                    "screen--selection"
                )
                line_text.stylize(selection_style, start, end)
                line = Strip(
                    line_text.render(self.app.console),
                    line._cell_length,
                )

        line = line.crop_extend(scroll_x, scroll_x + width, self.rich_style)
        line = line.apply_offsets(scroll_x, y)

        if selection is None:
            self._line_cache[key] = line
        return line

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        """Extract plain text under the selection."""
        all_lines: list[str] = []
        for strip in self.lines:
            all_lines.append("".join(segment.text for segment in strip))
        text = "\n".join(all_lines)
        return selection.extract(text), "\n"

    def selection_updated(self, selection: Selection | None) -> None:
        """Invalidate cache and refresh when selection changes."""
        self._line_cache.clear()
        self.refresh()

    def truncate_to(self, checkpoint: int) -> None:
        """Truncate rendered lines back to checkpoint line count.

        Args:
            checkpoint: Target line count. No-op if already at or below checkpoint.
        """
        from textual.geometry import Size

        if checkpoint >= len(self.lines):
            return
        self.lines = self.lines[:checkpoint]
        self._line_cache.clear()
        # Do NOT reset _start_line — it tracks historical max_lines trimming
        self._widest_line_width = 0  # Recalculated on next write()
        self.virtual_size = Size(self._widest_line_width, len(self.lines))
        self.refresh()


class ThinkingBar(Widget):
    """Animated timer bar shown while an agent is thinking."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = ""
        self._start_time = 0.0
        self._active = False
        self._timeout = 300

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(1.0, self._tick, pause=True)

    def render(self) -> str:
        if not self._active:
            return ""
        elapsed = int(time.monotonic() - self._start_time)
        return f"  [bold]{self._label}... ({elapsed}s / {self._timeout}s)[/bold]"

    @property
    def label(self) -> str:
        return self._label

    @property
    def active(self) -> bool:
        return self._active

    @property
    def timeout(self) -> int:
        return self._timeout

    def start(self, label: str, timeout: int = 300) -> None:
        """Start the thinking animation."""
        self._label = label
        self._timeout = timeout
        self._start_time = time.monotonic()
        self._active = True
        self.update_timer.resume()
        self.refresh(layout=True)

    def stop(self) -> int:
        """Stop the thinking animation and return elapsed seconds."""
        if not self._active:
            return 0
        self._active = False
        self.update_timer.pause()
        elapsed = int(time.monotonic() - self._start_time)
        self.refresh()
        return elapsed

    def update_label(self, label: str) -> None:
        """Update the display label without resetting the timer."""
        if not self._active:
            return
        self._label = label
        self.refresh()

    def _tick(self) -> None:
        if self._active:
            self.refresh()


class GrowingTextArea(TextArea):
    """A TextArea that starts at 1 row and grows as content wraps, up to a max."""

    DEFAULT_CSS = """
    GrowingTextArea {
        height: 3;
        min-height: 3;
        max-height: 8;
        padding: 0;
        width: 1fr;
        border: tall $accent-muted;
    }
    GrowingTextArea:focus {
        border: tall $accent;
    }
    """

    class Submitted(Message):
        """Posted when the user presses Enter to submit."""

        def __init__(self, text_area: GrowingTextArea, value: str) -> None:
            super().__init__()
            self.text_area = text_area
            self.value = value

    def __init__(self, **kwargs: object) -> None:
        super().__init__(
            show_line_numbers=False,
            soft_wrap=True,
            theme="css",
            **kwargs,
        )

    async def _on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            value = self.text
            self.post_message(self.Submitted(self, value))
            return
        await super()._on_key(event)

    def _on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Grow or shrink to fit content."""
        line_count = self.document.line_count
        # Use wrapped line count if available, otherwise raw line count
        with contextlib.suppress(AttributeError):
            line_count = self.wrapped_document.height
        clamped = max(1, min(6, line_count))
        self.styles.height = clamped + 2  # +2 for tall border

    def clear(self) -> None:
        """Clear content and reset height."""
        self.text = ""
        self.styles.height = 3


class InputBar(Widget):
    """Always-visible input bar for nudges and ASK_USER responses."""

    DEFAULT_CSS = """
    InputBar {
        dock: bottom;
        height: auto;
        max-height: 10;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._input = GrowingTextArea()

    def compose(self):
        self._input.border_title = "Nudge:"
        self._input.border_subtitle = (
            "shift+↩ newline  |  ^c Pause / Quit  |  ^p palette"
        )
        yield self._input

    def set_ask_mode(self, question: str) -> None:
        """Switch to ASK_USER mode."""
        self._input.border_title = f"Answer: {question}"
        self._input.focus()

    def set_nudge_mode(self) -> None:
        """Switch back to nudge mode."""
        self._input.border_title = "Nudge:"

    @property
    def input_widget(self) -> GrowingTextArea:
        return self._input
