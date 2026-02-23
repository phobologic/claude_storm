"""Project directory configuration and conversation pacing."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

STORM_CONFIG_FILENAME = "storm.toml"
STORMS_DIR_NAME = ".storms"

# Pacing thresholds (percentage-based)
FINAL_PCT = 90
HIGH_PROGRESS_PCT = 75
MID_PROGRESS_PCT = 50
EARLY_PHASE_PCT = 20

_TEMPLATE = '''\
# Storm session configuration.
# CLI flags override values set here. Run `storm init --update` to add
# newly supported keys after upgrading.

[session]
# The subject or question for the brainstorm. Multi-line strings supported.
topic = """
{topic}
"""

# Desired outcome or success criterion — describes direction/quality,
# not a specific document. Reinforced in pacing nudges and used during
# post-session deliverable compilation.
# goal = """
# Favor battle-tested technologies; produce production-ready
# designs with clear trade-off analysis.
# """

# Agent personas. Each replaces Claude Code's default system prompt for
# that agent. The first line is used as the display label in the TUI —
# keep it short (e.g. a title). Additional lines provide detailed
# persona guidance.
# role_a = """
# Subject Matter Expert - Deep domain knowledge and practical experience.
# Favors pragmatic, battle-tested approaches.
# """
#
# role_b = """
# Critical Analyst - Focuses on gaps, risks, and alternative perspectives.
# Challenges assumptions and probes failure modes.
# """

# Documents to produce as [ARTIFACT] files. Drives pacing (agents are
# nudged to start drafts at 50% and finalize by 75%) and post-session
# compilation. Draft artifacts with matching filenames are used as
# foundations for the final compiled versions.
# deliverables = [
#     "Summary document",
# ]

# Read-only directories agents can browse via Read/Glob/Grep for
# background context. Agents cannot write to these paths.
# reference_dirs = ["/path/to/notes"]

[options]
# Turn budget — shapes percentage-based pacing (default: 20)
# max_turns = 20
# Wall-clock time limit in minutes; session pauses when exceeded (default: none)
# max_minutes = 60
# Claude model: "sonnet", "opus", or a full model ID (default: "sonnet")
# model = "sonnet"
# Let agents signal [DONE] when the topic is explored; both agents must
# agree before the session ends (default: true)
# auto_complete = true
# Enable user nudges and [ASK_USER] agent questions (default: false)
# interactive = false
# Truncate conversation to last ~50k chars when compiling deliverables,
# keeping token usage manageable for long sessions (default: true)
# truncate_conversation = true
# Per-turn agent timeout in seconds (default: 600)
# agent_timeout = 600
'''


def load_project_config(config_path: Path | None) -> dict:
    """Parse a storm.toml file and return a flat config dict.

    Merges [session] and [options] sections. Multi-line string values
    are stripped of leading/trailing whitespace.

    Args:
        config_path: Path to the TOML file. If None, uses CWD/storm.toml.

    Returns:
        Flat dict with all config keys.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If required fields (topic) are missing.
    """
    if config_path is None:
        config_path = Path.cwd() / STORM_CONFIG_FILENAME

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    result: dict = {}

    # Flatten [session] section
    session = raw.get("session", {})
    for key, value in session.items():
        if isinstance(value, str):
            value = value.strip()
        result[key] = value

    # Flatten [options] section
    options = raw.get("options", {})
    for key, value in options.items():
        if isinstance(value, str):
            value = value.strip()
        result[key] = value

    if not result.get("topic"):
        raise ValueError("Config file must include a 'topic' in [session]")

    return result


def scaffold_config(path: Path, topic: str | None = None, force: bool = False) -> Path:
    """Write a template storm.toml file.

    Args:
        path: Directory to create the config in.
        topic: Optional topic to pre-fill.
        force: If True, overwrite existing file.

    Returns:
        Path to the created file.

    Raises:
        FileExistsError: If config already exists and force is False.
    """
    config_file = path / STORM_CONFIG_FILENAME
    if config_file.exists() and not force:
        raise FileExistsError(f"Config already exists: {config_file}")

    content = _TEMPLATE.format(topic=topic or "Describe your brainstorming topic here")
    config_file.write_text(content)
    return config_file


def get_storms_dir(config_path: Path | None) -> Path:
    """Resolve the .storms/ directory relative to the config file location.

    Args:
        config_path: Path to a storm.toml file, or None for CWD.

    Returns:
        Absolute path to the .storms/ directory.
    """
    base = config_path.parent if config_path is not None else Path.cwd()
    return base / STORMS_DIR_NAME


def _final_turn_message(goal: str | None, deliverables: list[str] | None) -> str:
    """Build pacing message for the final turns."""
    msg = (
        "This is one of the final turns. Prioritize completing artifacts "
        "and capturing remaining decisions. "
        "Your deliverable artifacts should already exist from earlier turns — "
        "finalize and update them now."
    )
    if goal:
        msg += f' Session goal: "{goal}" — ensure final output addresses this.'
    if deliverables:
        deliv_list = ", ".join(deliverables)
        msg += (
            f"\n\nIMPORTANT: Before signaling [DONE], produce an "
            f'[ARTIFACT filename="..."] for each deliverable '
            f"not yet produced: {deliv_list}. "
            f"If you've already produced them, signal [DONE]."
        )
    return msg


def _high_progress_message(goal: str | None) -> str:
    """Build pacing message for 75%+ progress."""
    msg = (
        "Session is 75% complete. Finalize deliverable artifacts now. "
        "Update or produce `[ARTIFACT]` files for each expected deliverable — "
        "these are working drafts that will be refined during compilation. "
        "Break large deliverables into multiple files "
        "(e.g., `part_1.md`, `part_2.md`). "
        "Focus on resolving open questions."
    )
    if goal:
        msg += f' Ensure output addresses the session goal: "{goal}"'
    return msg


def _mid_progress_message(goal: str | None) -> str:
    """Build pacing message for 50%+ progress."""
    msg = (
        "You're at the halfway point. Start narrowing down "
        "and committing to approaches. "
        "Start producing draft `[ARTIFACT]` files — write incremental sections "
        "for deliverables you have enough material for. These drafts will be "
        "refined during compilation. For large deliverables, break them into parts "
        "(e.g., `act_1_chapters.md`, `act_2a_chapters.md`). "
        "You can revise artifacts later."
    )
    if goal:
        msg += f' Keep the session goal in mind: "{goal}"'
    return msg


def _early_phase_message() -> str:
    """Build pacing message for early interactive exploration."""
    return (
        "Early exploration phase — this is the best time to use [ASK_USER] to "
        "confirm the user's intent, constraints, and preferences "
        "before the session narrows. "
        "Continue brainstorming."
    )


def _default_message() -> str:
    """Build the default pacing message."""
    return "Continue the brainstorm."


def format_pacing_block(
    turn: int,
    max_turns: int | None,
    elapsed_s: float = 0.0,
    max_minutes: int | None = None,
    deliverables: list[str] | None = None,
    session_id: str | None = None,
    interactive: bool = False,
    goal: str | None = None,
    is_first_turn: bool = True,
) -> str:
    """Compute percentage-based pacing nudge for a turn prompt.

    Args:
        turn: Current turn number (1-based).
        max_turns: Total turn budget, or None when only time-limited.
        elapsed_s: Elapsed wall-clock seconds (excluding interactive pauses).
        max_minutes: Time budget in minutes, or None when only turn-limited.
        deliverables: Optional list of expected deliverables.
        session_id: Optional session identifier to display.
        interactive: Whether the session is in interactive mode.
        goal: Optional session goal to reinforce in pacing nudges.
        is_first_turn: Whether this is the agent's first turn. When False,
            the deliverables/goal footer is omitted (already in system prompt).

    Returns:
        Formatted pacing block string.
    """
    turn_pct = int((turn / max_turns) * 100) if max_turns else None
    time_pct = int((elapsed_s / 60 / max_minutes) * 100) if max_minutes else None

    active_pcts = [p for p in [turn_pct, time_pct] if p is not None]
    effective_pct = min(max(active_pcts), 100) if active_pcts else 0

    # Build progress header line
    progress_parts: list[str] = []
    if max_turns is not None:
        progress_parts.append(f"Turn {turn}/{max_turns} ({turn_pct}%)")
    if max_minutes is not None:
        elapsed_min = int(elapsed_s / 60)
        progress_parts.append(
            f"Time {elapsed_min}/{max_minutes} min ({min(time_pct, 100)}%)"
        )
    progress_str = " | ".join(progress_parts) if progress_parts else f"Turn {turn}"

    if session_id:
        parts = [f"## Session {session_id} — {progress_str}"]
    else:
        parts = [f"## {progress_str}"]

    if effective_pct >= FINAL_PCT:
        parts.append(_final_turn_message(goal, deliverables))
    elif effective_pct >= HIGH_PROGRESS_PCT:
        parts.append(_high_progress_message(goal))
    elif effective_pct >= MID_PROGRESS_PCT:
        parts.append(_mid_progress_message(goal))
    elif effective_pct <= EARLY_PHASE_PCT and interactive:
        parts.append(_early_phase_message())
    else:
        parts.append(_default_message())

    if is_first_turn:
        if deliverables:
            parts.append("\n**Expected deliverables:** " + ", ".join(deliverables))
        elif goal:
            parts.append(f"\n**Session goal:** {goal}")

    return "\n".join(parts)


# Known config keys with their section, commented default, and a pattern to detect them.
_KNOWN_KEYS: list[tuple[str, str, str]] = [
    # (key_name, section, commented_default_line)
    ("reference_dirs", "session", '# reference_dirs = ["/path/to/notes"]'),
    ("max_turns", "options", "# max_turns = 20"),
    ("max_minutes", "options", "# max_minutes = 60"),
    ("model", "options", '# model = "sonnet"'),
    ("auto_complete", "options", "# auto_complete = true"),
    ("interactive", "options", "# interactive = false"),
    ("truncate_conversation", "options", "# truncate_conversation = true"),
    ("agent_timeout", "options", "# agent_timeout = 600"),
]


def migrate_config(config_path: Path) -> list[str]:
    """Migrate a storm.toml to the latest schema.

    Reads the raw TOML text, detects missing or renamed keys, and rewrites
    the file with commented defaults appended where needed.

    Returns a list of human-readable messages describing changes made.
    """
    text = config_path.read_text()
    messages: list[str] = []

    # --- Migration 1: reference_dir → reference_dirs ---
    # Uncommented: reference_dir = "..."  →  reference_dirs = ["..."]
    uncommented = re.search(r'^reference_dir\s*=\s*"([^"]*)"', text, re.MULTILINE)
    if uncommented:
        old_val = uncommented.group(1)
        if old_val:
            replacement = f'reference_dirs = ["{old_val}"]'
        else:
            replacement = '# reference_dirs = ["/path/to/notes"]'
        text = text[: uncommented.start()] + replacement + text[uncommented.end() :]
        messages.append("Renamed reference_dir → reference_dirs")
    else:
        # Commented: # reference_dir = "..."  →  # reference_dirs = ["/path/to/notes"]
        commented = re.search(r"^#\s*reference_dir\s*=", text, re.MULTILINE)
        if commented:
            text = (
                text[: commented.start()]
                + '# reference_dirs = ["/path/to/notes"]'
                + text[commented.end() :]
            )
            # Trim the rest of the old commented line
            # end() points past '# reference_dir ='; eat rest of line
            rest_match = re.search(r"^.*$", text[commented.start() :], re.MULTILINE)
            if rest_match:
                line_end = commented.start() + rest_match.end()
                text = (
                    text[: commented.start()]
                    + '# reference_dirs = ["/path/to/notes"]'
                    + text[line_end:]
                )
            messages.append("Updated commented reference_dir → reference_dirs")

    # --- Migration 2: Append missing keys ---
    for key_name, section, commented_default in _KNOWN_KEYS:
        # Check if key already present (commented or uncommented)
        pattern = rf"^#?\s*{re.escape(key_name)}\s*="
        if re.search(pattern, text, re.MULTILINE):
            continue

        # Key is missing — append to the appropriate section
        section_header = f"[{section}]"
        if section_header in text:
            # Insert before the next section header or at end of file
            idx = text.index(section_header) + len(section_header)
            # Find the next section header
            next_section = re.search(r"^\[", text[idx:], re.MULTILINE)
            if next_section:
                insert_pos = idx + next_section.start()
                text = text[:insert_pos] + commented_default + "\n" + text[insert_pos:]
            else:
                # Append at end
                if not text.endswith("\n"):
                    text += "\n"
                text += commented_default + "\n"
        else:
            # Section doesn't exist — append section + key
            if not text.endswith("\n"):
                text += "\n"
            text += f"\n{section_header}\n{commented_default}\n"

        messages.append(f"Added missing key: {key_name}")

    if messages:
        config_path.write_text(text)

    return messages
