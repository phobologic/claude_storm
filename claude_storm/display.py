"""Rich-based live terminal display for brainstorming sessions."""

from __future__ import annotations

import time
from contextlib import contextmanager

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from typing import TYPE_CHECKING

from claude_storm.config import SessionConfig

if TYPE_CHECKING:
    from claude_storm.input_buffer import InputBuffer

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


class Display:
    """Manages Rich console output for a brainstorming session."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def show_header(self, config: SessionConfig) -> None:
        """Display the session header."""
        title = Text("Claude Storm", style="bold magenta")
        self.console.print(title)
        self.console.print(f"Topic: {config.topic}", style="bold")
        if config.goal:
            self.console.print(f"Goal: {config.goal}")
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

    def show_agent_response(
        self, config: SessionConfig, agent: str, text: str
    ) -> None:
        """Display an agent's response in a colored panel."""
        label = _truncate_label(config.agent_label(agent))
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        panel = Panel(
            Markdown(text),
            title=label,
            border_style=style["border"],
            title_align="left",
        )
        self.console.print(panel)

    def show_status(self, message: str) -> None:
        """Display a status message."""
        self.console.print(f"[dim]{message}[/dim]")

    def show_error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(f"[bold red]Error: {message}[/bold red]")

    def show_memory_save(self, agent: str, title: str) -> None:
        """Display a memory save notification."""
        style = AGENT_STYLES.get(agent, AGENT_STYLES["a"])
        self.console.print(
            f"[{style['border']}]  Saved memory: \"{title}\"[/{style['border']}]"
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
            f"[bold yellow]  {label} disagrees — {other_label}'s DONE signal cleared[/bold yellow]"
        )

    def show_completion(self, config: SessionConfig) -> None:
        """Display session completion info."""
        self.console.rule()
        self.console.print(
            f"[bold]Session complete after {config.current_turn} turns.[/bold]"
        )
        self.console.print(
            f"Session directory: {config.session_dir()}"
        )

    def prompt_user(self, question: str) -> str:
        """Prompt the user for input during interactive mode."""
        self.console.print(
            Panel(question, title="Agent Question", border_style="yellow")
        )
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
            f"[bold yellow]  Proposal rejected \\[{proposal_id}]: {reason}[/bold yellow]"
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
        panel = Panel(
            Markdown(summary),
            title="Session Summary",
            border_style="magenta",
            title_align="left",
        )
        self.console.print(panel)

    def show_user_nudge(self, text: str) -> None:
        """Display a confirmation panel when user nudge input is injected."""
        panel = Panel(
            text,
            title="Your Input (injected)",
            border_style="yellow",
            title_align="left",
        )
        self.console.print(panel)

    def show_input_hint(self) -> None:
        """Display a hint at session start about nudge input."""
        self.console.print("[bold yellow]▶ Type at any time to nudge the conversation.[/bold yellow]")

    @contextmanager
    def thinking_status(
        self,
        label: str,
        timeout: int = 300,
        input_buffer: InputBuffer | None = None,
    ):
        """Show a live elapsed timer while an agent is working."""
        start = time.monotonic()
        short_label = _truncate_label(label)

        if input_buffer is not None:
            # Interactive mode: static prompt to avoid Live overwriting typed input
            style = AGENT_STYLES.get("a", AGENT_STYLES["a"])
            # Try to detect agent color from label
            for key, s in AGENT_STYLES.items():
                if key in label.lower():
                    style = s
                    break
            color = style["border"]
            self.console.print(
                f"[yellow]▶[/yellow] [bold {color}]{short_label} thinking "
                f"— type and press Enter to nudge[/bold {color}]"
            )
            try:
                yield
            finally:
                elapsed = int(time.monotonic() - start)
                self.console.print(f"[dim]  ({elapsed}s)[/dim]")
        else:
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
