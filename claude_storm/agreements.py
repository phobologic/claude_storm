"""Shared agreement protocol for brainstorming sessions."""

from __future__ import annotations

from uuid import uuid4

from claude_storm.config import SessionConfig


def generate_proposal_id() -> str:
    """Generate a 4-character hex ID for a proposal."""
    return uuid4().hex[:4]


def create_proposal(
    config: SessionConfig,
    title: str,
    content: str,
    agent: str,
    turn: int,
    revises: str | None = None,
) -> str:
    """Store a pending proposal and return the assigned ID.

    Args:
        config: The session configuration.
        title: Short title for the proposal.
        content: Full proposal content.
        agent: Which agent proposed ('a' or 'b').
        turn: The turn number when proposed.
        revises: ID of an existing agreement being revised, if any.

    Returns:
        The generated proposal ID.
    """
    proposal_id = generate_proposal_id()
    config.pending_proposals.append({
        "id": proposal_id,
        "title": title,
        "content": content,
        "proposed_by": agent,
        "turn": turn,
        "revises": revises,
    })
    return proposal_id


def accept_proposal(
    config: SessionConfig,
    proposal_id: str,
    turn: int,
) -> dict | None:
    """Accept a pending proposal and move it to confirmed agreements.

    Args:
        config: The session configuration.
        proposal_id: The ID of the proposal to accept.
        turn: The turn number when accepted.

    Returns:
        The accepted agreement dict, or None if proposal not found.
    """
    proposal = None
    for i, p in enumerate(config.pending_proposals):
        if p["id"] == proposal_id:
            proposal = config.pending_proposals.pop(i)
            break

    if proposal is None:
        return None

    agreement = {
        "id": proposal["id"],
        "title": proposal["title"],
        "content": proposal["content"],
        "proposed_by": proposal["proposed_by"],
        "proposed_turn": proposal["turn"],
        "accepted_turn": turn,
        "revises": proposal.get("revises"),
    }
    config.accepted_agreements.append(agreement)
    write_agreements_file(config)
    return agreement


def reject_proposal(
    config: SessionConfig,
    proposal_id: str,
) -> dict | None:
    """Remove a pending proposal (rejected).

    Args:
        config: The session configuration.
        proposal_id: The ID of the proposal to reject.

    Returns:
        The removed proposal dict, or None if not found.
    """
    for i, p in enumerate(config.pending_proposals):
        if p["id"] == proposal_id:
            return config.pending_proposals.pop(i)
    return None


def write_agreements_file(config: SessionConfig) -> None:
    """Rewrite agreements.md from accepted_agreements."""
    path = config.session_dir() / "agreements.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    parts: list[str] = []
    for a in config.accepted_agreements:
        label = "Agent A" if a["proposed_by"] == "a" else "Agent B"
        if a.get("revises"):
            header = f"## [{a['revises']} \u2192 {a['id']}] {a['title']} (revised)"
            meta = (
                f"**Original:** Turn {a.get('revises', '?')} | "
                f"**Revised:** Turn {a['proposed_turn']} by {label} | "
                f"**Accepted:** Turn {a['accepted_turn']}"
            )
        else:
            header = f"## [{a['id']}] {a['title']}"
            meta = (
                f"**Proposed:** Turn {a['proposed_turn']} by {label} | "
                f"**Accepted:** Turn {a['accepted_turn']}"
            )
        parts.append(f"{header}\n{meta}\n\n{a['content']}")

    path.write_text("\n\n---\n\n".join(parts) + "\n" if parts else "")


def format_agreements_for_prompt(
    config: SessionConfig,
    current_agent: str,
) -> str:
    """Format confirmed and pending agreements for inclusion in a turn prompt.

    Args:
        config: The session configuration.
        current_agent: The agent whose turn it is ('a' or 'b').

    Returns:
        Formatted agreements text, or empty string if none.
    """
    sections: list[str] = []

    # Confirmed agreements
    if config.accepted_agreements:
        lines = ["## Confirmed"]
        for a in config.accepted_agreements:
            lines.append(
                f"- [{a['id']}] **{a['title']}** "
                f"(Turn {a['proposed_turn']}\u2192{a['accepted_turn']})"
            )
            lines.append(f"  {a['content']}")
        sections.append("\n".join(lines))

    # Pending proposals awaiting the current agent's response
    other_agent = "b" if current_agent == "a" else "a"
    pending_for_me = [
        p for p in config.pending_proposals if p["proposed_by"] == other_agent
    ]
    if pending_for_me:
        lines = ["## Pending Proposals (awaiting your response)"]
        for p in pending_for_me:
            proposer = "Agent A" if p["proposed_by"] == "a" else "Agent B"
            lines.append(
                f"- [{p['id']}] **{p['title']}** "
                f"(proposed by {proposer}, Turn {p['turn']})"
            )
            lines.append(f"  {p['content']}")
            lines.append(
                f'  \u2192 Use [ACCEPT id="{p["id"]}"] or '
                f'[REJECT id="{p["id"]}" reason="..."]'
            )
        sections.append("\n".join(lines))

    if not sections:
        return ""

    return "# Shared Agreements\n\n" + "\n\n".join(sections)
