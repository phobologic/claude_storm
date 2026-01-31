"""Rich-based live terminal display for brainstorming sessions."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from claude_storm.config import SessionConfig

# Agent color scheme
AGENT_STYLES = {
    "a": {"border": "blue", "title_style": "bold blue"},
    "b": {"border": "green", "title_style": "bold green"},
}


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
        label = config.agent_label(agent)
        turn = config.current_turn + 1
        self.console.print(
            f"\n[dim]--- Turn {turn}/{config.max_turns} - {label} ---[/dim]"
        )

    def show_agent_response(
        self, config: SessionConfig, agent: str, text: str
    ) -> None:
        """Display an agent's response in a colored panel."""
        label = config.agent_label(agent)
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
