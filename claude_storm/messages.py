"""Custom Textual Message subclasses for StormApp."""

from __future__ import annotations

from rich.console import RenderableType
from textual.message import Message


class ShowRenderable(Message):
    """Post a Rich renderable to the RichLog."""

    def __init__(self, renderable: RenderableType) -> None:
        super().__init__()
        self.renderable = renderable


class UpdateThinking(Message):
    """Start or update the thinking bar with a label."""

    def __init__(self, label: str, timeout: int = 300) -> None:
        super().__init__()
        self.label = label
        self.timeout = timeout


class ClearThinking(Message):
    """Clear the thinking bar (agent finished)."""

    def __init__(self, elapsed: int = 0) -> None:
        super().__init__()
        self.elapsed = elapsed


class UpdateThinkingLabel(Message):
    """Update the thinking bar label without resetting the timer."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label


class RequestUserInput(Message):
    """Worker requests user input (ASK_USER directive).

    The worker thread blocks on ``event`` until the app sets the response.
    """

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question
        import threading

        self.event = threading.Event()
        self.response: str = ""


class StreamStart(Message):
    """Begin streaming an agent response."""


class StreamDelta(Message):
    """Incremental text chunk from a streaming agent response."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class StreamEnd(Message):
    """End of a streaming agent response.

    Attributes:
        error: Whether the stream ended due to an error (e.g. timeout or
            process kill).
        text: Complete response text from the parsed result event. Used as
            fallback content when streaming deltas were not received.
    """

    def __init__(self, error: bool = False, text: str = "") -> None:
        super().__init__()
        self.error = error
        self.text = text


class SessionComplete(Message):
    """The session worker has finished."""

    def __init__(self, error: str | None = None) -> None:
        super().__init__()
        self.error = error
