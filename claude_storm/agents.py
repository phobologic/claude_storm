"""Claude CLI subprocess wrapper with session management."""

from __future__ import annotations

import json
import re
import subprocess
import threading
from dataclasses import dataclass

from claude_storm.config import SessionConfig

# Allowed model identifiers (prevents injection via model field)
_ALLOWED_MODELS = re.compile(r"^[a-zA-Z0-9._-]+$")

# Paths that should never be granted as reference directories
_SENSITIVE_PATHS = frozenset(
    {
        "/",
        "/etc",
        "/var",
        "/root",
        "/private",
        "/private/etc",
        "/private/var",
    }
)

# Maximum response size (10 MB) to prevent memory exhaustion
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024

_active_process: subprocess.Popen | None = None
_process_lock = threading.Lock()


def cancel_active() -> None:
    """Terminate the currently running agent subprocess, if any."""
    with _process_lock:
        proc = _active_process
    if proc is not None:
        proc.terminate()


@dataclass
class AgentResponse:
    """Parsed response from a Claude CLI invocation."""

    text: str
    raw: dict
    cmd: list[str] = None
    is_error: bool = False
    timed_out: bool = False


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


def _validate_reference_dir(path: str) -> bool:
    """Check whether a reference directory path is safe to use.

    Rejects paths that resolve to sensitive system directories.

    Args:
        path: The directory path to validate.

    Returns:
        True if the path is safe, False otherwise.
    """
    from pathlib import Path as _Path

    try:
        resolved = str(_Path(path).resolve())
    except (OSError, ValueError):
        return False
    return resolved not in _SENSITIVE_PATHS


def _validate_model(model: str) -> str:
    """Validate a model identifier and return it, or fall back to 'sonnet'.

    Args:
        model: The model identifier to validate.

    Returns:
        The model string if valid, otherwise 'sonnet'.
    """
    if _ALLOWED_MODELS.match(model):
        return model
    return "sonnet"


def _build_allowed_tools(config: SessionConfig, readonly: bool = False) -> list[str]:
    """Build path-scoped --allowedTools list.

    Write/Edit are restricted to the session directory.
    Read/Glob/Grep are restricted to the session directory plus any
    configured reference directory. Reference directories are
    re-validated at build time to guard against tampered session data.

    Args:
        config: The session configuration.
        readonly: When True, omit Write and Edit tools.
    """
    session_path = str(config.session_dir().resolve())

    # Readable directories: session dir + validated reference dirs
    readable_dirs = [session_path]
    for ref in config.reference_dirs:
        if _validate_reference_dir(ref):
            readable_dirs.append(ref)

    tools: list[str] = []

    # Read-only tools scoped to all readable directories
    for d in readable_dirs:
        pattern = _abs_pattern(d)
        tools.append(f"Read({pattern})")
        tools.append(f"Glob({pattern})")
        tools.append(f"Grep({pattern})")

    # Write tools scoped to session directory only
    if not readonly:
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
    session_id: str | None = None,
    readonly: bool = False,
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
        session_id: Override session ID. When provided, creates a fresh
            session instead of resuming the agent's brainstorming session.

    Returns:
        AgentResponse with the agent's text response.
    """
    resolved_session_id = session_id or _get_session_id(config, agent)
    cwd = config.session_dir()

    cmd = ["claude", "-p", "--output-format", "json"]
    validated_model = _validate_model(config.model)

    if system_prompt is not None:
        # First turn: create session with system prompt
        cmd.extend(["--session-id", resolved_session_id])
        cmd.extend(["--system-prompt", system_prompt])
        cmd.extend(["--model", validated_model])
        cmd.extend(["--allowedTools", *_build_allowed_tools(config, readonly=readonly)])
    elif session_id is not None:
        # Fresh one-shot session (no system prompt, no resume)
        cmd.extend(["--session-id", resolved_session_id])
        cmd.extend(["--model", validated_model])
        cmd.extend(["--allowedTools", *_build_allowed_tools(config, readonly=readonly)])
    else:
        # Subsequent turns: resume existing session
        cmd.extend(["--resume", resolved_session_id])
        cmd.extend(["--allowedTools", *_build_allowed_tools(config, readonly=readonly)])

    global _active_process
    try:
        with _process_lock:
            _active_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
            )
        try:
            stdout, stderr = _active_process.communicate(input=prompt, timeout=timeout)
            returncode = _active_process.returncode
        finally:
            with _process_lock:
                _active_process = None
    except subprocess.TimeoutExpired:
        with _process_lock:
            if _active_process is not None:
                _active_process.kill()
                _active_process = None
        return AgentResponse(
            text="[Agent timed out]",
            raw={"error": "timeout"},
            cmd=cmd,
            is_error=True,
            timed_out=True,
        )

    if returncode != 0:
        return AgentResponse(
            text=f"[Agent error: {stderr.strip()}]",
            raw={"error": stderr.strip(), "returncode": returncode},
            cmd=cmd,
            is_error=True,
        )

    # Guard against excessively large responses
    if len(stdout) > _MAX_RESPONSE_BYTES:
        return AgentResponse(
            text="[Agent response exceeded size limit]",
            raw={"error": "response_too_large", "size": len(stdout)},
            cmd=cmd,
            is_error=True,
        )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        # Fall back to raw text if JSON parsing fails
        return AgentResponse(
            text=stdout.strip(),
            raw={"raw_output": stdout.strip()},
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
