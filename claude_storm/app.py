"""Textual-based TUI application for Claude Storm."""

from __future__ import annotations

import threading
from collections import deque
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import RichLog, Static

from claude_storm.config import SessionConfig
from claude_storm.messages import (
    ShowRenderable,
    UpdateThinking,
    ClearThinking,
    RequestUserInput,
    SessionComplete,
)
from claude_storm.widgets import ThinkingBar, InputBar, GrowingTextArea


class StormApp(App):
    """Textual app for running a Claude Storm brainstorming session."""

    CSS_PATH = "storm_app.tcss"
    TITLE = "Claude Storm"

    BINDINGS = [
        Binding("ctrl+c", "quit_session", "Pause / Quit", priority=True),
    ]

    def __init__(
        self,
        config: SessionConfig,
        resume: bool = False,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.resume = resume
        self.nudge_queue: deque[str] = deque()
        self._ask_request: RequestUserInput | None = None
        self._session_error: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="header-bar")
        yield RichLog(id="output-log", highlight=True, markup=True, wrap=True)
        yield ThinkingBar()
        if self.config.interactive:
            yield InputBar()

    def on_mount(self) -> None:
        """Set up header and start the session worker."""
        header = self.query_one("#header-bar", Static)
        mode_parts = [f"max {self.config.max_turns} turns"]
        if self.config.max_minutes:
            mode_parts.append(f"max {self.config.max_minutes} min")
        if self.config.auto_complete:
            mode_parts.append("auto-complete")
        if self.config.interactive:
            mode_parts.append("interactive")
        # Show only the first line of the topic, truncated, to keep the
        # header bar compact (full topic is visible in the session output).
        topic_summary = self.config.topic.split("\n")[0].strip()
        if len(topic_summary) > 80:
            topic_summary = topic_summary[:79] + "…"
        header.update(
            f"[bold magenta]Claude Storm[/bold magenta]  "
            f"[bold]{topic_summary}[/bold]  "
            f"[dim]{', '.join(mode_parts)}[/dim]"
        )
        self.run_worker(self._session_worker, thread=True)

    def _session_worker(self) -> None:
        """Run the session loop in a worker thread."""
        from claude_storm.cli import run_session
        from claude_storm.display import TextualDisplay

        display = TextualDisplay(self)
        try:
            run_session(self.config, display, nudge_queue=self.nudge_queue)
        except Exception as exc:
            if self.config.debug:
                import traceback
                debug_log = self.config.session_dir() / "debug.log"
                with open(debug_log, "a") as f:
                    f.write(f"\n=== Worker Exception ===\n{traceback.format_exc()}\n")
            self.post_message(SessionComplete(error=str(exc)))
            return
        self.post_message(SessionComplete())

    # ── Message handlers ──────────────────────────────────────────

    def on_show_renderable(self, message: ShowRenderable) -> None:
        log = self.query_one("#output-log", RichLog)
        log.write(message.renderable)

    def on_update_thinking(self, message: UpdateThinking) -> None:
        bar = self.query_one(ThinkingBar)
        bar.start(message.label, timeout=message.timeout)

    def on_clear_thinking(self, message: ClearThinking) -> None:
        bar = self.query_one(ThinkingBar)
        bar.stop()

    def on_request_user_input(self, message: RequestUserInput) -> None:
        self._ask_request = message
        log = self.query_one("#output-log", RichLog)
        from rich.panel import Panel
        log.write(Panel(message.question, title="Agent Question", border_style="yellow"))
        try:
            input_bar = self.query_one(InputBar)
            input_bar.set_ask_mode(message.question)
        except Exception:
            # No InputBar (non-interactive) — unblock with empty response
            message.response = ""
            message.event.set()

    def on_growing_text_area_submitted(self, event: GrowingTextArea.Submitted) -> None:
        text = event.value.strip()
        event.text_area.clear()
        if self._ask_request is not None:
            # Respond to ASK_USER
            self._ask_request.response = text
            self._ask_request.event.set()
            self._ask_request = None
            try:
                input_bar = self.query_one(InputBar)
                input_bar.set_nudge_mode()
            except Exception:
                pass
        elif text:
            # Nudge input
            self.nudge_queue.append(text)
            log = self.query_one("#output-log", RichLog)
            from rich.panel import Panel
            log.write(Panel(text, title="Your Input (queued)", border_style="yellow", title_align="left"))

    def on_session_complete(self, message: SessionComplete) -> None:
        if message.error:
            log = self.query_one("#output-log", RichLog)
            from rich.text import Text
            log.write(Text(f"Session error: {message.error}", style="bold red"))
        self._session_error = message.error
        self.exit()

    def action_quit_session(self) -> None:
        """Handle Ctrl+C — request graceful shutdown and kill active subprocess."""
        from claude_storm.cli import _signal_handler
        from claude_storm.agents import cancel_active
        _signal_handler(0, None)
        # Persist paused status immediately so it survives a hard exit.
        self.config.status = "paused"
        self.config.save()
        cancel_active()
        self.exit()
