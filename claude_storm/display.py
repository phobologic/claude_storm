"""Rich-based live terminal display for brainstorming sessions."""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import Protocol, runtime_checkable

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.rule import Rule
from rich.text import Text

from claude_storm.config import SessionConfig

# Agent color scheme
AGENT_STYLES = {
    "a": {"border": "blue", "title_style": "bold blue"},
    "b": {"border": "green", "title_style": "bold green"},
}


def _truncate_label(label: str, max_len: int = 40) -> str:
    """Take only the first line of a label and truncate to max_len."""
    first_line = label.split("\n")[0].strip()
    if len(first_line) > max_len:
        return first_line[: max_len - 1] + "…"
    return first_line


@runtime_checkable
class DisplayProtocol(Protocol):
    """Protocol defining the display interface for brainstorming sessions.

    Stream Fallback Strategy
    ~~~~~~~~~~~~~~~~~~~~~~~~
    When streaming output arrives via ``show_agent_stream_delta`` callbacks,
    the final text may also be provided in ``show_agent_stream_end(text=...)``.
    Implementations use divergent mechanisms to decide whether to render
    the ``text`` fallback:

    * **PlainDisplay** tracks a ``_stream_has_content`` boolean flag that is
      set to ``True`` by ``show_agent_stream_delta``.  If no deltas arrived,
      the ``text`` kwarg is rendered as a Markdown block.
    * **TextualDisplay** (via ``StormApp``) accumulates delta chunks in a
      ``_stream_parts`` list.  On ``StreamEnd``, if the joined parts are
      empty, it falls back to ``message.text``.
    """

    def show_header(self, config: SessionConfig) -> None: ...
    def show_turn_start(self, config: SessionConfig, agent: str) -> None: ...
    def show_status(self, message: str) -> None: ...
    def show_error(self, message: str) -> None: ...
    def show_warning(self, message: str) -> None: ...
    def show_memory_save(self, agent: str, title: str) -> None: ...
    def show_artifact_save(self, filename: str) -> None: ...
    def show_done_signal(self, agent: str, reason: str) -> None: ...
    def show_done_disagreement(self, agent: str, other: str) -> None: ...
    def show_completion(self, config: SessionConfig) -> None: ...
    def prompt_user(self, question: str) -> str: ...
    def show_proposal(self, agent: str, title: str, proposal_id: str) -> None: ...
    def show_agreement_accepted(self, proposal_id: str, title: str) -> None: ...
    def show_agreement_rejected(self, proposal_id: str, reason: str) -> None: ...
    def show_revision_proposed(
        self, agent: str, agreement_id: str, new_id: str
    ) -> None: ...
    def show_deliverable_compile(self, deliverable_name: str) -> None: ...
    def show_summary(self, summary: str) -> None: ...
    def show_user_nudge(self, text: str) -> None: ...
    def show_input_hint(self) -> None: ...
    def show_agent_stream_start(self, config: SessionConfig, agent: str) -> None: ...
    def show_agent_stream_delta(self, text: str) -> None: ...
    def show_agent_stream_end(self, error: bool = False, text: str = "") -> None:
        """Finalize the streamed response.

        Args:
            error: Whether the stream ended due to an error.
            text: Complete response text, used as fallback when no
                streaming deltas were received.
        """
        ...

    def thinking_status(
        self, label: str, timeout: int = 600, **kwargs: object
    ) -> object: ...


class PlainDisplay:
    """Manages Rich console output for a brainstorming session."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        # Fallback flag: set True by show_agent_stream_delta so
        # show_agent_stream_end knows whether to render the text kwarg.
        self._stream_has_content = False

    def show_header(self, config: SessionConfig) -> None:
        """Display the session header."""
        title = Text("Claude Storm", style="bold magenta")
        self.console.print(title)
        self.console.print(f"Topic: {config.topic}", style="bold")
        if config.goal:
            self.console.print(f"Goal: {config.goal}")
        if config.deliverables:
            self.console.print(f"Deliverables: {', '.join(config.deliverables)}")
        agents = f"{config.agent_label('a')} vs {config.agent_label('b')}"
        self.console.print(f"Agents: {agents}")
        mode_parts = [f"max {config.max_turns} turns"]
        if config.max_minutes:
            mode_parts.append(f"max {config.max_minutes} min")
        if config.auto_complete:
            mode_parts.append("auto-complete")
        if config.interactive:
            mode_parts.append("interactive")
        if config.debug:
            mode_parts.append("debug")
        self.console.print(f"Mode: {', '.join(mode_parts)}")
        self.console.print(f"Session: {config.session_id}")
        self.console.rule()

    def show_turn_start(self, config: SessionConfig, agent: str) -> None:
        """Display a turn start indicator."""
        label = _truncate_label(config.agent_label(agent))
        turn = config.current_turn + 1
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        color = style["border"]
        self.console.print(
            f"\n[{color}]── Turn {turn}/{config.max_turns} · {label} ──[/{color}]"
        )

    def show_status(self, message: str) -> None:
        """Display a status message."""
        self.console.print(f"[dim]{message}[/dim]")

    def show_error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(f"[bold red]Error: {message}[/bold red]")

    def show_warning(self, message: str) -> None:
        """Display a warning message."""
        self.console.print(f"[bold yellow]Warning: {message}[/bold yellow]")

    def show_memory_save(self, agent: str, title: str) -> None:
        """Display a memory save notification."""
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        self.console.print(
            f'[{style["border"]}]  Saved memory: "{title}"[/{style["border"]}]'
        )

    def show_artifact_save(self, filename: str) -> None:
        """Display an artifact save notification."""
        self.console.print(f"[yellow]  Saved artifact: {filename}[/yellow]")

    def show_done_signal(self, agent: str, reason: str) -> None:
        """Display a done signal from an agent."""
        label = agent.upper()
        self.console.print(
            f"[bold magenta]  {label} signals DONE: {reason}[/bold magenta]"
        )

    def show_done_disagreement(self, agent: str, other: str) -> None:
        """Display when an agent disagrees with the other's DONE signal."""
        label = agent.upper()
        other_label = other.upper()
        self.console.print(
            f"[bold yellow]  {label} disagrees"
            f" — {other_label}'s DONE signal"
            f" cleared[/bold yellow]"
        )

    def show_completion(self, config: SessionConfig) -> None:
        """Display session completion info."""
        self.console.rule()
        status_msg = f"Session {config.status} after {config.current_turn} turns."
        if config.stop_reason:
            status_msg += f" (reason: {config.stop_reason})"
        self.console.print(f"[bold]{status_msg}[/bold]")
        if config.stop_error:
            self.console.print(f"[red]Error: {config.stop_error}[/red]")
        self.console.print(f"Session directory: {config.session_dir()}")

    def prompt_user(self, question: str) -> str:
        """Prompt the user for input during interactive mode."""
        self.console.print(Rule("Agent Question", style="yellow", align="left"))
        self.console.print(question)
        self.console.print()
        return self.console.input("[bold yellow]Your response: [/bold yellow]")

    def show_proposal(self, agent: str, title: str, proposal_id: str) -> None:
        """Display a proposal notification."""
        label = agent.upper()
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        self.console.print(
            f"[{style['border']}]  Agent {label} proposed \\[{proposal_id}]: "
            f"{title}[/{style['border']}]"
        )

    def show_agreement_accepted(self, proposal_id: str, title: str) -> None:
        """Display an agreement acceptance notification."""
        self.console.print(
            f"[bold cyan]  Agreement accepted \\[{proposal_id}]: {title}[/bold cyan]"
        )

    def show_agreement_rejected(self, proposal_id: str, reason: str) -> None:
        """Display an agreement rejection notification."""
        self.console.print(
            f"[bold yellow]  Proposal rejected"
            f" \\[{proposal_id}]: {reason}[/bold yellow]"
        )

    def show_revision_proposed(
        self, agent: str, agreement_id: str, new_id: str
    ) -> None:
        """Display a revision proposal notification."""
        label = agent.upper()
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        self.console.print(
            f"[{style['border']}]  Agent {label} proposed revision \\[{new_id}] "
            f"of \\[{agreement_id}][/{style['border']}]"
        )

    def show_deliverable_compile(self, deliverable_name: str) -> None:
        """Display progress during the deliverable compilation phase."""
        self.console.print(
            f"[bold cyan]  Compiling deliverable: {deliverable_name}[/bold cyan]"
        )

    def show_summary(self, summary: str) -> None:
        """Display the final session summary."""
        self.console.print()
        self.console.print(Rule("Session Summary", style="magenta", align="left"))
        self.console.print(Markdown(summary))
        self.console.print()

    def show_user_nudge(self, text: str) -> None:
        """Display a confirmation when user nudge input is injected."""
        self.console.print(Rule("Your Input (injected)", style="yellow", align="left"))
        self.console.print(text)
        self.console.print()

    def show_input_hint(self) -> None:
        """Display a hint at session start about nudge input."""
        self.console.print(
            "[bold yellow]\u25b6 Type at any time to"
            " nudge the conversation.[/bold yellow]"
        )

    def show_agent_stream_start(self, config: SessionConfig, agent: str) -> None:
        """Reset stream state before streaming begins."""
        self._stream_has_content = False

    def show_agent_stream_delta(self, text: str) -> None:
        """Print an incremental text chunk (no trailing newline)."""
        self._stream_has_content = True
        sys.stdout.write(text)
        sys.stdout.flush()

    def show_agent_stream_end(self, error: bool = False, text: str = "") -> None:
        """Finalize the streamed response with a trailing newline.

        Args:
            error: Whether the stream ended due to an error.
            text: Complete response text, used as fallback when no
                streaming deltas were received (``_stream_has_content``
                is False).
        """
        if error:
            self.console.print("\n[bold red][stream interrupted][/bold red]")
        else:
            if not self._stream_has_content and text.strip():
                self.console.print(Markdown(text))
            self.console.print()

    @contextmanager
    def thinking_status(
        self,
        label: str,
        timeout: int = 600,
        **kwargs: object,
    ):
        """Show a live elapsed timer while an agent is working."""
        start = time.monotonic()
        short_label = _truncate_label(label)

        # Non-interactive: use Live timer display
        def get_renderable():
            elapsed = int(time.monotonic() - start)
            return Text(
                f"  {short_label} is thinking... ({elapsed}s / {timeout}s)",
                style="bold",
            )

        with Live(
            get_renderable(),
            console=self.console,
            refresh_per_second=1,
            get_renderable=get_renderable,
            transient=True,
        ):
            yield


class TextualDisplay:
    """Display implementation that posts messages to a Textual StormApp."""

    def __init__(self, app: object) -> None:
        self._app = app  # StormApp instance

    def _post(self, message: object) -> None:
        self._app.post_message(message)  # type: ignore[union-attr]

    def _show(self, renderable: object) -> None:
        """Post a renderable to the TUI output log."""
        from claude_storm.messages import ShowRenderable

        self._post(ShowRenderable(renderable))

    def show_header(self, config: SessionConfig) -> None:
        # No-op: the #header-bar widget already displays session info.
        pass

    def show_turn_start(self, config: SessionConfig, agent: str) -> None:
        label = _truncate_label(config.agent_label(agent))
        turn = config.current_turn + 1
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        color = style["border"]
        self._show(
            Text(f"\n── Turn {turn}/{config.max_turns} · {label} ──", style=color)
        )

    def show_status(self, message: str) -> None:
        self._show(Text(message, style="dim"))

    def show_error(self, message: str) -> None:
        self._show(Text(f"Error: {message}", style="bold red"))

    def show_warning(self, message: str) -> None:
        self._show(Text(f"Warning: {message}", style="bold yellow"))

    def show_memory_save(self, agent: str, title: str) -> None:
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        self._show(Text(f'  Saved memory: "{title}"', style=style["border"]))

    def show_artifact_save(self, filename: str) -> None:
        self._show(Text(f"  Saved artifact: {filename}", style="yellow"))

    def show_done_signal(self, agent: str, reason: str) -> None:
        label = agent.upper()
        self._show(Text(f"  {label} signals DONE: {reason}", style="bold magenta"))

    def show_done_disagreement(self, agent: str, other: str) -> None:
        label = agent.upper()
        other_label = other.upper()
        self._show(
            Text(
                f"  {label} disagrees \u2014 {other_label}'s DONE signal cleared",
                style="bold yellow",
            )
        )

    def show_completion(self, config: SessionConfig) -> None:
        status_msg = f"Session {config.status} after {config.current_turn} turns."
        if config.stop_reason:
            status_msg += f" (reason: {config.stop_reason})"
        self._show(Text(status_msg, style="bold"))
        if config.stop_error:
            self._show(Text(f"Error: {config.stop_error}", style="red"))
        self._show(Text(f"Session directory: {config.session_dir()}"))

    def prompt_user(self, question: str) -> str:
        from claude_storm.messages import RequestUserInput
        from claude_storm.session import _shutdown_requested

        msg = RequestUserInput(question)
        self._post(msg)
        while not msg.event.wait(timeout=0.5):
            if _shutdown_requested:
                return ""
        return msg.response

    def show_proposal(self, agent: str, title: str, proposal_id: str) -> None:
        label = agent.upper()
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        self._show(
            Text(
                f"  Agent {label} proposed [{proposal_id}]: {title}",
                style=style["border"],
            )
        )

    def show_agreement_accepted(self, proposal_id: str, title: str) -> None:
        self._show(
            Text(f"  Agreement accepted [{proposal_id}]: {title}", style="bold cyan")
        )

    def show_agreement_rejected(self, proposal_id: str, reason: str) -> None:
        self._show(
            Text(
                f"  Proposal rejected [{proposal_id}]: {reason}",
                style="bold yellow",
            )
        )

    def show_revision_proposed(
        self, agent: str, agreement_id: str, new_id: str
    ) -> None:
        label = agent.upper()
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        self._show(
            Text(
                f"  Agent {label} proposed revision [{new_id}] of [{agreement_id}]",
                style=style["border"],
            )
        )

    def show_deliverable_compile(self, deliverable_name: str) -> None:
        self._show(
            Text(f"  Compiling deliverable: {deliverable_name}", style="bold cyan")
        )

    def show_summary(self, summary: str) -> None:
        self._show(
            Group(
                Rule("Session Summary", style="magenta", align="left"),
                Markdown(summary),
                Text(""),
            )
        )

    def show_user_nudge(self, text: str) -> None:
        self._show(
            Group(
                Rule("Your Input (injected)", style="yellow", align="left"),
                Text(text),
                Text(""),
            )
        )

    def show_input_hint(self) -> None:
        # No-op: the InputBar placeholder already displays this hint.
        pass

    def show_agent_stream_start(self, config: SessionConfig, agent: str) -> None:
        """Post a StreamStart message to the TUI."""
        from claude_storm.messages import StreamStart, UpdateThinking

        label = _truncate_label(config.agent_label(agent))
        self._post(StreamStart())
        self._post(UpdateThinking(label, timeout=config.agent_timeout))

    def show_agent_stream_delta(self, text: str) -> None:
        """Post a StreamDelta message to the TUI."""
        from claude_storm.messages import StreamDelta

        self._post(StreamDelta(text))

    def show_agent_stream_end(self, error: bool = False, text: str = "") -> None:
        """Post a StreamEnd message to the TUI.

        Args:
            error: Whether the stream ended due to an error.
            text: Complete response text, forwarded via ``StreamEnd``
                so the TUI can fall back to it when ``_stream_parts``
                is empty.
        """
        from claude_storm.messages import ClearThinking, StreamEnd

        self._post(ClearThinking(0))
        self._post(StreamEnd(error=error, text=text))

    @contextmanager
    def thinking_status(
        self,
        label: str,
        timeout: int = 600,
        **kwargs: object,
    ):
        """Post UpdateThinking/ClearThinking messages."""
        from claude_storm.messages import ClearThinking, UpdateThinking

        start = time.monotonic()
        short_label = _truncate_label(label)
        self._post(UpdateThinking(short_label, timeout=timeout))
        try:
            yield
        finally:
            elapsed = int(time.monotonic() - start)
            self._post(ClearThinking(elapsed))


# Backward-compatible alias
Display = PlainDisplay
