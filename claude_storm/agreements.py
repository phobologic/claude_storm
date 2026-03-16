"""Shared agreement protocol for brainstorming sessions."""

from __future__ import annotations

import re
from typing import NamedTuple, NotRequired, TypedDict
from uuid import uuid4

from claude_storm.config import SessionConfig, slugify


class ProposalDict(TypedDict):
    """Shape of a pending proposal dict."""

    id: str
    title: str
    content: str
    proposed_by: str
    turn: int
    revises: str | None
    summary: str
    original_content: NotRequired[str]
    original_turn: NotRequired[int]
    original_agent: NotRequired[str]


class AgreementDict(TypedDict):
    """Shape of an accepted agreement dict."""

    id: str
    title: str
    content: str
    proposed_by: str
    proposed_turn: int
    accepted_turn: int
    revises: str | None
    summary: str
    original_content: NotRequired[str]
    original_turn: NotRequired[int]
    original_agent: NotRequired[str]


class RejectionDict(TypedDict):
    """Shape of a rejected proposal record."""

    id: str
    title: str
    proposed_by: str
    proposed_turn: int
    rejected_turn: int
    reason: str


class RevisionContext(NamedTuple):
    """Context resolved for a REVISE directive target.

    Bundles the target ID with the original content so the revision
    fields are always present or absent as a group.
    """

    revises: str
    title: str
    original_content: str | None
    original_turn: int | None
    original_agent: str | None


_ORIGINAL_FIELDS = ("original_content", "original_turn", "original_agent")


def generate_proposal_id() -> str:
    """Generate a 4-character hex ID for a proposal."""
    return uuid4().hex[:4]


def _extract_summary(content: str) -> str:
    """Extract a compact summary from agreement/proposal content.

    Takes the first line, strips markdown heading prefixes, and truncates
    to 120 characters.

    Args:
        content: The full agreement or proposal content.

    Returns:
        A one-line summary string.
    """
    first_line = content.strip().split("\n")[0][:120]
    return re.sub(r"^#+\s*", "", first_line)


def _slugify(title: str) -> str:
    """Convert a title to a filename-safe slug.

    Args:
        title: The title to slugify.

    Returns:
        A lowercase, hyphenated slug truncated to 60 characters.
    """
    return slugify(title)


def _agreement_filename(agreement: dict) -> str:
    """Build a per-agreement filename from its ID and title.

    Args:
        agreement: An agreement dict with 'id' and 'title' keys.

    Returns:
        Filename like ``a3f2_use-rest.md``.
    """
    slug = _slugify(agreement["title"])
    return f"{agreement['id']}_{slug}.md"


def create_proposal(
    config: SessionConfig,
    title: str,
    content: str,
    agent: str,
    turn: int,
    revision: RevisionContext | None = None,
) -> str:
    """Store a pending proposal and return the assigned ID.

    Args:
        config: The session configuration.
        title: Short title for the proposal.
        content: Full proposal content.
        agent: Which agent proposed ('a' or 'b').
        turn: The turn number when proposed.
        revision: Context from the original proposal/agreement being
            revised.  Carries the target ID and original content so the
            accepted agreement file is self-contained.

    Returns:
        The generated proposal ID.
    """
    existing_ids = {p["id"] for p in config.pending_proposals} | {
        a["id"] for a in config.accepted_agreements
    }
    proposal_id = generate_proposal_id()
    while proposal_id in existing_ids:
        proposal_id = generate_proposal_id()
    proposal: dict = {
        "id": proposal_id,
        "title": title,
        "content": content,
        "proposed_by": agent,
        "turn": turn,
        "revises": revision.revises if revision else None,
        "summary": _extract_summary(content),
    }
    if revision and revision.original_content is not None:
        proposal["original_content"] = revision.original_content
        proposal["original_turn"] = revision.original_turn
        proposal["original_agent"] = revision.original_agent
    config.pending_proposals.append(proposal)
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

    agreement: dict = {
        "id": proposal["id"],
        "title": proposal["title"],
        "content": proposal["content"],
        "proposed_by": proposal["proposed_by"],
        "proposed_turn": proposal["turn"],
        "accepted_turn": turn,
        "revises": proposal.get("revises"),
        "summary": proposal.get("summary", _extract_summary(proposal["content"])),
    }
    # Copy original_* fields atomically — all three or none
    if proposal.get("original_content") is not None:
        for key in _ORIGINAL_FIELDS:
            agreement[key] = proposal.get(key)
    config.accepted_agreements.append(agreement)
    write_agreement_files(config)
    return agreement


def reject_proposal(
    config: SessionConfig,
    proposal_id: str,
    reason: str = "",
    turn: int = 0,
) -> dict | None:
    """Remove a pending proposal (rejected) and record the rejection.

    Args:
        config: The session configuration.
        proposal_id: The ID of the proposal to reject.
        reason: The reason for rejection.
        turn: The turn number when rejected.

    Returns:
        The removed proposal dict, or None if not found.
    """
    for i, p in enumerate(config.pending_proposals):
        if p["id"] == proposal_id:
            rejection: dict = {
                "id": proposal_id,
                "title": p["title"],
                "proposed_by": p["proposed_by"],
                "proposed_turn": p["turn"],
                "rejected_turn": turn,
                "reason": reason,
            }
            config.rejected_proposals.append(rejection)
            config.save()
            return config.pending_proposals.pop(i)
    return None


def _format_agreement_block(a: dict) -> str:
    """Format a single agreement as a markdown block.

    For revisions that carry ``original_content``, both the original
    proposal and the revision are rendered so the file is self-contained.

    Args:
        a: An accepted agreement dict.

    Returns:
        Markdown string with header, metadata, and content.
    """
    label = "Agent A" if a["proposed_by"] == "a" else "Agent B"

    if a.get("revises"):
        header = f"## [{a['revises']} \u2192 {a['id']}] {a['title']} (revised)"
        orig_turn = a.get("original_turn", "?")
        orig_agent = a.get("original_agent")
        orig_label = (
            f" by {'Agent A' if orig_agent == 'a' else 'Agent B'}" if orig_agent else ""
        )
        meta = (
            f"**Original:** Turn {orig_turn}{orig_label} | "
            f"**Revised:** Turn {a['proposed_turn']} by {label} | "
            f"**Accepted:** Turn {a['accepted_turn']}"
        )
        if a.get("original_content") is not None:
            body = (
                f"### Original proposal\n{a['original_content']}\n\n"
                f"### Revisions\n{a['content']}"
            )
        else:
            body = a["content"]
    else:
        header = f"## [{a['id']}] {a['title']}"
        meta = (
            f"**Proposed:** Turn {a['proposed_turn']} by {label} | "
            f"**Accepted:** Turn {a['accepted_turn']}"
        )
        body = a["content"]

    return f"{header}\n{meta}\n\n{body}"


def write_agreement_files(config: SessionConfig) -> None:
    """Write per-agreement files and a combined agreements.md.

    Each accepted agreement is written to its own file in the
    ``agreements/`` subdirectory with a human-readable filename
    (e.g. ``a3f2_use-rest.md``).  A concatenated ``agreements.md``
    is also written for backwards compatibility and human reading.

    Stale files (from revoked/revised agreements) are removed.

    Args:
        config: The session configuration.
    """
    session_dir = config.session_dir()
    agreements_dir = session_dir / "agreements"
    agreements_dir.mkdir(parents=True, exist_ok=True)

    # Track current agreement IDs for stale-file cleanup
    current_ids = {a["id"] for a in config.accepted_agreements}

    # Write individual per-agreement files
    parts: list[str] = []
    for a in config.accepted_agreements:
        block = _format_agreement_block(a)
        parts.append(block)
        filename = _agreement_filename(a)
        (agreements_dir / filename).write_text(block + "\n")

    # Remove stale files whose ID prefix no longer matches any agreement
    for existing in agreements_dir.glob("*.md"):
        file_id = existing.stem.split("_", 1)[0]
        if file_id not in current_ids:
            existing.unlink()

    # Write combined agreements.md for backwards compat
    combined_path = session_dir / "agreements.md"
    combined_path.write_text("\n\n---\n\n".join(parts) + "\n" if parts else "")


def format_agreement_index(config: SessionConfig) -> str:
    """Format a compact index of confirmed agreements.

    Each entry shows the ID, title, turn range, summary, and the
    per-agreement file path so agents can read individual files.
    Superseded agreements (replaced by a revision) are marked as such
    so agents know which version is current.

    Args:
        config: The session configuration.

    Returns:
        Formatted index string, or empty string if no agreements.
    """
    if not config.accepted_agreements:
        return ""

    # Build set of superseded IDs (agreements replaced by a later revision)
    superseded = {a["revises"] for a in config.accepted_agreements if a.get("revises")}

    total = len(config.accepted_agreements)
    active_count = total - len(superseded)
    if superseded:
        lines = [f"You have {active_count} active agreement(s) ({total} total):"]
    else:
        lines = [f"You have {active_count} confirmed agreement(s):"]

    for a in config.accepted_agreements:
        summary = a.get("summary", _extract_summary(a["content"]))
        filename = _agreement_filename(a)
        if a["id"] in superseded:
            # Find which agreement superseded this one
            superseding_id = next(
                (
                    s["id"]
                    for s in config.accepted_agreements
                    if s.get("revises") == a["id"]
                ),
                "?",
            )
            lines.append(
                f"- ~~[{a['id']}]~~ ~~**{a['title']}**~~ "
                f"*(superseded by [{superseding_id}])*"
            )
        elif a.get("revises"):
            lines.append(
                f"- [{a['revises']} \u2192 {a['id']}] **{a['title']}** "
                f"(revised, Turn {a['proposed_turn']}\u2192{a['accepted_turn']}): "
                f"{summary}"
            )
            lines.append(f"  File: agreements/{filename}")
        else:
            lines.append(
                f"- [{a['id']}] **{a['title']}** "
                f"(Turn {a['proposed_turn']}\u2192{a['accepted_turn']}): "
                f"{summary}"
            )
            lines.append(f"  File: agreements/{filename}")
    return "\n".join(lines)


def format_agreements_for_compilation(config: SessionConfig) -> str:
    """Format the full content of all confirmed agreements for compilation.

    Used by the deliverable compiler which needs complete agreement text
    in a single prompt. Not for per-turn agent prompts.

    Args:
        config: The session configuration.

    Returns:
        Full-content agreements text, or empty string if none.
    """
    if not config.accepted_agreements:
        return ""

    parts = [_format_agreement_block(a) for a in config.accepted_agreements]
    return "\n\n---\n\n".join(parts)


def format_agreements_for_prompt(
    config: SessionConfig,
    current_agent: str,
    current_turn: int | None = None,
    watermark: dict | None = None,
) -> str:
    """Format agreements for inclusion in a per-turn agent prompt.

    Returns a compact index of confirmed agreements (not full content),
    full text of pending proposals awaiting response, and a file reference
    so agents can read ``agreements.md`` on demand.

    When a watermark is provided, only new/changed content is included to
    reduce redundancy on resumed turns.

    Args:
        config: The session configuration.
        current_agent: The agent whose turn it is ('a' or 'b').
        current_turn: The current turn number (1-indexed). When provided and
            >= 3 with no agreements, a nudge is returned instead of empty string.
        watermark: Agent's watermark dict with agreement_count and
            seen_proposal_ids. When None, full content is shown (first turn).

    Returns:
        Formatted agreements text, or empty string if none (unless nudge applies).
    """
    sections: list[str] = []

    # Compact index of confirmed agreements (no full content)
    confirmed = config.accepted_agreements
    wm_agreement_count = watermark["agreement_count"] if watermark else 0
    if confirmed:
        new_agreement_count = len(confirmed) - wm_agreement_count
        if watermark and new_agreement_count <= 0:
            # Agent already knows all confirmed agreements
            sections.append(
                f"## Confirmed\n"
                f"You have {len(confirmed)} confirmed agreement(s) (no changes)."
            )
        elif watermark and wm_agreement_count > 0:
            # Show count + only new entries
            new_agreements = confirmed[wm_agreement_count:]
            lines = [
                f"You have {len(confirmed)} confirmed agreement(s) "
                f"({new_agreement_count} new):"
            ]
            for a in new_agreements:
                summary = a.get("summary", _extract_summary(a["content"]))
                filename = _agreement_filename(a)
                lines.append(
                    f"- [{a['id']}] **{a['title']}** "
                    f"(Turn {a['proposed_turn']}\u2192{a['accepted_turn']}): "
                    f"{summary}"
                )
                lines.append(f"  File: agreements/{filename}")
            sections.append("## Confirmed\n" + "\n".join(lines))
        else:
            # First turn or no watermark: full index
            index = format_agreement_index(config)
            if index:
                sections.append(f"## Confirmed\n{index}")

    # Current agent's own pending proposals (awaiting other agent's response)
    other_agent = "b" if current_agent == "a" else "a"
    other_label = "Agent B" if current_agent == "a" else "Agent A"
    my_pending = [
        p for p in config.pending_proposals if p["proposed_by"] == current_agent
    ]
    if my_pending:
        lines = [f"## Your Pending Proposals (awaiting {other_label}'s response)"]
        for p in my_pending:
            lines.append(f"- [{p['id']}] **{p['title']}** (proposed Turn {p['turn']})")
        sections.append("\n".join(lines))

    # Pending proposals awaiting the current agent's response
    pending_for_me = [
        p for p in config.pending_proposals if p["proposed_by"] == other_agent
    ]
    if pending_for_me:
        seen_ids = set(watermark["seen_proposal_ids"]) if watermark else set()
        lines = ["## Pending Proposals (awaiting your response)"]
        for p in pending_for_me:
            if p["id"] in seen_ids:
                # Already-seen proposal: compact one-liner
                lines.append(
                    f"- [{p['id']}] **{p['title']}** (still pending"
                    " — you must respond this turn: ACCEPT, REJECT, or REVISE)"
                )
            else:
                # New proposal: full content with instructions
                proposer = "Agent A" if p["proposed_by"] == "a" else "Agent B"
                # Truncate proposal content to prevent excessively long prompts
                content = p["content"][:2000] if p["content"] else ""
                lines.append(
                    f"- [{p['id']}] **{p['title']}** "
                    f"(proposed by {proposer}, Turn {p['turn']})"
                )
                lines.append(f"  {content}")
                lines.append(
                    f'  \u2192 Use [ACCEPT id="{p["id"]}"] or '
                    f'[REJECT id="{p["id"]}" reason="..."] or '
                    f'[REVISE id="{p["id"]}"]...revised content...[/REVISE]'
                )
        sections.append("\n".join(lines))

    if not sections:
        # No agreements or proposals — check if we should nudge
        if current_turn is not None and current_turn >= 3:
            return (
                "# Shared Agreements\n\n"
                "No agreements yet. Use [PROPOSE] when you reach consensus "
                "\u2014 verbal agreement alone does not create a shared record."
            )
        return ""

    result = "# Shared Agreements\n\n" + "\n\n".join(sections)

    # File reference so agents can read full agreement text on demand
    if confirmed:
        session_dir = config.session_dir()
        result += (
            f"\n\nEach agreement is saved to its own file in "
            f"`{session_dir}/agreements/` (see the File path "
            f"listed next to each agreement above). Use your "
            f"Read tool on the specific file when you need to "
            f"review or revise an agreement."
        )

    # Stale agreement nudge: if agreements exist but the last one was accepted
    # 4+ turns ago, remind the agent to formalize new consensus points
    if current_turn is not None and confirmed and not pending_for_me:
        last_accepted_turn = max(a["accepted_turn"] for a in confirmed)
        if current_turn - last_accepted_turn >= 4:
            result += (
                "\n\n*Reminder: It has been several turns "
                "since the last agreement. "
                "If you've reached new consensus points, "
                "formalize them with [PROPOSE].*"
            )

    # Rejected proposals — differential via watermark, capped at 5
    if config.rejected_proposals:
        wm_rejected_count = watermark["rejected_count"] if watermark else 0
        new_rejections = config.rejected_proposals[wm_rejected_count:]
        if new_rejections:
            show = new_rejections[-5:]
            lines = ["## Recent Rejections"]
            for r in show:
                is_mine = r["proposed_by"] == current_agent
                actor = "your proposal" if is_mine else f"{other_label}'s proposal"
                reason_suffix = f': "{r["reason"]}"' if r.get("reason") else ""
                lines.append(
                    f"- [{r['id']}] **{r['title']}** "
                    f"({actor}, rejected Turn {r['rejected_turn']}){reason_suffix}"
                )
            result += "\n\n" + "\n".join(lines)

    return result
