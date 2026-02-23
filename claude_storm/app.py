"""Textual-based TUI application for Claude Storm."""

from __future__ import annotations

import contextlib
from collections import deque
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import Static

from claude_storm.config import SessionConfig
from claude_storm.messages import (
    ClearThinking,
    RequestUserInput,
    SessionComplete,
    ShowRenderable,
    StreamDelta,
    StreamEnd,
    StreamStart,
    UpdateProgress,
    UpdateThinking,
    UpdateThinkingLabel,
)
from claude_storm.widgets import (
    GrowingTextArea,
    InputBar,
    SelectableRichLog,
    ThinkingBar,
)

_TOPIC_SUMMARY_MAX_LEN = 88


class StormApp(App):
    """Textual app for running a Claude Storm brainstorming session."""

    CSS_PATH = "storm_app.tcss"
    TITLE = "Claude Storm"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+c", "quit_session", "Quit", priority=True),
        Binding("end", "scroll_to_bottom", "Jump to live", show=False),
        Binding("pageup", "scroll_log_page_up", "Scroll up", show=False),
        Binding("shift+up", "scroll_log_page_up", "Scroll up", show=False),
        Binding("shift+down", "scroll_log_page_down", "Scroll down", show=False),
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
        self._stream_start: int = 0
        self._stream_buffer: str = ""
        self._stream_log: SelectableRichLog | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="header-bar")
        yield SelectableRichLog(id="output-log", highlight=True, markup=True, wrap=True)
        yield Static(
            "▼ Press End to jump to live output", id="scroll-indicator", markup=False
        )
        yield Static(
            "  ↑/↓ scroll  │  shift+↑/↓ page  │  End live  │  ^C quit",
            id="hints-bar",
            markup=False,
        )
        yield ThinkingBar()
        if self.config.interactive:
            yield InputBar()

    def on_mount(self) -> None:
        """Set up header and start the session worker."""
        header = self.query_one("#header-bar", Static)
        mode_parts = []
        if self.config.max_turns is not None:
            mode_parts.append(f"max {self.config.max_turns} turns")
        if self.config.max_minutes:
            mode_parts.append(f"max {self.config.max_minutes} min")
        if self.config.auto_complete:
            mode_parts.append("auto-complete")
        if self.config.interactive:
            mode_parts.append("interactive")
        # Two-row header: row 1 = app name + session ID + mode info,
        # row 2 = topic (truncated to _TOPIC_SUMMARY_MAX_LEN chars).
        topic_summary = self.config.topic.split("\n")[0].strip()
        if len(topic_summary) > _TOPIC_SUMMARY_MAX_LEN:
            topic_summary = topic_summary[: _TOPIC_SUMMARY_MAX_LEN - 1] + "…"
        header.update(
            f"[bold magenta]Claude Storm[/bold magenta]  "
            f"[dim italic]{self.config.session_id}[/dim italic]  "
            f"[dim]{', '.join(mode_parts)}[/dim]\n"
            f"[dim]Topic:[/dim] {topic_summary}"
        )
        self.run_worker(self._session_worker, thread=True)
        if self.config.interactive:
            # Start with the log focused (watch mode); input gets focus on ASK_USER.
            self.set_focus(self.query_one("#output-log", SelectableRichLog))

    def _session_worker(self) -> None:
        """Run the session loop in a worker thread."""
        from claude_storm.display import TextualDisplay
        from claude_storm.session import run_session

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

    def on_update_thinking_label(self, message: UpdateThinkingLabel) -> None:
        bar = self.query_one(ThinkingBar)
        bar.update_label(message.label)

    def on_update_progress(self, message: UpdateProgress) -> None:
        bar = self.query_one(ThinkingBar)
        bar.update_progress(
            message.turn,
            message.max_turns,
            message.elapsed_s,
            message.max_minutes,
        )

    def on_selectable_rich_log_following_changed(
        self, message: SelectableRichLog.FollowingChanged
    ) -> None:
        indicator = self.query_one("#scroll-indicator", Static)
        indicator.display = not message.following

    def action_scroll_to_bottom(self) -> None:
        """Jump to the bottom of the log and re-engage scroll-lock."""
        log = self.query_one("#output-log", SelectableRichLog)
        log.scroll_to_bottom()

    def action_scroll_log_page_up(self) -> None:
        """Scroll the log up one page and disengage scroll-lock."""
        log = self.query_one("#output-log", SelectableRichLog)
        log.following = False
        log.scroll_page_up(animate=False)

    def action_scroll_log_page_down(self) -> None:
        """Scroll the log down one page; re-engage scroll-lock if at bottom."""
        log = self.query_one("#output-log", SelectableRichLog)
        log._user_scrolling = True
        log.scroll_page_down(animate=False)
        log.call_after_refresh(log._maybe_reengage_following)

    def on_stream_start(self, message: StreamStart) -> None:
        log = self.query_one("#output-log", SelectableRichLog)
        self._stream_start = len(log.lines)
        self._stream_buffer = ""
        self._stream_log = log

    def on_stream_delta(self, message: StreamDelta) -> None:
        from rich.text import Text

        log = self._stream_log or self.query_one("#output-log", SelectableRichLog)
        self._stream_buffer += message.text
        # Flush one log entry per complete line so RichLog.write() doesn't
        # create a new visual row for every tiny delta chunk.
        while "\n" in self._stream_buffer:
            line, self._stream_buffer = self._stream_buffer.split("\n", 1)
            log.write(Text(line))

    def on_stream_end(self, message: StreamEnd) -> None:
        from rich.markdown import Markdown
        from rich.text import Text

        log = self._stream_log or self.query_one("#output-log", SelectableRichLog)
        log.truncate_to(self._stream_start)

        if message.error:
            log.write(Text("[stream interrupted]", style="bold red"))
        elif message.text.strip():
            log.write(Markdown(message.text))

        log.write(Text(""))
        self._stream_start = 0
        self._stream_buffer = ""
        self._stream_log = None

    def on_request_user_input(self, message: RequestUserInput) -> None:
        # If the user is mid-typing, defer the ask until they submit.
        try:
            input_bar = self.query_one(InputBar)
            ta = input_bar.query_one(GrowingTextArea)
            if ta.text.strip():
                self._deferred_ask = message
                return
        except NoMatches:
            # No InputBar (non-interactive) — unblock with empty response
            message.response = ""
            message.event.set()
            return
        self._activate_ask(message)

    def _activate_ask(self, message: RequestUserInput) -> None:
        """Display an agent question and switch the input bar to ask mode."""
        self._ask_request = message
        log = self.query_one("#output-log", SelectableRichLog)
        from rich.console import Group
        from rich.rule import Rule
        from rich.text import Text

        log.write(
            Group(
                Rule("Agent Question", style="yellow", align="left"),
                Text(message.question),
                Text(""),
            )
        )
        try:
            input_bar = self.query_one(InputBar)
            input_bar.set_ask_mode(message.question)
        except NoMatches:
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
            except NoMatches:
                pass
        elif text:
            # Nudge input
            self.nudge_queue.append(text)
            log = self.query_one("#output-log", SelectableRichLog)
            from rich.console import Group
            from rich.rule import Rule
            from rich.text import Text

            log.write(
                Group(
                    Rule("Your Input (queued)", style="yellow", align="left"),
                    Text(text),
                    Text(""),
                )
            )
        # Activate any deferred ASK_USER now that the input has been submitted.
        if self._deferred_ask is not None:
            ask = self._deferred_ask
            self._deferred_ask = None
            self._activate_ask(ask)
        # Return focus to the log (watch mode) unless an ASK_USER question is active.
        if self._ask_request is None:
            with contextlib.suppress(NoMatches):
                self.set_focus(self.query_one("#output-log", SelectableRichLog))

    def on_session_complete(self, message: SessionComplete) -> None:
        log = self.query_one("#output-log", SelectableRichLog)
        from rich.text import Text

        if message.error:
            log.write(Text(f"Session error: {message.error}", style="bold red"))
        self._session_error = message.error
        self._session_finished = True
        log.write(Text(""))
        if self.config.status == "paused":
            hint = "Session paused \u2014 Press Ctrl+C to exit."
        else:
            hint = "Session ended \u2014 Press Ctrl+C to exit."
        log.write(Text(hint, style="bold magenta"))

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
        from claude_storm.agents import cancel_active
        from claude_storm.session import _signal_handler

        _signal_handler(0, None)
        # Persist paused status immediately so it survives a hard exit.
        self.config.status = "paused"
        self.config.stop_reason = "interrupted"
        self.config.save()
        cancel_active()
        self.exit()
