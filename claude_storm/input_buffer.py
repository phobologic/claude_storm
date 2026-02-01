"""Thread-safe input buffer for collecting user nudges during agent turns."""

from __future__ import annotations

import sys
import threading
from collections import deque


class InputBuffer:
    """Collects user input lines in a background thread.

    Lines are accumulated in a thread-safe deque and can be drained
    (consumed) as a single string for injection into the next agent prompt.
    """

    def __init__(self) -> None:
        self._lines: deque[str] = deque()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background reader thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the reader thread to stop.

        Because ``input()`` blocks, the thread may not exit immediately.
        Since it is a daemon thread, it will be cleaned up on process exit.
        """
        self._stop_event.set()

    def _reader_loop(self) -> None:
        """Blocking loop that reads stdin lines until stopped."""
        while not self._stop_event.is_set():
            try:
                line = input()
            except EOFError:
                break
            except Exception:
                break
            stripped = line.strip()
            if stripped:
                with self._lock:
                    self._lines.append(stripped)

    def drain(self) -> str | None:
        """Pop all queued lines and return them joined with newlines.

        Returns ``None`` if the buffer is empty.
        """
        with self._lock:
            if not self._lines:
                return None
            joined = "\n".join(self._lines)
            self._lines.clear()
            return joined

    def has_pending(self) -> bool:
        """Return whether there are queued lines."""
        with self._lock:
            return len(self._lines) > 0

    @property
    def pending_count(self) -> int:
        """Return the number of queued lines."""
        with self._lock:
            return len(self._lines)
