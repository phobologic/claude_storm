"""Main CLI application for Claude Storm."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from claude_storm.config import SessionConfig, validate_reference_dirs
from claude_storm.display import Display
from claude_storm.project import (
    STORM_CONFIG_FILENAME,
    get_storms_dir,
    load_project_config,
    migrate_config,
    scaffold_config,
)
from claude_storm.session import run_session

app = typer.Typer(
    name="storm",
    help="Claude Storm - Dual-agent brainstorming system",
    no_args_is_help=True,
)

# Debug mode flag (set by --debug callback)
_debug_mode = False


@app.callback()
def main(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """Claude Storm - Dual-agent brainstorming system."""
    global _debug_mode
    _debug_mode = debug


@app.command()
def init(
    topic: str | None = typer.Option(
        None, "--topic", "-t", help="Pre-fill topic in the config"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing storm.toml"
    ),
    update: bool = typer.Option(
        False, "--update", "-u", help="Migrate existing config to latest schema"
    ),
) -> None:
    """Initialize a storm.toml config file in the current directory."""
    console = Console()

    if update:
        config_file = Path.cwd() / STORM_CONFIG_FILENAME
        if not config_file.exists():
            console.print(
                f"[bold red]No {STORM_CONFIG_FILENAME} found to update.[/bold red]"
            )
            raise typer.Exit(1)
        messages = migrate_config(config_file)
        if messages:
            for msg in messages:
                console.print(f"[yellow]{msg}[/yellow]")
        else:
            console.print("Config is already up to date.")
        return

    try:
        path = scaffold_config(Path.cwd(), topic=topic, force=force)
        console.print(f"Created {path}")
    except FileExistsError as e:
        console.print(f"[bold red]{e}[/bold red]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1) from None


def _load_and_migrate_toml(
    config_path: Path | None,
    console: Console,
) -> tuple[dict, Path | None]:
    """Load and migrate a TOML config file.

    Resolves the config path (auto-detecting storm.toml in CWD when no
    explicit path is given), loads the config, runs migration, and applies
    the ``reference_dir`` → ``reference_dirs`` compatibility shim.

    Args:
        config_path: Explicit path to storm.toml, or None to auto-detect.
        console: Rich console for printing migration messages.

    Returns:
        Tuple of (config dict, resolved config path). Returns ({}, None)
        when no config file is found.
    """
    resolved_config_path = config_path
    if resolved_config_path is None:
        default_toml = Path.cwd() / STORM_CONFIG_FILENAME
        if default_toml.exists():
            resolved_config_path = default_toml

    if resolved_config_path is None:
        return {}, None

    try:
        toml_config = load_project_config(resolved_config_path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1) from None

    # Run migration on the config file
    migration_messages = migrate_config(resolved_config_path)
    for msg in migration_messages:
        console.print(f"[yellow]{msg}[/yellow]")

    # Reload if migrated
    if migration_messages:
        toml_config = load_project_config(resolved_config_path)

    # Migrate old reference_dir key from TOML to reference_dirs
    if "reference_dir" in toml_config and "reference_dirs" not in toml_config:
        old_val = toml_config.pop("reference_dir")
        if old_val:
            toml_config["reference_dirs"] = [old_val]

    return toml_config, resolved_config_path


def _resolve_start_config(
    *,
    topic: str | None,
    config_path: Path | None,
    goal: str | None,
    roles: list[str] | None,
    max_turns: int | None,
    max_minutes: int | None,
    auto_complete: bool | None,
    interactive: bool | None,
    model: str | None,
    deliverable: list[str] | None,
    reference_dir: list[Path] | None,
    agent_timeout: int | None,
    web_search: bool | None,
    debug: bool,
    console: Console,
) -> SessionConfig:
    """Build a SessionConfig by merging defaults, TOML, and CLI overrides.

    Implements the three-layer config merge: hardcoded defaults → TOML values
    → CLI flags. Validates reference directories and topic presence.

    Args:
        topic: Brainstorming topic from CLI argument.
        config_path: Explicit path to storm.toml, or None.
        goal: Desired outcome from CLI flag.
        roles: Agent roles from CLI flag (up to two).
        max_turns: Maximum turns from CLI flag.
        max_minutes: Time limit from CLI flag.
        auto_complete: Auto-complete toggle from CLI flag.
        interactive: Interactive toggle from CLI flag.
        model: Claude model from CLI flag.
        deliverable: Expected output documents from CLI flag.
        reference_dir: Reference directory paths from CLI flag.
        agent_timeout: Per-turn timeout from CLI flag.
        debug: Whether debug mode is enabled.
        console: Rich console for error messages.

    Returns:
        A fully configured SessionConfig ready for session launch.
    """
    # Layer 1: Defaults
    merged: dict = {
        "topic": None,
        "goal": "",
        "role_a": None,
        "role_b": None,
        "max_turns": 20,
        "max_minutes": None,
        "auto_complete": False,
        "interactive": False,
        "model": "sonnet",
        "deliverables": [],
        "reference_dirs": [],
        "truncate_conversation": True,
        "agent_timeout": 600,
        "web_search": False,
    }

    # Layer 2: TOML config (if available)
    toml_config, resolved_config_path = _load_and_migrate_toml(config_path, console)
    for key in merged:
        if key in toml_config:
            merged[key] = toml_config[key]

    # Layer 3: CLI overrides (only non-None values)
    if topic is not None:
        merged["topic"] = topic
    if goal is not None:
        merged["goal"] = goal
    if roles:
        if len(roles) >= 1:
            merged["role_a"] = roles[0]
        if len(roles) >= 2:
            merged["role_b"] = roles[1]
    if max_turns is not None:
        merged["max_turns"] = max_turns
    if max_minutes is not None:
        merged["max_minutes"] = max_minutes
    if auto_complete is not None:
        merged["auto_complete"] = auto_complete
    if interactive is not None:
        merged["interactive"] = interactive
    if model is not None:
        merged["model"] = model
    if deliverable:
        merged["deliverables"] = list(deliverable)
    if reference_dir:
        merged["reference_dirs"] = [str(p) for p in reference_dir]
    if agent_timeout is not None:
        merged["agent_timeout"] = agent_timeout
    if web_search is not None:
        merged["web_search"] = web_search

    # Validate: each reference dir must exist
    try:
        merged["reference_dirs"] = validate_reference_dirs(merged["reference_dirs"])
    except ValueError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1) from None

    # Validate: topic is required
    if not merged["topic"]:
        console.print(
            "[bold red]No topic provided. "
            "Pass a topic argument or create a storm.toml.[/bold red]"
        )
        raise typer.Exit(1)

    # Resolve storms dir
    storms_dir = str(get_storms_dir(resolved_config_path))

    return SessionConfig.create(
        topic=merged["topic"],
        goal=merged["goal"],
        role_a=merged["role_a"],
        role_b=merged["role_b"],
        max_turns=merged["max_turns"],
        max_minutes=merged["max_minutes"],
        auto_complete=merged["auto_complete"],
        interactive=merged["interactive"],
        debug=debug,
        model=merged["model"],
        deliverables=merged["deliverables"],
        reference_dirs=merged["reference_dirs"],
        truncate_conversation=merged["truncate_conversation"],
        agent_timeout=merged["agent_timeout"],
        web_search=merged["web_search"],
        storms_dir=storms_dir,
    )


@app.command()
def start(
    topic: str | None = typer.Argument(default=None, help="The brainstorming topic"),
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to storm.toml"
    ),
    goal: str | None = typer.Option(
        None,
        "--goal",
        "-g",
        help="Desired outcome or success criterion (describes direction/quality)",
    ),
    roles: list[str] | None = typer.Option(
        None, "--roles", "-r", help="Agent roles (provide two)"
    ),
    max_turns: int | None = typer.Option(
        None, "--max-turns", "-t", help="Maximum turns"
    ),
    auto_complete: bool | None = typer.Option(
        None, "--auto-complete/--no-auto-complete", help="Let agents decide when done"
    ),
    max_minutes: int | None = typer.Option(
        None, "--max-minutes", "-m", help="Wall-clock time limit"
    ),
    model: str | None = typer.Option(None, "--model", help="Claude model to use"),
    interactive: bool | None = typer.Option(
        None,
        "--interactive/--no-interactive",
        help="Allow agents to ask user questions",
    ),
    deliverable: list[str] | None = typer.Option(
        None, "--deliverable", "-d", help="Expected output document (repeatable)"
    ),
    reference_dir: list[Path] | None = typer.Option(
        None,
        "--reference-dir",
        "--ref",
        help="Read-only directory of reference materials (repeatable)",
    ),
    agent_timeout: int | None = typer.Option(
        None,
        "--agent-timeout",
        help="Per-turn agent timeout in seconds (default: 600)",
    ),
    web_search: bool | None = typer.Option(
        None,
        "--web-search/--no-web-search",
        help="Allow agents to search and fetch web pages",
    ),
) -> None:
    """Start a new brainstorming session."""
    console = Console()
    config = _resolve_start_config(
        topic=topic,
        config_path=config_path,
        goal=goal,
        roles=roles,
        max_turns=max_turns,
        max_minutes=max_minutes,
        auto_complete=auto_complete,
        interactive=interactive,
        model=model,
        deliverable=deliverable,
        reference_dir=reference_dir,
        agent_timeout=agent_timeout,
        web_search=web_search,
        debug=_debug_mode,
        console=console,
    )

    if sys.stdout.isatty():
        from claude_storm.app import StormApp

        tui = StormApp(config)
        tui.run()
        console.print(f"\nSession directory: [dim]{config.session_dir()}[/dim]")
        if config.status == "paused":
            console.print(
                f"Session paused. Resume with: "
                f"[bold]storm resume {config.session_id}[/bold]"
            )
    else:
        display = Display()
        run_session(config, display)


@app.command()
def resume(
    session_id: str = typer.Argument(help="Session ID to resume"),
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to storm.toml (to locate .storms/)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force resume even if session is not paused (e.g. after a hard kill)",
    ),
) -> None:
    """Resume a paused brainstorming session."""
    console = Console()
    storms_dir = str(get_storms_dir(config_path))

    try:
        config = SessionConfig.load(session_id, storms_dir=storms_dir)
    except FileNotFoundError:
        console.print(f"[bold red]Session not found: {session_id}[/bold red]")
        raise typer.Exit(1) from None

    if config.status == "completed":
        console.print(
            f"[bold red]Session {session_id} is completed "
            f"and cannot be resumed[/bold red]"
        )
        raise typer.Exit(1)

    if config.status != "paused" and not force:
        console.print(
            f"[bold red]Session {session_id} is {config.status}, not paused[/bold red]"
        )
        console.print(
            "[dim]Use --force to resume anyway (e.g. after a hard kill)[/dim]"
        )
        raise typer.Exit(1)

    config.status = "active"
    if _debug_mode:
        config.debug = True

    if sys.stdout.isatty():
        from claude_storm.app import StormApp

        tui = StormApp(config, resume=True)
        tui.run()
        console.print(f"\nSession directory: [dim]{config.session_dir()}[/dim]")
        if config.status == "paused":
            console.print(
                f"Session paused. Resume with: "
                f"[bold]storm resume {config.session_id}[/bold]"
            )
    else:
        display = Display()
        run_session(config, display)


@app.command(name="list")
def list_sessions(
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to storm.toml (to locate .storms/)"
    ),
) -> None:
    """List all brainstorming sessions."""
    console = Console()
    storms_dir = Path(str(get_storms_dir(config_path)))

    if not storms_dir.exists():
        console.print("[dim]No sessions found.[/dim]")
        return

    sessions = sorted(storms_dir.iterdir())
    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    for session_dir in sessions:
        config_file = session_dir / "session.json"
        if not config_file.exists():
            continue
        try:
            config = SessionConfig.load(session_dir.name, storms_dir=str(storms_dir))
        except Exception:
            continue

        status_style = {
            "active": "yellow",
            "paused": "blue",
            "completed": "green",
        }.get(config.status, "dim")

        console.print(
            f"  [{status_style}]{config.status:>10}[/{status_style}]  "
            f"[bold]{config.session_id}[/bold]  "
            f"{config.topic[:50]}  "
            f"[dim]({config.current_turn}/{config.max_turns} turns)[/dim]"
        )


@app.command()
def show(
    session_id: str = typer.Argument(help="Session ID to display"),
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to storm.toml (to locate .storms/)"
    ),
) -> None:
    """Show details of a brainstorming session."""
    console = Console()
    storms_dir = str(get_storms_dir(config_path))

    try:
        config = SessionConfig.load(session_id, storms_dir=storms_dir)
    except FileNotFoundError:
        console.print(f"[bold red]Session not found: {session_id}[/bold red]")
        raise typer.Exit(1) from None

    console.print(f"[bold]Session: {config.session_id}[/bold]")
    console.print(f"Topic: {config.topic}")
    if config.goal:
        console.print(f"Goal: {config.goal}")
    console.print(f"Agents: {config.agent_label('a')} vs {config.agent_label('b')}")
    console.print(f"Status: {config.status}")
    if config.stop_reason:
        console.print(f"Stop reason: {config.stop_reason}")
    if config.stop_error:
        console.print(f"Stop error: {config.stop_error}")
    console.print(f"Turns: {config.current_turn}/{config.max_turns}")
    console.print(f"Model: {config.model}")
    if config.deliverables:
        console.print(f"Deliverables: {', '.join(config.deliverables)}")
    console.print(f"Started: {config.started_at}")
    if config.ended_at:
        console.print(f"Ended: {config.ended_at}")
    duration_s = config.total_duration_s
    if duration_s is not None:
        from claude_storm.config import format_duration

        console.print(f"Duration: {format_duration(duration_s)}")
    # Show cost/token totals from watermarks
    from claude_storm.display import _format_session_totals

    totals = _format_session_totals(config, duration_s=duration_s)
    if totals:
        console.print(totals)
    console.print(f"Directory: {config.session_dir()}")

    # Show conversation if it exists
    conv_path = config.session_dir() / "conversation.md"
    if conv_path.exists():
        console.rule("Conversation")
        from rich.markdown import Markdown

        console.print(Markdown(conv_path.read_text()))

    # Show summary if it exists
    summary_path = config.session_dir() / "summary.md"
    if summary_path.exists():
        console.rule("Summary")
        from rich.markdown import Markdown

        console.print(Markdown(summary_path.read_text()))
