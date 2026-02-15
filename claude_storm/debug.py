"""Debug logging utilities for Claude Storm."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
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
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append(f"=== Turn {turn} - {agent_label} === [{timestamp}]")
    lines.append("")

    if system_prompt is not None:
        sp_chars = len(system_prompt)
        sp_lines = system_prompt.count("\n") + 1
        lines.append(
            f"--- SYSTEM PROMPT --- [{sp_chars:,} chars \u00b7 {sp_lines:,} lines]"
        )
        lines.append(system_prompt)
        lines.append("")

    tp_chars = len(turn_prompt)
    tp_lines = turn_prompt.count("\n") + 1
    lines.append(f"--- TURN PROMPT --- [{tp_chars:,} chars \u00b7 {tp_lines:,} lines]")
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

    if "usage" in raw_response:
        usage = raw_response["usage"]
        lines.append("--- USAGE SUMMARY ---")
        lines.append(f"Input: {usage.get('input_tokens', 0):,}")
        lines.append(f"Output: {usage.get('output_tokens', 0):,}")
        if "total_cost_usd" in raw_response:
            lines.append(f"Cost: ${raw_response['total_cost_usd']:.4f}")
        if "iterations" in usage:
            lines.append(f"Compaction iterations: {len(usage['iterations'])}")
        lines.append("")

    # Human-readable response excerpt
    result_text = raw_response.get("result", "")
    if result_text:
        excerpt_lines = result_text.split("\n")[:80]
        lines.append("--- RESPONSE TEXT (first 80 lines) ---")
        lines.append("\n".join(excerpt_lines))
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


def write_debug_phase_banner(log_path: Path, phase_name: str) -> None:
    """Write a phase separator banner to the debug log.

    Args:
        log_path: Path to the log file.
        phase_name: Name of the phase (e.g. "COMPILATION PHASE").
    """
    lines = [
        "",
        "=======================================",
        f"=== {phase_name} ===",
        "=======================================",
        "",
    ]
    _append_restricted(log_path, "\n".join(lines))


def _format_duration(seconds: int) -> str:
    """Format a duration in seconds as 'Xm Ys'."""
    minutes, secs = divmod(seconds, 60)
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def write_debug_summary(
    log_path: Path,
    config: object,
    duration_s: int | None,
) -> None:
    """Write a session summary footer to the debug log.

    Args:
        log_path: Path to the log file.
        config: SessionConfig instance.
        duration_s: Total session duration in seconds, or None.
    """
    lines = [
        "",
        "=======================================",
        "=== SESSION SUMMARY ===",
        "=======================================",
        f"Turns: {config.current_turn}/{config.max_turns}",  # type: ignore[attr-defined]
    ]
    if duration_s is not None:
        lines.append(f"Duration: {_format_duration(duration_s)}")

    status = config.status  # type: ignore[attr-defined]
    if config.stop_reason:  # type: ignore[attr-defined]
        lines.append(f"Status: {status} ({config.stop_reason})")  # type: ignore[attr-defined]
    else:
        lines.append(f"Status: {status}")

    # Aggregate totals from watermarks
    total_cost = 0.0
    total_in = 0
    total_out = 0
    total_compactions = 0
    agent_lines: list[str] = []
    for agent_key in ("a", "b"):
        wm = config.get_watermark(agent_key)  # type: ignore[attr-defined]
        cost = wm.get("total_cost_usd", 0.0)
        inp = wm.get("total_input_tokens", 0)
        out = wm.get("total_output_tokens", 0)
        comp = wm.get("compaction_count", 0)
        total_cost += cost
        total_in += inp
        total_out += out
        total_compactions += comp
        label = config.agent_label(agent_key)  # type: ignore[attr-defined]
        agent_lines.append(
            f"  {label}: ${cost:.4f}"
            f" \u00b7 In: {inp:,} Out: {out:,}"
            f" \u00b7 Compactions: {comp}"
        )

    if total_cost > 0:
        lines.append(f"Total cost: ${total_cost:.4f}")
    if total_in > 0 or total_out > 0:
        lines.append(f"Total tokens \u2014 In: {total_in:,}  Out: {total_out:,}")
    lines.append(f"Compactions: {total_compactions}")
    lines.append("")
    lines.append("Per-agent breakdown:")
    lines.extend(agent_lines)
    lines.append("")
    lines.append("")

    _append_restricted(log_path, "\n".join(lines))
