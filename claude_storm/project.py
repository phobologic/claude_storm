"""Project directory configuration and conversation pacing."""

from __future__ import annotations

import tomllib
from pathlib import Path

STORM_CONFIG_FILENAME = "storm.toml"
STORMS_DIR_NAME = ".storms"

_TEMPLATE = '''\
[session]
topic = """
{topic}
"""

# goal = """
# Produce a detailed document covering the key aspects of the topic.
# """

# role_a = """
# Subject Matter Expert - Deep domain knowledge and practical experience.
# """

# role_b = """
# Critical Analyst - Focuses on gaps, risks, and alternative perspectives.
# """

# deliverables = [
#     "Summary document",
# ]

[options]
# max_turns = 20
# model = "sonnet"
# auto_complete = true
# interactive = false
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
    if config_path is not None:
        base = config_path.parent
    else:
        base = Path.cwd()
    return base / STORMS_DIR_NAME


def format_pacing_block(turn: int, max_turns: int, deliverables: list[str] | None = None) -> str:
    """Compute percentage-based pacing nudge for a turn prompt.

    Args:
        turn: Current turn number (1-based).
        max_turns: Total turn budget.
        deliverables: Optional list of expected deliverables.

    Returns:
        Formatted pacing block string.
    """
    pct = int((turn / max_turns) * 100)
    remaining = max_turns - turn

    parts = [f"=== TURN {turn} of {max_turns} ({pct}%) ==="]

    if remaining < 2:
        parts.append(
            "This is one of the final turns. Prioritize completing artifacts "
            "and capturing remaining decisions."
        )
    elif pct >= 75:
        parts.append(
            "Session is 75% complete. Focus on producing deliverables "
            "and resolving open questions."
        )
    elif pct >= 50:
        parts.append(
            "You're at the halfway point. Start narrowing down "
            "and committing to approaches."
        )
    else:
        parts.append("Continue the brainstorm. Save important ideas with [MEMORY].")

    if deliverables:
        parts.append(
            "\nExpected deliverables: " + ", ".join(deliverables)
        )

    return "\n".join(parts)
