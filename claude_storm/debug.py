"""Debug logging and pause utilities for Claude Storm."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console


def write_debug_entry(
    log_path: Path,
    turn: int,
    agent_label: str,
    cmd: list[str],
    system_prompt: str | None,
    turn_prompt: str,
    raw_response: dict,
    directives: dict,
) -> None:
    """Append a formatted debug entry to the log file.

    Each entry is delimited by === lines and contains labeled sections
    for the CLI command, prompts, raw response, and parsed directives.
    """
    lines: list[str] = []
    lines.append(f"=== Turn {turn} - {agent_label} ===")
    lines.append("")

    lines.append("--- CLI COMMAND ---")
    lines.append(" ".join(cmd))
    lines.append("")

    if system_prompt is not None:
        lines.append("--- SYSTEM PROMPT ---")
        lines.append(system_prompt)
        lines.append("")

    lines.append("--- TURN PROMPT ---")
    lines.append(turn_prompt)
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

    with open(log_path, "a") as f:
        f.write("\n".join(lines))


def debug_pause(console: Console) -> None:
    """Print a debug prompt and wait for the user to press Enter."""
    console.input("[bold yellow][debug] Press Enter to continue...[/bold yellow]")
