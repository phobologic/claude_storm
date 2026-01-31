"""Project directory configuration and conversation pacing."""

from __future__ import annotations

import re
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

# reference_dirs = ["/path/to/notes"]

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

    parts = [f"## Turn {turn} of {max_turns} ({pct}%)"]

    if remaining < 2:
        msg = (
            "This is one of the final turns. Prioritize completing artifacts "
            "and capturing remaining decisions."
        )
        if deliverables:
            deliv_list = ", ".join(deliverables)
            msg += (
                f"\n\nIMPORTANT: Before signaling [DONE], produce an "
                f'[ARTIFACT filename="..."] for each deliverable not yet produced: {deliv_list}. '
                f"If you've already produced them, signal [DONE]."
            )
        parts.append(msg)
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
            "\n**Expected deliverables:** " + ", ".join(deliverables)
        )

    return "\n".join(parts)


# Known config keys with their section, commented default, and a pattern to detect them.
_KNOWN_KEYS: list[tuple[str, str, str]] = [
    # (key_name, section, commented_default_line)
    ("reference_dirs", "session", '# reference_dirs = ["/path/to/notes"]'),
    ("max_turns", "options", "# max_turns = 20"),
    ("model", "options", '# model = "sonnet"'),
    ("auto_complete", "options", "# auto_complete = true"),
    ("interactive", "options", "# interactive = false"),
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
        commented = re.search(r'^#\s*reference_dir\s*=', text, re.MULTILINE)
        if commented:
            text = (
                text[: commented.start()]
                + '# reference_dirs = ["/path/to/notes"]'
                + text[commented.end() :]
            )
            # Trim the rest of the old commented line
            # The end() above points past '# reference_dir =', need to eat the rest of line
            rest_match = re.search(r'^.*$', text[commented.start():], re.MULTILINE)
            if rest_match:
                line_end = commented.start() + rest_match.end()
                text = text[:commented.start()] + '# reference_dirs = ["/path/to/notes"]' + text[line_end:]
            messages.append("Updated commented reference_dir → reference_dirs")

    # --- Migration 2: Append missing keys ---
    for key_name, section, commented_default in _KNOWN_KEYS:
        # Check if key already present (commented or uncommented)
        pattern = rf'^#?\s*{re.escape(key_name)}\s*='
        if re.search(pattern, text, re.MULTILINE):
            continue

        # Key is missing — append to the appropriate section
        section_header = f"[{section}]"
        if section_header in text:
            # Insert before the next section header or at end of file
            idx = text.index(section_header) + len(section_header)
            # Find the next section header
            next_section = re.search(r'^\[', text[idx:], re.MULTILINE)
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
