"""Debug logging utilities for Claude Storm."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _append_restricted(log_path: Path, content: str) -> None:
    """Append content to a log file with owner-only permissions (0o600).

    Creates the file with restricted permissions if it doesn't exist.

    Args:
        log_path: Path to the log file.
        content: Text content to append.
    """
    fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, content.encode())
    finally:
        os.close(fd)


def write_debug_request(
    log_path: Path,
    turn: int | str,
    agent_label: str,
    system_prompt: str | None,
    turn_prompt: str,
) -> None:
    """Write the request half of a debug entry (before agent invocation).

    Writes the turn header, system prompt (if any), and turn prompt.
    This is called before the agent is invoked so the prompts are
    visible even if the agent hangs or crashes.
    """
    lines: list[str] = []
    lines.append(f"=== Turn {turn} - {agent_label} ===")
    lines.append("")

    if system_prompt is not None:
        lines.append("--- SYSTEM PROMPT ---")
        lines.append(system_prompt)
        lines.append("")

    lines.append("--- TURN PROMPT ---")
    lines.append(turn_prompt)
    lines.append("")

    _append_restricted(log_path, "\n".join(lines))


def write_debug_response(
    log_path: Path,
    cmd: list[str],
    raw_response: dict,
    directives: dict,
) -> None:
    """Write the response half of a debug entry (after agent invocation).

    Writes the CLI command, raw response, and parsed directives.
    """
    lines: list[str] = []
    lines.append("--- CLI COMMAND ---")
    lines.append(" ".join(cmd))
    lines.append("")

    lines.append("--- RAW RESPONSE ---")
    lines.append(json.dumps(raw_response, indent=2))
    lines.append("")

    lines.append("--- DIRECTIVES ---")
    directive_summary = {
        "memories": [(t, tags) for t, tags, _ in directives.get("memories", [])],
        "memory_searches": directives.get("memory_searches", []),
        "artifacts": [f for f, _ in directives.get("artifacts", [])],
        "done": directives.get("done"),
        "ask_user": directives.get("ask_user"),
    }
    lines.append(json.dumps(directive_summary, indent=2))
    lines.append("")
    lines.append("")

    _append_restricted(log_path, "\n".join(lines))


def write_debug_entry(
    log_path: Path,
    turn: int | str,
    agent_label: str,
    cmd: list[str],
    system_prompt: str | None,
    turn_prompt: str,
    raw_response: dict,
    directives: dict,
) -> None:
    """Append a formatted debug entry to the log file.

    Thin wrapper that calls write_debug_request followed by
    write_debug_response, preserving the original all-at-once API.
    """
    write_debug_request(log_path, turn, agent_label, system_prompt, turn_prompt)
    write_debug_response(log_path, cmd, raw_response, directives)
