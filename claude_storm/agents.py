"""Claude CLI subprocess wrapper with session management."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from claude_storm.config import SessionConfig


@dataclass
class AgentResponse:
    """Parsed response from a Claude CLI invocation."""

    text: str
    raw: dict
    cmd: list[str] = None
    is_error: bool = False


def _get_session_id(config: SessionConfig, agent: str) -> str:
    """Return the Claude CLI session UUID for an agent."""
    return config.claude_session_a if agent == "a" else config.claude_session_b


def _abs_pattern(path: str) -> str:
    """Convert an absolute path to a // prefixed glob pattern.

    The // prefix in allowedTools means 'from filesystem root',
    so /some/path becomes //some/path/**.
    """
    # Strip leading slash since // already implies root
    stripped = path.lstrip("/")
    return f"//{stripped}/**"


def _build_allowed_tools(config: SessionConfig) -> list[str]:
    """Build path-scoped --allowedTools list.

    Write/Edit are restricted to the session directory.
    Read/Glob/Grep are restricted to the session directory plus any
    configured reference directory.
    """
    session_path = str(config.session_dir().resolve())

    # Readable directories: session dir + any reference dirs
    readable_dirs = [session_path]
    readable_dirs.extend(config.reference_dirs)

    tools: list[str] = []

    # Read-only tools scoped to all readable directories
    for d in readable_dirs:
        pattern = _abs_pattern(d)
        tools.append(f"Read({pattern})")
        tools.append(f"Glob({pattern})")
        tools.append(f"Grep({pattern})")

    # Write tools scoped to session directory only
    session_pattern = _abs_pattern(session_path)
    tools.append(f"Write({session_pattern})")
    tools.append(f"Edit({session_pattern})")

    return tools


def invoke_agent(
    config: SessionConfig,
    agent: str,
    prompt: str,
    system_prompt: str | None = None,
    timeout: int = 300,
) -> AgentResponse:
    """Invoke a Claude CLI session for an agent.

    On the first turn (when system_prompt is provided), uses --session-id to
    create a new session. On subsequent turns, uses --resume to continue
    the existing session.

    Args:
        config: The session configuration.
        agent: Which agent ('a' or 'b').
        prompt: The user prompt to send.
        system_prompt: System prompt (only for first turn).
        timeout: Per-turn timeout in seconds.

    Returns:
        AgentResponse with the agent's text response.
    """
    session_id = _get_session_id(config, agent)
    cwd = config.session_dir()

    cmd = ["claude", "-p", "--output-format", "json"]

    if system_prompt is not None:
        # First turn: create session with system prompt
        cmd.extend(["--session-id", session_id])
        cmd.extend(["--system-prompt", system_prompt])
        cmd.extend(["--model", config.model])
        cmd.extend(["--allowedTools"] + _build_allowed_tools(config))
    else:
        # Subsequent turns: resume existing session
        cmd.extend(["--resume", session_id])

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return AgentResponse(
            text="[Agent timed out]",
            raw={"error": "timeout"},
            cmd=cmd,
            is_error=True,
        )

    if result.returncode != 0:
        return AgentResponse(
            text=f"[Agent error: {result.stderr.strip()}]",
            raw={"error": result.stderr.strip(), "returncode": result.returncode},
            cmd=cmd,
            is_error=True,
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        # Fall back to raw text if JSON parsing fails
        return AgentResponse(
            text=result.stdout.strip(),
            raw={"raw_output": result.stdout.strip()},
            cmd=cmd,
        )

    # Extract text from JSON response
    text = _extract_text(data)
    return AgentResponse(text=text, raw=data, cmd=cmd)


def _extract_text(data: dict) -> str:
    """Extract text content from Claude CLI JSON output.

    The JSON output format has a 'result' field containing the response text,
    or a list of content blocks.
    """
    if isinstance(data, dict):
        # Standard format: {"result": "text"}
        if "result" in data:
            return data["result"]
        # Content blocks format
        if "content" in data and isinstance(data["content"], list):
            parts = []
            for block in data["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block["text"])
            return "\n".join(parts)
    return str(data)
