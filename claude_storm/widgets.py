"""Custom Textual widgets for StormApp."""

from __future__ import annotations

import time

from textual.events import Key
from textual.message import Message
from textual.widget import Widget
from textual.widgets import TextArea


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
        return (
            f"  [bold]{self._label} is thinking... "
            f"({elapsed}s / {self._timeout}s)[/bold]"
        )

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
        self._active = False
        self.update_timer.pause()
        elapsed = int(time.monotonic() - self._start_time)
        self.refresh()
        return elapsed

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
        try:
            line_count = self.wrapped_document.height
        except AttributeError:
            pass
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
