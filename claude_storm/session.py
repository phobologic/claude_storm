"""Session execution loop and turn processing."""

from __future__ import annotations

import contextlib
import signal
import threading
import time
from collections import deque
from dataclasses import asdict

from claude_storm.agents import AgentResponse, invoke_agent
from claude_storm.agreements import (
    RevisionContext,
    accept_proposal,
    create_proposal,
    format_agreements_for_prompt,
    reject_proposal,
)
from claude_storm.compilation import compile_deliverables, generate_summary
from claude_storm.config import SessionConfig
from claude_storm.debug import write_debug_request, write_debug_response
from claude_storm.directives import ParsedDirectives, parse_directives
from claude_storm.display import Display, DisplayProtocol
from claude_storm.memory import (
    format_memory_index,
    format_recent_memories,
    format_search_results,
    get_memory_index,
    save_memory,
)
from claude_storm.prompts import build_system_prompt, build_turn_prompt

# Graceful shutdown flag
_shutdown_requested = False


def _signal_handler(signum: int, frame: object) -> None:
    """Set the shutdown flag on SIGINT."""
    global _shutdown_requested
    _shutdown_requested = True


def _append_conversation(config: SessionConfig, agent: str, text: str) -> None:
    """Append a message to the conversation log."""
    conv_path = config.session_dir() / "conversation.md"
    label = config.agent_label(agent)
    with open(conv_path, "a") as f:
        f.write(f"\n## {label} (Turn {config.current_turn + 1})\n\n{text}\n")


def merge_user_input(
    ask_user_response: str | None,
    nudge_queue: deque[str] | None,
) -> str | None:
    """Combine [ASK_USER] response and buffered nudges into a single string.

    Args:
        ask_user_response: Response text from an ASK_USER interaction.
        nudge_queue: Deque of buffered user nudge strings.

    Returns:
        Combined string, or None if both are empty/None.
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
    if not parts:
        return None
    body = "\n\n".join(parts)
    return (
        ">>> HUMAN USER INPUT (not from the other agent) <<<\n"
        f"{body}\n"
        ">>> END USER INPUT <<<"
    )


def _run_turn(
    config: SessionConfig,
    agent: str,
    other_response: str,
    display: DisplayProtocol,
    search_query: str | None = None,
    user_input: str | None = None,
    nudge_queue: deque[str] | None = None,
) -> tuple[AgentResponse, ParsedDirectives, str, str | None]:
    """Execute a single agent turn.

    Returns:
        Tuple of (AgentResponse, ParsedDirectives, turn_prompt, system_prompt).
    """
    agent_dir = config.session_dir() / f"agent-{agent}"

    # Determine if this is the first turn for this agent
    is_first = (agent == "a" and config.current_turn == 0) or (
        agent == "b" and config.current_turn == 1
    )

    # Get watermark for differential prompts
    watermark = config.get_watermark(agent)
    since_count = 0 if is_first else watermark["memory_count"]

    # Build memory context
    memory_index = format_memory_index(agent_dir, since_count=since_count)
    recent_memories = format_recent_memories(agent_dir, since_count=since_count)
    search_results = None
    if search_query:
        search_results = format_search_results(agent_dir, search_query)

    # Build agreements context
    agreements_text = format_agreements_for_prompt(
        config,
        agent,
        current_turn=config.current_turn + 1,
        watermark=None if is_first else watermark,
    )

    # Merge buffered nudges with any ASK_USER response
    merged_input = merge_user_input(user_input, nudge_queue)
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
        is_agent_first_turn=is_first,
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

    display.show_agent_stream_start(config, agent)
    response = invoke_agent(
        config=config,
        agent=agent,
        prompt=turn_prompt,
        system_prompt=system_prompt,
        timeout=config.agent_timeout,
        on_delta=display.show_agent_stream_delta,
    )
    display.show_agent_stream_end(error=response.is_error, text=response.text)

    # Parse directives
    directives = parse_directives(response.text)

    # Write debug response after invocation
    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_response(
            log_path=debug_log,
            cmd=response.cmd or [],
            raw_response=response.raw,
            directives=asdict(directives),
        )

    return response, directives, turn_prompt, system_prompt


def _resolve_revision_context(
    config: SessionConfig,
    target_id: str,
    agent: str,
    display: DisplayProtocol,
) -> RevisionContext | None:
    """Resolve context for a REVISE directive target.

    Looks up target_id in accepted agreements first, then pending proposals.
    Removes the pending proposal if found and not self-revision.

    For chained revisions (A->B->C), the deepest original is preserved so
    the root content is never lost.

    Args:
        config: The session configuration.
        target_id: The agreement or proposal ID being revised.
        agent: The agent performing the revision.
        display: Display interface for warnings.

    Returns:
        A RevisionContext with the target ID and original content, or None
        to skip (self-revision).
    """
    original = next(
        (a for a in config.accepted_agreements if a["id"] == target_id),
        None,
    )
    if original:
        # For chained revisions, preserve the deepest original
        return RevisionContext(
            revises=target_id,
            title=original["title"],
            original_content=original.get("original_content", original["content"]),
            original_turn=original.get("original_turn", original.get("proposed_turn")),
            original_agent=original.get("original_agent", original.get("proposed_by")),
        )

    pending = next(
        (p for p in config.pending_proposals if p["id"] == target_id),
        None,
    )
    if pending:
        if pending["proposed_by"] == agent:
            display.show_warning(
                f"Agent cannot revise its own pending proposal {target_id}"
            )
            return None
        config.pending_proposals.remove(pending)
        return RevisionContext(
            revises=target_id,
            title=pending["title"],
            original_content=pending.get("original_content", pending["content"]),
            original_turn=pending.get("original_turn", pending.get("turn")),
            original_agent=pending.get("original_agent", pending.get("proposed_by")),
        )

    display.show_warning(
        f"REVISE target {target_id!r} not found; creating proposal with fallback title"
    )
    return RevisionContext(
        revises=target_id,
        title="Revised agreement",
        original_content=None,
        original_turn=None,
        original_agent=None,
    )


def process_directives(
    config: SessionConfig,
    agent: str,
    directives: ParsedDirectives,
    display: DisplayProtocol,
) -> tuple[str | None, str | None]:
    """Process parsed directives from an agent response.

    Args:
        config: The session configuration.
        agent: Which agent ('a' or 'b').
        directives: Parsed directives from the agent response.
        display: The display manager.

    Returns:
        Tuple of (search_query for next turn, user_input if collected).
    """
    agent_dir = config.session_dir() / f"agent-{agent}"
    search_query = None
    user_input = None

    # Save memories
    for title, tags, content in directives.memories:
        save_memory(agent_dir, title, tags, content)
        display.show_memory_save(agent, title)

    # Queue memory searches
    if directives.memory_searches:
        search_query = directives.memory_searches[0]

    # Save artifacts
    artifacts_dir = config.session_dir() / "artifacts"
    for filename, content in directives.artifacts:
        artifact_path = (artifacts_dir / filename).resolve()
        if not artifact_path.is_relative_to(artifacts_dir.resolve()):
            display.show_warning(f"Blocked artifact with unsafe filename: {filename!r}")
            continue
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content + "\n")
        display.show_artifact_save(filename)

    # Handle done signal (consensus mechanism)
    other_agent = "b" if agent == "a" else "a"
    if directives.done:
        display.show_done_signal(agent, directives.done)
        config.done_signals[agent] = directives.done
    else:
        # If the other agent had a pending DONE but this agent didn't agree, clear it
        if other_agent in config.done_signals and agent not in config.done_signals:
            display.show_done_disagreement(agent, other_agent)
            del config.done_signals[other_agent]

    # Handle proposals
    turn = config.current_turn + 1
    for title, content in directives.proposals:
        proposal_id = create_proposal(config, title, content, agent, turn)
        display.show_proposal(agent, title, proposal_id)

    # Handle accepts
    for proposal_id in directives.accepts:
        accepted = accept_proposal(config, proposal_id, turn)
        if accepted:
            display.show_agreement_accepted(proposal_id, accepted["title"])

    # Handle rejects
    for proposal_id, reason in directives.rejects:
        rejected = reject_proposal(config, proposal_id)
        if rejected:
            display.show_agreement_rejected(proposal_id, reason)

    # Handle revisions (confirmed agreements OR pending proposals)
    for target_id, content in directives.revisions:
        ctx = _resolve_revision_context(config, target_id, agent, display)
        if ctx is None:
            continue
        new_id = create_proposal(
            config,
            ctx.title,
            content,
            agent,
            turn,
            revision=ctx,
        )
        display.show_revision_proposed(agent, target_id, new_id)

    # Handle ask_user
    if directives.ask_user and config.interactive:
        answer = display.prompt_user(directives.ask_user)
        user_input = f"Q: {directives.ask_user}\nA: {answer}"

    return search_query, user_input


def check_stop(config: SessionConfig, start_time: float) -> str | None:
    """Check if the session should stop.

    Args:
        config: The session configuration.
        start_time: Session start timestamp (from time.time()).

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
    pending_answer_for: dict[str, str] = {}

    try:
        while True:
            stop_reason = check_stop(config, start_time)
            if stop_reason:
                config.stop_reason = stop_reason
                if stop_reason == "interrupted":
                    config.status = "paused"
                    display.show_status(
                        f"Session paused. Resume with: storm resume {config.session_id}"
                    )
                else:
                    config.status = "completed"
                    display.show_status(f"Session ended: {stop_reason}")
                break

            # Merge any pending ASK_USER answer for this agent
            pending = pending_answer_for.pop(current_agent, None)
            if pending:
                user_input = f"{user_input}\n\n{pending}" if user_input else pending

            response, directives, _, _ = _run_turn(
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
                config.stop_reason = (
                    "agent_timeout" if response.timed_out else "agent_error"
                )
                config.stop_error = response.text
                break

            # Append to conversation log before processing directives,
            # which may block on ASK_USER prompts and get interrupted.
            _append_conversation(config, current_agent, directives.clean_text)

            # Process directives
            search_query, user_input = process_directives(
                config, current_agent, directives, display
            )

            # If this agent asked a question and got an answer, store it so
            # the asking agent also sees the answer on its next turn.
            if user_input and directives.ask_user:
                pending_answer_for[current_agent] = user_input

            # Update watermark before advancing turn
            agent_dir = config.session_dir() / f"agent-{current_agent}"
            memory_count = len(get_memory_index(agent_dir))
            config.update_watermark(current_agent, memory_count)

            # Advance turn
            other_response = response.text
            config.current_turn += 1
            config.save()

            # Check stop after processing (for done signals)
            stop_reason = check_stop(config, start_time)
            if stop_reason:
                config.stop_reason = stop_reason
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
        compile_deliverables(config, display)
        generate_summary(config, display)

    display.show_completion(config)

    if config.interactive and isinstance(display, Display):
        with contextlib.suppress(EOFError, KeyboardInterrupt):
            display.console.input("[dim]Press Enter to exit...[/dim]")
