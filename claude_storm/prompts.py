"""System prompt and per-turn prompt templates."""

from __future__ import annotations

import re
from pathlib import Path

from claude_storm.config import SessionConfig
from claude_storm.project import format_pacing_block

# Maximum length for agent-supplied reason strings embedded in prompts
_MAX_REASON_LENGTH = 200


def _sanitize_agent_text(text: str, max_length: int = _MAX_REASON_LENGTH) -> str:
    """Sanitize agent-supplied text before embedding in prompts.

    Truncates to max_length and strips directive-like patterns to
    prevent prompt injection via agent responses.

    Args:
        text: The raw agent-supplied string.
        max_length: Maximum allowed length.

    Returns:
        Sanitized text string.
    """
    text = text[:max_length]
    # Strip anything that looks like a directive tag
    text = re.sub(r"\[/?[A-Z_]+[^\]]*\]", "", text)
    return text.strip()


def _build_role_section(config: SessionConfig, agent: str) -> str:
    """Build the role and context section of the system prompt."""
    role = config.role_a if agent == "a" else config.role_b
    other = config.agent_label("b" if agent == "a" else "a")

    if role:
        role_lines = role.strip().splitlines()
        title = role_lines[0].strip()
        persona = (
            f"You are playing the role of **{title}** "
            "in a structured brainstorming session."
        )
        description = "\n".join(role_lines[1:]).strip()
        if description:
            persona += f"\n\n{description}"
    else:
        persona = (
            "You are a brainstorming partner in a structured two-agent discussion."
        )

    parts = [
        "# Role and Context\n",
        persona,
        f"\n**Topic:** {config.topic}",
    ]
    if config.goal:
        parts.append(f"**Goal:** {config.goal}")

    parts.append(
        f"\nYou are having a rigorous debate with another agent ({other}). "
        "You take strict alternating turns. Read their latest "
        "message, identify where you agree and where you disagree, "
        "and respond with a clear position."
    )
    return "\n".join(parts)


def _build_directives_section(config: SessionConfig) -> str:
    """Build the directives section listing available agent commands."""
    text = (
        "\n# Directives\n"
        "You may use these special directives in your responses:\n\n"
        "## Private Tools\n"
        '- `[MEMORY title="..." tags="t1,t2"]content[/MEMORY]`'
        " — Save a note to your **private** long-term memory "
        "(only visible to you). Use this for your own working "
        "notes, open questions, and ideas you're still "
        "developing.\n"
        '- `[MEMORY_SEARCH query="..."]` — Request a search '
        "of your saved memories. Results will appear in your "
        "next turn.\n\n"
        "## Shared Output\n"
        '- `[PROPOSE title="..."]content[/PROPOSE]` — Propose '
        "a shared agreement for the other agent to confirm or "
        "reject. **Make bold, specific proposals — take a "
        "strong position and defend it.** Verbal agreement "
        "('I agree', 'good point', 'I'm sold') does NOT "
        "create a shared record. Only [PROPOSE] + [ACCEPT] "
        "does. Confirmed agreements become part of the "
        "session's formal output and are saved as "
        "individual files in the `agreements/` directory "
        "(e.g. `agreements/a3f2_use-rest.md`) — use "
        "your Read tool on the specific file to review "
        "the full text when you need it for reference or "
        "revision. Propose early and "
        "forcefully — if the other agent disagrees, that "
        "sharpens the debate.\n"
        '- `[ACCEPT id="..."]` — Accept a pending agreement '
        "proposal by its ID.\n"
        '- `[REJECT id="..." reason="..."]` — Reject a '
        "pending proposal with an explanation.\n"
        '- `[REVISE id="..."]new content[/REVISE]` — Propose a '
        "revised version of a confirmed agreement or a pending "
        "proposal. When used on a confirmed agreement, creates a "
        "new pending proposal. When used on a pending proposal, "
        "replaces it with your revised version for the other "
        "agent to review.\n"
        '- `[ARTIFACT filename="..."]content[/ARTIFACT]`'
        " — Produce a shared output file "
        "(code, document, etc.).\n"
        '- `[DONE reason="..."]` — Signal that you believe '
        "the brainstorming is complete and the topic is "
        "well-explored. The other agent will be asked to "
        "confirm. If they disagree, the conversation "
        "continues.\n"
    )
    if config.interactive:
        text += (
            "- `[ASK_USER]question[/ASK_USER]` — Pause to "
            "ask the human user a question. A human operator "
            "is available and monitoring this session. Use "
            "this when you need clarification, want input on "
            "a decision, or are unsure which direction to "
            "take.\n"
        )
    return text


def _build_guidelines_section(config: SessionConfig) -> str:
    """Build the behavioral guidelines section."""
    text = (
        "\n# Guidelines\n"
        "- Take strong, opinionated positions — do not hedge or equivocate\n"
        "- Challenge assumptions directly; say what is wrong and why\n"
        "- When you disagree, say so plainly and give concrete reasons\n"
        "- Do not accept proposals merely to be agreeable — [REJECT] or [REVISE] any "
        "proposal you have genuine concerns about\n"
        "- Keep responses focused and actionable\n"
        "- Produce concrete artifacts when appropriate\n\n"
        "## Debate and Proposals\n"
        "- Use [MEMORY] for your private working notes — things you want to track "
        "but that don't need the other agent's sign-off.\n"
        "- Prefer [PROPOSE] over [MEMORY] for anything that should be a session "
        "conclusion, recommendation, or decision. Proposals are the **only** way to "
        "create shared, confirmed output that both agents endorse.\n"
        "- Propose early and with conviction. A proposal that gets "
        "rejected sharpens the discussion and is more valuable than vague agreement.\n"
        '- Good proposals are specific and assertive: *"Use PostgreSQL for the data '
        'layer because X, Y, Z"* rather than *"We discussed database options."*\n'
        "- Always review and respond to pending proposals from the other agent"
        " — accepting without scrutiny is worse than rejecting with good reasons\n"
        "- When you mostly agree with a proposal but want changes, use [REVISE] to "
        "submit your improved version rather than accepting and then proposing "
        "separate amendments"
    )
    if config.interactive:
        text += (
            "\n- If you're uncertain about a direction or need user preferences, "
            "ask with [ASK_USER]"
            "\n- The user may type nudges at any time during the session. These "
            'appear in the "User Input" section of your turn prompt and should be '
            "treated as steering guidance — acknowledge and incorporate them."
        )
    return text


def _build_reference_section(config: SessionConfig) -> str:
    """Build the reference materials section. Returns empty string if none.

    Directs agents to use the ``refs/`` symlinks in the session directory
    instead of the raw paths, which may contain characters that LLMs garble
    when reconstructing tool-call arguments.  Falls back to the raw path
    when a symlink is missing (e.g. creation failed due to permissions).
    """
    if not config.reference_dirs:
        return ""
    symlink_paths = config.ref_symlink_paths()
    rows: list[str] = []
    for i, raw_path in enumerate(config.reference_dirs, start=1):
        symlink = symlink_paths[i]
        # Fall back to raw path when symlink is missing (e.g. creation failed)
        use_path = symlink if symlink.is_symlink() else Path(raw_path)
        # Show the last component(s) of the actual path for human context
        short_actual = Path(raw_path).name
        rows.append(f"| `{use_path}` | `{short_actual}` |")
    table = "\n".join(rows)
    return (
        "\n# Reference Materials\n"
        "The following reference directories are available. Use the **path**\n"
        "(first column) for all Glob and Read operations — these are short, reliable\n"
        "paths that point to the actual directories:\n\n"
        "| Path | Actual Directory |\n"
        "|---|---|\n"
        f"{table}\n\n"
        "Use `Glob` and `Read` to browse and read files from these paths.\n"
        "This is read-only reference material — do not modify these files."
    )


def _build_session_structure_section(config: SessionConfig) -> str:
    """Build the session structure section. Returns empty string if not applicable."""
    if not config.deliverables and not config.goal:
        return ""
    structure_parts = [
        f"\n# Session Structure\n"
        f"This session has a budget of {config.max_turns} turns total."
    ]
    if config.goal:
        structure_parts.append(f"\n**Session goal:** {config.goal}")
    if config.deliverables:
        structure_parts.append("\n## Expected Deliverables")
        for d in config.deliverables:
            structure_parts.append(f"- {d}")
    if config.interactive:
        structure_parts.append(
            "\nPace yourself: use the early turns to clarify goals and constraints "
            "with the user (via [ASK_USER]), explore broadly through the first half, "
            "then shift toward concrete decisions and producing deliverables in the "
            "second half. Start writing `[ARTIFACT]` files incrementally from the "
            "halfway point — don't wait until the end. For large deliverables, break "
            "them into multiple artifact files that you can "
            "refine over subsequent turns."
        )
    else:
        structure_parts.append(
            "\nPace yourself: explore broadly in the first half, then shift toward "
            "concrete decisions and producing deliverables in the second half. "
            "Start writing `[ARTIFACT]` files incrementally from the halfway point — "
            "don't wait until the end. For large deliverables, break them into "
            "multiple artifact files that you can refine over subsequent turns."
        )
    return "\n".join(structure_parts)


def build_system_prompt(config: SessionConfig, agent: str) -> str:
    """Build the system prompt for an agent's first turn.

    Args:
        config: The session configuration.
        agent: Which agent ('a' or 'b').

    Returns:
        The system prompt string.
    """
    parts = [
        _build_role_section(config, agent),
        _build_directives_section(config),
        _build_guidelines_section(config),
    ]

    ref_section = _build_reference_section(config)
    if ref_section:
        parts.append(ref_section)

    structure_section = _build_session_structure_section(config)
    if structure_section:
        parts.append(structure_section)

    return "\n".join(parts)


def build_turn_prompt(
    config: SessionConfig,
    agent: str,
    other_response: str,
    memory_index: str,
    recent_memories: str,
    search_results: str | None = None,
    user_input: str | None = None,
    agreements_text: str = "",
    is_agent_first_turn: bool = True,
) -> str:
    """Build the per-turn prompt for an agent.

    Args:
        config: The session configuration.
        agent: Which agent ('a' or 'b').
        other_response: The other agent's last message.
        memory_index: Formatted memory index string.
        recent_memories: Formatted recent memories string.
        search_results: Formatted search results, if any.
        user_input: User input in response to ASK_USER, if any.
        agreements_text: Formatted shared agreements text.
        is_agent_first_turn: Whether this is the agent's first turn.
            When False, DONE and interactive mode reminders are omitted
            (already in the system prompt).

    Returns:
        The per-turn prompt string.
    """
    other_label = config.agent_label("b" if agent == "a" else "a")

    sections = []

    # Other agent's response
    sections.append(f"# {other_label}'s Response")
    if config.current_turn == 0 and agent == "a":
        sections.append("This is the start of the conversation. You go first.")
    else:
        sections.append(other_response or "(no response)")

    # Memory index
    sections.append(f"\n# Your Memory Index\n{memory_index}")

    # Recent memories
    if recent_memories:
        sections.append(f"\n# Recent Memories\n{recent_memories}")

    # Search results
    if search_results:
        sections.append(f"\n# Search Results\n{search_results}")

    # User input
    if user_input:
        sections.append(f"\n# User Input\n{user_input}")

    # Shared agreements
    if agreements_text:
        sections.append(f"\n{agreements_text}")

    # Pacing block (replaces old turn info)
    turn_number = config.current_turn + 1
    pacing = format_pacing_block(
        turn=turn_number,
        max_turns=config.max_turns,
        deliverables=config.deliverables or None,
        session_id=config.session_id,
        interactive=config.interactive,
        goal=config.goal or None,
        is_first_turn=is_agent_first_turn,
    )
    sections.append(f"\n# Turn Progress\n{pacing}")

    # Completion Check: if the other agent has a pending DONE signal
    other_agent = "b" if agent == "a" else "a"
    other_done_reason = config.done_signals.get(other_agent)
    if other_done_reason and config.auto_complete:
        sanitized_reason = _sanitize_agent_text(other_done_reason)
        sections.append(
            f"\n# Completion Check\n"
            f"{other_label} has signaled that they believe "
            "the brainstorming is complete.\n"
            f'Their reason: "{sanitized_reason}"\n\n'
            f"If you agree, signal [DONE]. If not, continue normally and explain "
            f"what still needs attention."
        )
    elif config.auto_complete and is_agent_first_turn:
        sections.append("Signal [DONE] when you believe the topic is well-explored.")

    # Interactive mode reminder (only on first turn; already in system prompt)
    if config.interactive and is_agent_first_turn:
        sections.append(
            "\nYou are in **interactive mode** — a human is monitoring. "
            "Use [ASK_USER] if you need their input."
        )

    return "\n".join(sections)


def build_summary_prompt(config: SessionConfig) -> str:
    """Build a prompt requesting a session summary.

    Args:
        config: The session configuration.

    Returns:
        The summary request prompt.
    """
    parts = [
        "# Session Summary Request\n",
        f'The brainstorming session on "{config.topic}" has concluded after '
        f"{config.current_turn} turns.",
    ]
    if config.goal:
        parts.append(f"**Session goal:** {config.goal}")
    parts.append(
        "\nPlease provide a comprehensive summary of:\n\n"
        "1. Key ideas discussed\n"
        "2. Decisions made\n"
        "3. Open questions remaining\n"
        "4. Recommended next steps\n"
    )
    if config.goal:
        parts.append("5. Goal assessment — did the session achieve its stated goal?\n")
    parts.append("Be concise but thorough. Format as markdown.")

    if config.deliverables:
        parts.append(
            "\n## Deliverables Assessment\n\n"
            "The following deliverables were expected:\n"
            + "\n".join(f"- {d}" for d in config.deliverables)
            + "\n\nPlease assess which were produced and their completeness."
        )

    return "\n".join(parts)


_TRUNCATION_THRESHOLD = 50_000


def build_deliverable_prompt(
    config: SessionConfig,
    deliverable_name: str,
    memories_text: str,
    conversation_text: str,
    agreements_text: str = "",
    existing_artifacts: dict[str, str] | None = None,
) -> str:
    """Build a prompt to compile a single deliverable from session materials.

    Args:
        config: The session configuration.
        deliverable_name: Name of the deliverable to compile.
        memories_text: Combined memory contents from both agents.
        conversation_text: The full conversation log.
        agreements_text: Formatted shared agreements text.
        existing_artifacts: Dict of filename→content for draft artifacts
            that match this deliverable. When present, the agent is asked
            to refine/merge rather than generate from scratch.

    Returns:
        The compilation prompt string.
    """
    if existing_artifacts:
        instruction = (
            "Produce a clean, well-structured markdown document. "
            "Draft artifact files from the session are included below — "
            "refine, merge, and complete them into the final deliverable. "
            "Do not start from scratch; use the drafts as your foundation.\n\n"
            "IMPORTANT: Output the full deliverable content "
            "directly in your response.\n"
            "Do NOT use Write or Edit tools. Do NOT summarize "
            "what you would write —\n"
            "write the actual content here."
        )
    else:
        instruction = (
            "Produce a clean, well-structured markdown document. Include all relevant\n"
            "information discussed during the session. Do not include preamble or\n"
            "meta-commentary — just the deliverable content.\n\n"
            "IMPORTANT: Output the full deliverable content "
            "directly in your response.\n"
            "Do NOT use Write or Edit tools. Do NOT summarize "
            "what you would write —\n"
            "write the actual content here."
        )

    goal_line = f"**Session goal:** {config.goal}\n\n" if config.goal else ""
    parts = [
        f"# Deliverable Compilation\n\n"
        f'The brainstorming session on "{config.topic}" has concluded.\n'
        f"{goal_line}"
        f"Please compile the following deliverable from the session materials:\n\n"
        f"**Deliverable:** {deliverable_name}\n\n"
        f"{instruction}\n\n"
        f"---\n\n"
        f"## Agent Memories\n\n{memories_text}",
    ]

    if agreements_text:
        parts.append(f"---\n\n## Shared Agreements\n\n{agreements_text}")

    if existing_artifacts:
        draft_parts = []
        for filename, content in existing_artifacts.items():
            draft_parts.append(f"### {filename}\n\n{content}")
        parts.append(
            "---\n\n## Draft Content (from session artifacts)\n\n"
            + "\n\n---\n\n".join(draft_parts)
        )

    # Optionally truncate conversation to avoid timeout on large sessions
    if config.truncate_conversation and len(conversation_text) > _TRUNCATION_THRESHOLD:
        conversation_text = (
            "[...earlier conversation truncated...]\n\n"
            + conversation_text[-_TRUNCATION_THRESHOLD:]
        )

    parts.append(f"---\n\n## Conversation Log\n\n{conversation_text}")

    return "\n\n".join(parts)
