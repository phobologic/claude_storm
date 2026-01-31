"""System prompt and per-turn prompt templates."""

from __future__ import annotations

from claude_storm.config import SessionConfig
from claude_storm.project import format_pacing_block


def build_system_prompt(config: SessionConfig, agent: str) -> str:
    """Build the system prompt for an agent's first turn.

    Args:
        config: The session configuration.
        agent: Which agent ('a' or 'b').

    Returns:
        The system prompt string.
    """
    role = config.role_a if agent == "a" else config.role_b
    other = config.agent_label("b" if agent == "a" else "a")

    if role:
        persona = f"You are playing the role of **{role}** in a structured brainstorming session."
    else:
        persona = "You are a brainstorming partner in a structured two-agent discussion."

    parts = [
        "# Role and Context\n",
        persona,
        f"\n**Topic:** {config.topic}",
    ]
    if config.goal:
        parts.append(f"**Goal:** {config.goal}")

    parts.append(
        f"\nYou are having a conversation with another agent ({other}). "
        "You take strict alternating turns. Read their latest message and respond thoughtfully."
    )

    parts.append(
        "\n# Directives\n"
        "You may use these special directives in your responses:\n\n"
        '- `[MEMORY title="..." tags="t1,t2"]content[/MEMORY]` - Save a note to your '
        "long-term memory. Use this for important ideas, decisions, or insights you want "
        "to remember.\n"
        '- `[MEMORY_SEARCH query="..."]` - Request a search of your saved memories. '
        "Results will appear in your next turn.\n"
        '- `[ARTIFACT filename="..."]content[/ARTIFACT]` - Produce a shared output file '
        "(code, document, etc.).\n"
        '- `[DONE reason="..."]` - Signal that you believe the brainstorming is complete '
        "and the topic is well-explored.\n"
        "- `[ASK_USER]question[/ASK_USER]` - Pause to ask the human user a question "
        "(only if interactive mode is enabled)."
    )

    parts.append(
        "\n# Guidelines\n"
        "- Be substantive and build on previous ideas\n"
        "- Challenge assumptions constructively\n"
        "- Save key insights and decisions to memory with [MEMORY]\n"
        "- Produce concrete artifacts when appropriate\n"
        "- Keep responses focused and actionable"
    )

    # Reference materials section
    if config.reference_dirs:
        dir_list = "\n".join(f"- `{d}`" for d in config.reference_dirs)
        parts.append(
            "\n# Reference Materials\n"
            "Directories of background materials relevant to this topic are available at:\n"
            f"{dir_list}\n\n"
            "Use `Glob` and `Read` to browse and read files from these directories. "
            "This is read-only reference material — do not modify these files."
        )

    # Session structure section (pacing overview + deliverables)
    if config.deliverables or config.goal:
        structure_parts = [
            f"\n# Session Structure\n"
            f"This session has a budget of {config.max_turns} turns total."
        ]
        if config.deliverables:
            structure_parts.append("\n## Expected Deliverables")
            for d in config.deliverables:
                structure_parts.append(f"- {d}")
        structure_parts.append(
            "\nPace yourself: explore broadly in the first half, then shift toward "
            "concrete decisions and producing deliverables in the second half."
        )
        parts.append("\n".join(structure_parts))

    return "\n".join(parts)


def build_turn_prompt(
    config: SessionConfig,
    agent: str,
    other_response: str,
    memory_index: str,
    recent_memories: str,
    search_results: str | None = None,
    user_input: str | None = None,
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

    # Pacing block (replaces old turn info)
    turn_number = config.current_turn + 1
    pacing = format_pacing_block(
        turn=turn_number,
        max_turns=config.max_turns,
        deliverables=config.deliverables or None,
    )
    sections.append(f"\n# Turn Progress\n{pacing}")

    if config.auto_complete:
        sections.append(
            "Signal [DONE] when you believe the topic is well-explored."
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
        f"The brainstorming session on \"{config.topic}\" has concluded after "
        f"{config.current_turn} turns.\n"
        "Please provide a comprehensive summary of:\n\n"
        "1. Key ideas discussed\n"
        "2. Decisions made\n"
        "3. Open questions remaining\n"
        "4. Recommended next steps\n\n"
        "Be concise but thorough. Format as markdown."
    ]

    if config.deliverables:
        parts.append(
            "\n## Deliverables Assessment\n\n"
            "The following deliverables were expected:\n"
            + "\n".join(f"- {d}" for d in config.deliverables)
            + "\n\nPlease assess which were produced and their completeness."
        )

    return "\n".join(parts)


def build_deliverable_prompt(
    config: SessionConfig,
    deliverable_name: str,
    memories_text: str,
    conversation_text: str,
) -> str:
    """Build a prompt to compile a single deliverable from session materials.

    Args:
        config: The session configuration.
        deliverable_name: Name of the deliverable to compile.
        memories_text: Combined memory contents from both agents.
        conversation_text: The full conversation log.

    Returns:
        The compilation prompt string.
    """
    return (
        f"# Deliverable Compilation\n\n"
        f"The brainstorming session on \"{config.topic}\" has concluded.\n"
        f"Please compile the following deliverable from the session materials:\n\n"
        f"**Deliverable:** {deliverable_name}\n\n"
        f"Produce a clean, well-structured markdown document. Include all relevant\n"
        f"information discussed during the session. Do not include preamble or\n"
        f"meta-commentary — just the deliverable content.\n\n"
        f"---\n\n"
        f"## Agent Memories\n\n{memories_text}\n\n"
        f"---\n\n"
        f"## Conversation Log\n\n{conversation_text}"
    )
