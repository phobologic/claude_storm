"""Textual-based TUI application for Claude Storm."""

from __future__ import annotations

import threading
from collections import deque
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from claude_storm.config import SessionConfig
from claude_storm.messages import (
    ShowRenderable,
    UpdateThinking,
    ClearThinking,
    RequestUserInput,
    SessionComplete,
)
from claude_storm.widgets import SelectableRichLog, ThinkingBar, InputBar, GrowingTextArea


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
        self._deferred_ask: RequestUserInput | None = None
        self._session_error: str | None = None
        self._session_finished: bool = False

    def compose(self) -> ComposeResult:
        yield Static(id="header-bar")
        yield SelectableRichLog(id="output-log", highlight=True, markup=True, wrap=True)
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
            f"[dim]{', '.join(mode_parts)}[/dim]  "
            f"[dim italic]session: {self.config.session_id}[/dim italic]"
        )
        self.run_worker(self._session_worker, thread=True)

    def _session_worker(self) -> None:
        """Run the session loop in a worker thread."""
        from claude_storm.session import run_session
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
        log = self.query_one("#output-log", SelectableRichLog)
        log.write(message.renderable)

    def on_update_thinking(self, message: UpdateThinking) -> None:
        bar = self.query_one(ThinkingBar)
        bar.start(message.label, timeout=message.timeout)

    def on_clear_thinking(self, message: ClearThinking) -> None:
        bar = self.query_one(ThinkingBar)
        bar.stop()

    def on_request_user_input(self, message: RequestUserInput) -> None:
        # If the user is mid-typing, defer the ask until they submit.
        try:
            input_bar = self.query_one(InputBar)
            ta = input_bar.query_one(GrowingTextArea)
            if ta.text.strip():
                self._deferred_ask = message
                return
        except Exception:
            # No InputBar (non-interactive) — unblock with empty response
            message.response = ""
            message.event.set()
            return
        self._activate_ask(message)

    def _activate_ask(self, message: RequestUserInput) -> None:
        """Display an agent question and switch the input bar to ask mode."""
        self._ask_request = message
        log = self.query_one("#output-log", SelectableRichLog)
        from rich.rule import Rule
        from rich.console import Group
        from rich.text import Text
        log.write(Group(
            Rule("Agent Question", style="yellow", align="left"),
            Text(message.question),
            Text(""),
        ))
        try:
            input_bar = self.query_one(InputBar)
            input_bar.set_ask_mode(message.question)
        except Exception:
            pass

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
            log = self.query_one("#output-log", SelectableRichLog)
            from rich.rule import Rule
            from rich.console import Group
            from rich.text import Text
            log.write(Group(
                Rule("Your Input (queued)", style="yellow", align="left"),
                Text(text),
                Text(""),
            ))
        # Activate any deferred ASK_USER now that the input has been submitted.
        if self._deferred_ask is not None:
            ask = self._deferred_ask
            self._deferred_ask = None
            self._activate_ask(ask)

    def on_session_complete(self, message: SessionComplete) -> None:
        log = self.query_one("#output-log", SelectableRichLog)
        from rich.text import Text
        if message.error:
            log.write(Text(f"Session error: {message.error}", style="bold red"))
        self._session_error = message.error
        self._session_finished = True
        log.write(Text(""))
        log.write(Text("Session ended. Press Ctrl+C to exit.", style="bold magenta"))

    def action_quit_session(self) -> None:
        """Handle Ctrl+C — copy selection if active, otherwise quit."""
        if self.screen.selections:
            selected = self.screen.get_selected_text()
            if selected:
                self.copy_to_clipboard(selected)
                self.notify("Copied to clipboard", timeout=2)
            self.screen.selections = {}
            return
        if self._session_finished:
            self.exit()
            return
        from claude_storm.session import _signal_handler
        from claude_storm.agents import cancel_active
        _signal_handler(0, None)
        # Persist paused status immediately so it survives a hard exit.
        self.config.status = "paused"
        self.config.stop_reason = "interrupted"
        self.config.save()
        cancel_active()
        self.exit()
