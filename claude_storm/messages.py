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


class SessionComplete(Message):
    """The session worker has finished."""

    def __init__(self, error: str | None = None) -> None:
        super().__init__()
        self.error = error
