"""Main CLI application for Claude Storm."""

from __future__ import annotations

import re
import signal
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional
from uuid import uuid4

import typer
from rich.console import Console

from claude_storm.agents import invoke_agent, AgentResponse
from claude_storm.config import SessionConfig
from claude_storm.debug import (
    write_debug_entry,
    write_debug_request,
    write_debug_response,
)
from claude_storm.display import Display, DisplayProtocol
from claude_storm.memory import (
    format_memory_index,
    format_recent_memories,
    format_search_results,
    save_memory,
)
from claude_storm.project import (
    load_project_config,
    scaffold_config,
    get_storms_dir,
    migrate_config,
    STORM_CONFIG_FILENAME,
)
from claude_storm.agreements import (
    accept_proposal,
    create_proposal,
    format_agreements_for_prompt,
    reject_proposal,
)
from claude_storm.prompts import (
    build_system_prompt,
    build_turn_prompt,
    build_summary_prompt,
    build_deliverable_prompt,
)

app = typer.Typer(
    name="storm",
    help="Claude Storm - Dual-agent brainstorming system",
    no_args_is_help=True,
)

# Graceful shutdown flag
_shutdown_requested = False

# Debug mode flag (set by --debug callback)
_debug_mode = False


def _signal_handler(signum: int, frame: object) -> None:
    global _shutdown_requested
    _shutdown_requested = True


def _parse_directives(text: str) -> dict:
    """Parse structured directives from agent response text.

    Returns a dict with:
        memories: list of (title, tags, content)
        memory_searches: list of query strings
        artifacts: list of (filename, content)
        done: reason string or None
        ask_user: question string or None
        clean_text: text with directives removed
    """
    result: dict = {
        "memories": [],
        "memory_searches": [],
        "artifacts": [],
        "done": None,
        "ask_user": None,
        "proposals": [],
        "accepts": [],
        "rejects": [],
        "revisions": [],
        "clean_text": text,
    }

    # Parse [MEMORY title="..." tags="..."]content[/MEMORY]
    memory_pattern = re.compile(
        r'\[MEMORY\s+title="([^"]+)"\s+tags="([^"]*)"\](.*?)\[/MEMORY\]',
        re.DOTALL,
    )
    for match in memory_pattern.finditer(text):
        title = match.group(1)
        tags = [t.strip() for t in match.group(2).split(",") if t.strip()]
        content = match.group(3).strip()
        result["memories"].append((title, tags, content))

    # Parse [MEMORY_SEARCH query="..."]
    search_pattern = re.compile(r'\[MEMORY_SEARCH\s+query="([^"]+)"\]')
    for match in search_pattern.finditer(text):
        result["memory_searches"].append(match.group(1))

    # Parse [ARTIFACT filename="..."]content[/ARTIFACT]
    artifact_pattern = re.compile(
        r'\[ARTIFACT\s+filename="([^"]+)"\](.*?)\[/ARTIFACT\]',
        re.DOTALL,
    )
    for match in artifact_pattern.finditer(text):
        result["artifacts"].append((match.group(1), match.group(2).strip()))

    # Parse [DONE] or [DONE reason="..."]
    done_pattern = re.compile(r'\[DONE(?:\s+reason="([^"]+)")?\]')
    done_match = done_pattern.search(text)
    if done_match:
        result["done"] = done_match.group(1) or "complete"

    # Parse [ASK_USER]question[/ASK_USER]
    ask_pattern = re.compile(r"\[ASK_USER\](.*?)\[/ASK_USER\]", re.DOTALL)
    ask_match = ask_pattern.search(text)
    if ask_match:
        result["ask_user"] = ask_match.group(1).strip()

    # Parse [PROPOSE title="..."]content[/PROPOSE]
    propose_pattern = re.compile(
        r'\[PROPOSE\s+title="([^"]+)"\](.*?)\[/PROPOSE\]',
        re.DOTALL,
    )
    for match in propose_pattern.finditer(text):
        result["proposals"].append((match.group(1), match.group(2).strip()))

    # Parse [ACCEPT id="..."]
    accept_pattern = re.compile(r'\[ACCEPT\s+id="([^"]+)"\]')
    for match in accept_pattern.finditer(text):
        result["accepts"].append(match.group(1))

    # Parse [REJECT id="..." reason="..."]
    reject_pattern = re.compile(r'\[REJECT\s+id="([^"]+)"\s+reason="([^"]+)"\]')
    for match in reject_pattern.finditer(text):
        result["rejects"].append((match.group(1), match.group(2)))

    # Parse [REVISE id="..."]content[/REVISE]
    revise_pattern = re.compile(
        r'\[REVISE\s+id="([^"]+)"\](.*?)\[/REVISE\]',
        re.DOTALL,
    )
    for match in revise_pattern.finditer(text):
        result["revisions"].append((match.group(1), match.group(2).strip()))

    # Clean text: remove all directives
    clean = text
    clean = memory_pattern.sub("", clean)
    clean = search_pattern.sub("", clean)
    clean = artifact_pattern.sub("", clean)
    clean = done_pattern.sub("", clean)
    clean = ask_pattern.sub("", clean)
    clean = propose_pattern.sub("", clean)
    clean = accept_pattern.sub("", clean)
    clean = reject_pattern.sub("", clean)
    clean = revise_pattern.sub("", clean)
    result["clean_text"] = clean.strip()

    return result


def _append_conversation(config: SessionConfig, agent: str, text: str) -> None:
    """Append a message to the conversation log."""
    conv_path = config.session_dir() / "conversation.md"
    label = config.agent_label(agent)
    with open(conv_path, "a") as f:
        f.write(f"\n## {label} (Turn {config.current_turn + 1})\n\n{text}\n")


def _merge_user_input(
    ask_user_response: str | None,
    nudge_queue: deque[str] | None,
) -> str | None:
    """Combine [ASK_USER] response and buffered nudges into a single string.

    Returns None if both are empty/None.
    """
    parts: list[str] = []
    if ask_user_response:
        parts.append(f"[Agent asked the user a question]:\n{ask_user_response}")
    if nudge_queue:
        lines = []
        while nudge_queue:
            lines.append(nudge_queue.popleft())
        buffered = "\n".join(lines)
        parts.append(f"[User nudge]: {buffered}")
    return "\n\n".join(parts) if parts else None


def _run_turn(
    config: SessionConfig,
    agent: str,
    other_response: str,
    display: DisplayProtocol,
    search_query: str | None = None,
    user_input: str | None = None,
    nudge_queue: deque[str] | None = None,
) -> tuple[AgentResponse, dict, str, str | None]:
    """Execute a single agent turn.

    Returns:
        Tuple of (AgentResponse, parsed_directives, turn_prompt, system_prompt).
    """
    agent_dir = config.session_dir() / f"agent-{agent}"

    # Build memory context
    memory_index = format_memory_index(agent_dir)
    recent_memories = format_recent_memories(agent_dir)
    search_results = None
    if search_query:
        search_results = format_search_results(agent_dir, search_query)

    # Build agreements context
    agreements_text = format_agreements_for_prompt(config, agent, current_turn=config.current_turn + 1)

    # Merge buffered nudges with any ASK_USER response
    merged_input = _merge_user_input(user_input, nudge_queue)
    if merged_input:
        display.show_user_nudge(merged_input)

    # Build the turn prompt
    turn_prompt = build_turn_prompt(
        config=config,
        agent=agent,
        other_response=other_response,
        memory_index=memory_index,
        recent_memories=recent_memories,
        search_results=search_results,
        user_input=merged_input,
        agreements_text=agreements_text,
    )

    # Determine if this is the first turn for this agent
    is_first = (agent == "a" and config.current_turn == 0) or (
        agent == "b" and config.current_turn == 1
    )
    system_prompt = build_system_prompt(config, agent) if is_first else None

    # Display turn start
    display.show_turn_start(config, agent)

    # Write debug request before invoking (visible even if agent hangs)
    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_request(
            log_path=debug_log,
            turn=config.current_turn + 1,
            agent_label=config.agent_label(agent),
            system_prompt=system_prompt,
            turn_prompt=turn_prompt,
        )

    with display.thinking_status(config.agent_label(agent)):
        response = invoke_agent(
            config=config,
            agent=agent,
            prompt=turn_prompt,
            system_prompt=system_prompt,
        )

    # Display response
    display.show_agent_response(config, agent, response.text)

    # Parse directives
    directives = _parse_directives(response.text)

    # Write debug response after invocation
    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_response(
            log_path=debug_log,
            cmd=response.cmd or [],
            raw_response=response.raw,
            directives=directives,
        )

    return response, directives, turn_prompt, system_prompt


def _process_directives(
    config: SessionConfig,
    agent: str,
    directives: dict,
    display: DisplayProtocol,
) -> tuple[str | None, str | None]:
    """Process parsed directives from an agent response.

    Returns:
        Tuple of (search_query for next turn, user_input if collected).
    """
    agent_dir = config.session_dir() / f"agent-{agent}"
    search_query = None
    user_input = None

    # Save memories
    for title, tags, content in directives["memories"]:
        save_memory(agent_dir, title, tags, content)
        display.show_memory_save(agent, title)

    # Queue memory searches
    if directives["memory_searches"]:
        search_query = directives["memory_searches"][0]

    # Save artifacts
    for filename, content in directives["artifacts"]:
        artifact_path = config.session_dir() / "artifacts" / filename
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content + "\n")
        display.show_artifact_save(filename)

    # Handle done signal (consensus mechanism)
    other_agent = "b" if agent == "a" else "a"
    if directives["done"]:
        display.show_done_signal(agent, directives["done"])
        config.done_signals[agent] = directives["done"]
    else:
        # If the other agent had a pending DONE but this agent didn't agree, clear it
        if other_agent in config.done_signals and agent not in config.done_signals:
            display.show_done_disagreement(agent, other_agent)
            del config.done_signals[other_agent]

    # Handle proposals
    turn = config.current_turn + 1
    for title, content in directives["proposals"]:
        proposal_id = create_proposal(config, title, content, agent, turn)
        display.show_proposal(agent, title, proposal_id)

    # Handle accepts
    for proposal_id in directives["accepts"]:
        accepted = accept_proposal(config, proposal_id, turn)
        if accepted:
            display.show_agreement_accepted(proposal_id, accepted["title"])

    # Handle rejects
    for proposal_id, reason in directives["rejects"]:
        rejected = reject_proposal(config, proposal_id)
        if rejected:
            display.show_agreement_rejected(proposal_id, reason)

    # Handle revisions
    for agreement_id, content in directives["revisions"]:
        # Find the original agreement title
        original = next(
            (a for a in config.accepted_agreements if a["id"] == agreement_id),
            None,
        )
        title = original["title"] if original else "Revised agreement"
        new_id = create_proposal(
            config, title, content, agent, turn, revises=agreement_id
        )
        display.show_revision_proposed(agent, agreement_id, new_id)

    # Handle ask_user
    if directives["ask_user"] and config.interactive:
        answer = display.prompt_user(directives["ask_user"])
        user_input = f"Q: {directives['ask_user']}\nA: {answer}"

    return search_query, user_input


def _check_stop(config: SessionConfig, start_time: float) -> str | None:
    """Check if the session should stop.

    Returns:
        Reason string if stopping, None to continue.
    """
    global _shutdown_requested
    if _shutdown_requested:
        return "interrupted"

    if config.current_turn >= config.max_turns:
        return "max_turns"

    if config.max_minutes:
        elapsed = (time.time() - start_time) / 60
        if elapsed >= config.max_minutes:
            return "max_minutes"

    if config.auto_complete and len(config.done_signals) >= 2:
        return "auto_complete"

    return None


def run_session(
    config: SessionConfig,
    display: DisplayProtocol,
    nudge_queue: deque[str] | None = None,
) -> None:
    """Run the main brainstorming loop.

    Args:
        config: The session configuration.
        display: The display manager.
        nudge_queue: Optional thread-safe deque for user nudge input.
    """
    global _shutdown_requested
    _shutdown_requested = False

    # Install signal handler for graceful shutdown (only from main thread;
    # when running inside a Textual worker thread, Textual's own Ctrl+C
    # binding handles shutdown via action_quit_session).
    old_handler = None
    if threading.current_thread() is threading.main_thread():
        old_handler = signal.signal(signal.SIGINT, _signal_handler)

    config.ensure_dirs()
    config.save()
    display.show_header(config)

    if config.interactive:
        display.show_input_hint()

    start_time = time.time()
    other_response = ""
    current_agent = "a"
    search_query: str | None = None
    user_input: str | None = None

    try:
        while True:
            stop_reason = _check_stop(config, start_time)
            if stop_reason:
                if stop_reason == "interrupted":
                    config.status = "paused"
                    display.show_status(
                        f"Session paused. Resume with: storm resume {config.session_id}"
                    )
                else:
                    config.status = "completed"
                    display.show_status(f"Session ended: {stop_reason}")
                break

            response, directives, turn_prompt, system_prompt = _run_turn(
                config=config,
                agent=current_agent,
                other_response=other_response,
                display=display,
                search_query=search_query,
                user_input=user_input,
                nudge_queue=nudge_queue,
            )

            if response.is_error:
                display.show_error(response.text)
                config.status = "paused"
                break

            # Process directives
            search_query, user_input = _process_directives(
                config, current_agent, directives, display
            )

            # Append to conversation log
            _append_conversation(
                config, current_agent, directives["clean_text"]
            )

            # Advance turn
            other_response = response.text
            config.current_turn += 1
            config.save()

            # Check stop after processing (for done signals)
            stop_reason = _check_stop(config, start_time)
            if stop_reason:
                if stop_reason == "interrupted":
                    config.status = "paused"
                    display.show_status(
                        f"Session paused. Resume with: storm resume {config.session_id}"
                    )
                else:
                    config.status = "completed"
                    display.show_status(f"Session ended: {stop_reason}")
                break

            # Switch agent
            current_agent = "b" if current_agent == "a" else "a"

    finally:
        if old_handler is not None:
            signal.signal(signal.SIGINT, old_handler)
        config.save()

    # Compile deliverables and generate summary if completed
    if config.status == "completed":
        _compile_deliverables(config, display)
        _generate_summary(config, display)

    display.show_completion(config)


def _find_matching_artifacts(artifacts_dir: Path, deliverable_name: str) -> dict[str, str]:
    """Find existing artifact files whose names fuzzy-match a deliverable.

    Compares normalized words from the deliverable name against each artifact
    filename. A file matches if at least half the deliverable's words appear
    in the filename.

    Returns:
        Dict of filename → file content for matching artifacts.
    """
    if not artifacts_dir.exists():
        return {}

    # Normalize deliverable name into lowercase tokens
    deliv_words = set(re.sub(r'[^\w\s]', '', deliverable_name).lower().split())
    if not deliv_words:
        return {}

    matches: dict[str, str] = {}
    for path in sorted(artifacts_dir.glob("*.md")):
        stem_words = set(re.sub(r'[_\-]', ' ', path.stem).lower().split())
        overlap = deliv_words & stem_words
        if len(overlap) >= max(1, len(deliv_words) // 2):
            matches[path.name] = path.read_text()

    return matches


def _compile_deliverables(config: SessionConfig, display: DisplayProtocol) -> None:
    """Compile each deliverable from session materials into artifact files."""
    if not config.deliverables:
        return

    # Gather all memory files from both agents
    memories_parts: list[str] = []
    for agent in ("a", "b"):
        mem_dir = config.session_dir() / f"agent-{agent}" / "memory"
        if mem_dir.exists():
            for md_file in sorted(mem_dir.glob("*.md")):
                label = config.agent_label(agent)
                memories_parts.append(
                    f"### {label}: {md_file.stem}\n\n{md_file.read_text()}"
                )
    memories_text = "\n\n---\n\n".join(memories_parts) if memories_parts else "(no memories)"

    # Read conversation log
    conv_path = config.session_dir() / "conversation.md"
    conversation_text = conv_path.read_text() if conv_path.exists() else "(no conversation)"

    # Build agreements text for deliverable compilation
    agreements_text = format_agreements_for_prompt(config, "a")

    artifacts_dir = config.session_dir() / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    for deliverable in config.deliverables:
        display.show_deliverable_compile(deliverable)

        # Find existing artifact files that match this deliverable
        existing_artifacts = _find_matching_artifacts(artifacts_dir, deliverable)

        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name=deliverable,
            memories_text=memories_text,
            conversation_text=conversation_text,
            agreements_text=agreements_text,
            existing_artifacts=existing_artifacts or None,
        )

        if config.debug:
            debug_log = config.session_dir() / "debug.log"
            write_debug_request(
                log_path=debug_log,
                turn=f"deliverable:{deliverable}",
                agent_label="Compiler",
                system_prompt=None,
                turn_prompt=prompt,
            )

        with display.thinking_status(f"Compiling: {deliverable}"):
            response = invoke_agent(
                config=config,
                agent="a",
                prompt=prompt,
                session_id=str(uuid4()),
                readonly=True,
            )

        if config.debug:
            debug_log = config.session_dir() / "debug.log"
            write_debug_response(
                log_path=debug_log,
                cmd=response.cmd or [],
                raw_response=response.raw,
                directives={},
            )

        if not response.is_error:
            # Sanitize filename
            safe_name = re.sub(r'[^\w\s-]', '', deliverable).strip()
            safe_name = re.sub(r'[\s]+', '_', safe_name).lower()
            artifact_path = artifacts_dir / f"{safe_name}.md"
            artifact_path.write_text(response.text + "\n")
            display.show_artifact_save(f"{safe_name}.md")
        else:
            display.show_error(f"Failed to compile deliverable: {deliverable}")


def _generate_summary(config: SessionConfig, display: DisplayProtocol) -> None:
    """Generate and save a session summary."""
    display.show_status("Generating session summary...")
    summary_prompt = build_summary_prompt(config)

    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_request(
            log_path=debug_log,
            turn="summary",
            agent_label="Summarizer",
            system_prompt=None,
            turn_prompt=summary_prompt,
        )

    with display.thinking_status("Generating summary"):
        response = invoke_agent(
            config=config,
            agent="a",
            prompt=summary_prompt,
            session_id=str(uuid4()),
            readonly=True,
        )

    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_response(
            log_path=debug_log,
            cmd=response.cmd or [],
            raw_response=response.raw,
            directives={},
        )

    if not response.is_error:
        summary_path = config.session_dir() / "summary.md"
        summary_path.write_text(response.text + "\n")
        display.show_summary(response.text)
    else:
        display.show_error("Failed to generate session summary")


@app.callback()
def main(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """Claude Storm - Dual-agent brainstorming system."""
    global _debug_mode
    _debug_mode = debug


@app.command()
def init(
    topic: Optional[str] = typer.Option(
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
            console.print(f"[bold red]No {STORM_CONFIG_FILENAME} found to update.[/bold red]")
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
        raise typer.Exit(1)


@app.command()
def start(
    topic: Optional[str] = typer.Argument(default=None, help="The brainstorming topic"),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to storm.toml"
    ),
    goal: Optional[str] = typer.Option(
        None, "--goal", "-g", help="Session goal"
    ),
    roles: Optional[list[str]] = typer.Option(
        None, "--roles", "-r", help="Agent roles (provide two)"
    ),
    max_turns: Optional[int] = typer.Option(
        None, "--max-turns", "-t", help="Maximum turns"
    ),
    auto_complete: Optional[bool] = typer.Option(
        None, "--auto-complete/--no-auto-complete", help="Let agents decide when done"
    ),
    max_minutes: Optional[int] = typer.Option(
        None, "--max-minutes", "-m", help="Wall-clock time limit"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Claude model to use"
    ),
    interactive: Optional[bool] = typer.Option(
        None, "--interactive/--no-interactive", help="Allow agents to ask user questions"
    ),
    reference_dir: Optional[list[Path]] = typer.Option(
        None, "--reference-dir", "--ref", help="Read-only directory of reference materials (repeatable)"
    ),
) -> None:
    """Start a new brainstorming session."""
    console = Console()

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
    }

    # Layer 2: TOML config (if available)
    toml_config: dict = {}
    resolved_config_path = config_path
    if resolved_config_path is None:
        default_toml = Path.cwd() / STORM_CONFIG_FILENAME
        if default_toml.exists():
            resolved_config_path = default_toml

    if resolved_config_path is not None:
        try:
            toml_config = load_project_config(resolved_config_path)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[bold red]{e}[/bold red]")
            raise typer.Exit(1)

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
    if reference_dir:
        merged["reference_dirs"] = [str(p) for p in reference_dir]

    # Validate: each reference dir must exist
    resolved_refs: list[str] = []
    for ref in merged["reference_dirs"]:
        ref_path = Path(ref).resolve()
        if not ref_path.is_dir():
            console.print(
                f"[bold red]Reference directory not found: {ref_path}[/bold red]"
            )
            raise typer.Exit(1)
        resolved_refs.append(str(ref_path))
    merged["reference_dirs"] = resolved_refs

    # Validate: topic is required
    if not merged["topic"]:
        console.print(
            "[bold red]No topic provided. Pass a topic argument or create a storm.toml.[/bold red]"
        )
        raise typer.Exit(1)

    # Resolve storms dir
    storms_dir = str(get_storms_dir(resolved_config_path))

    config = SessionConfig.create(
        topic=merged["topic"],
        goal=merged["goal"],
        role_a=merged["role_a"],
        role_b=merged["role_b"],
        max_turns=merged["max_turns"],
        max_minutes=merged["max_minutes"],
        auto_complete=merged["auto_complete"],
        interactive=merged["interactive"],
        debug=_debug_mode,
        model=merged["model"],
        deliverables=merged["deliverables"],
        reference_dirs=merged["reference_dirs"],
        truncate_conversation=merged["truncate_conversation"],
        storms_dir=storms_dir,
    )

    if sys.stdout.isatty():
        from claude_storm.app import StormApp
        tui = StormApp(config)
        tui.run()
    else:
        display = Display()
        run_session(config, display)


@app.command()
def resume(
    session_id: str = typer.Argument(help="Session ID to resume"),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to storm.toml (to locate .storms/)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
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
        raise typer.Exit(1)

    if config.status == "completed":
        console.print(
            f"[bold red]Session {session_id} is completed and cannot be resumed[/bold red]"
        )
        raise typer.Exit(1)

    if config.status != "paused" and not force:
        console.print(
            f"[bold red]Session {session_id} is {config.status}, not paused[/bold red]"
        )
        console.print("[dim]Use --force to resume anyway (e.g. after a hard kill)[/dim]")
        raise typer.Exit(1)

    config.status = "active"
    if _debug_mode:
        config.debug = True

    if sys.stdout.isatty():
        from claude_storm.app import StormApp
        tui = StormApp(config, resume=True)
        tui.run()
    else:
        display = Display()
        run_session(config, display)


@app.command(name="list")
def list_sessions(
    config_path: Optional[Path] = typer.Option(
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
    config_path: Optional[Path] = typer.Option(
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
        raise typer.Exit(1)

    console.print(f"[bold]Session: {config.session_id}[/bold]")
    console.print(f"Topic: {config.topic}")
    if config.goal:
        console.print(f"Goal: {config.goal}")
    console.print(
        f"Agents: {config.agent_label('a')} vs {config.agent_label('b')}"
    )
    console.print(f"Status: {config.status}")
    console.print(f"Turns: {config.current_turn}/{config.max_turns}")
    console.print(f"Model: {config.model}")
    if config.deliverables:
        console.print(f"Deliverables: {', '.join(config.deliverables)}")
    console.print(f"Started: {config.started_at}")
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
