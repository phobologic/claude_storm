"""Custom Textual widgets for StormApp."""

from __future__ import annotations

import time

from textual.widget import Widget
from textual.widgets import Static, Input
from textual.containers import Horizontal


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


class InputBar(Horizontal):
    """Always-visible input bar for nudges and ASK_USER responses."""

    DEFAULT_CSS = """
    InputBar {
        dock: bottom;
        height: auto;
        max-height: 3;
        padding: 0 1;
    }
    InputBar .input-label {
        width: auto;
        padding: 0 1 0 0;
        color: $text-muted;
    }
    InputBar Input {
        width: 1fr;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._label = Static("Nudge:", classes="input-label")
        self._input = Input(placeholder="Type to nudge the conversation...")

    def compose(self):
        yield self._label
        yield self._input

    def set_ask_mode(self, question: str) -> None:
        """Switch to ASK_USER mode."""
        self._label.update("Your response:")
        self._input.placeholder = question
        self._input.focus()

    def set_nudge_mode(self) -> None:
        """Switch back to nudge mode."""
        self._label.update("Nudge:")
        self._input.placeholder = "Type to nudge the conversation..."

    @property
    def input_widget(self) -> Input:
        return self._input
