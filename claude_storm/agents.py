"""Claude CLI subprocess wrapper with session management."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import selectors
import signal as _signal
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from claude_storm.config import SessionConfig, _validate_reference_dir

_log = logging.getLogger(__name__)

# Allowed model identifiers (prevents injection via model field)
_ALLOWED_MODELS = re.compile(r"^[a-zA-Z0-9._-]+$")

# Maximum response size (10 MB) to prevent memory exhaustion
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024

# Maximum stderr we'll accumulate (1 MB) to prevent memory exhaustion
_MAX_STDERR_BYTES = 1_048_576


class _StreamResult(NamedTuple):
    """Result from reading a stream-json subprocess."""

    text: str
    result_event: dict | None
    timed_out: bool
    oversized: bool
    compaction_summary: str | None = None


_active_process: subprocess.Popen | None = None
_process_lock = threading.Lock()


def cancel_active() -> None:
    """Terminate the currently running agent subprocess, if any."""
    with _process_lock:
        proc = _active_process
    if proc is None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), _signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        # Process already dead or pgid unavailable — fall back to direct kill
        with contextlib.suppress(OSError):
            proc.kill()


@dataclass
class AgentResponse:
    """Parsed response from a Claude CLI invocation."""

    text: str
    raw: dict
    cmd: list[str] = None
    is_error: bool = False
    timed_out: bool = False
    compaction_summary: str | None = None
    usage: dict | None = None


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


def _parse_stream_event(line: str) -> tuple[str | None, dict | None]:
    """Parse one NDJSON line from stream-json output.

    Args:
        line: A single JSON line from the stream.

    Returns:
        Tuple of (text_delta or None, parsed_event or None).
        text_delta is set only for content_block_delta events with text_delta type.
    """
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        _log.debug("Unparseable stream line: %s", line[:200])
        return None, None

    if not isinstance(event, dict):
        return None, event

    if event.get("type") == "stream_event":
        inner = event.get("event", {})
        if (
            inner.get("type") == "content_block_delta"
            and isinstance(inner.get("delta"), dict)
            and inner["delta"].get("type") == "text_delta"
        ):
            return inner["delta"].get("text"), event
        return None, event

    # result and other top-level event types
    return None, event


def _read_stream(
    proc: subprocess.Popen,
    timeout: int,
    on_delta: Callable[[str], None] | None,
) -> _StreamResult:
    """Read NDJSON lines from a subprocess stdout with idle timeout.

    Uses selectors to detect idle periods. Each line of output resets the
    idle timer. If no output is received for ``timeout`` seconds, the
    process is killed.

    Args:
        proc: The subprocess to read from.
        timeout: Idle timeout in seconds.
        on_delta: Optional callback invoked with each text delta chunk.

    Returns:
        _StreamResult with accumulated text, last result event, and status flags.
    """
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)

    text_parts: list[str] = []
    total_bytes = 0
    result_event: dict | None = None
    timed_out = False
    oversized = False
    compaction_summary: str | None = None

    try:
        while True:
            ready = sel.select(timeout=timeout)
            if not ready:
                # Idle timeout — no data for `timeout` seconds
                proc.kill()
                proc.wait()
                timed_out = True
                break

            line = proc.stdout.readline()
            if not line:
                # EOF — process closed stdout
                break

            line = line.strip()
            if not line:
                continue

            total_bytes += len(line)
            if total_bytes > _MAX_RESPONSE_BYTES:
                proc.kill()
                proc.wait()
                oversized = True
                break

            delta, event = _parse_stream_event(line)

            if delta is not None:
                text_parts.append(delta)
                if on_delta is not None:
                    try:
                        on_delta(delta)
                    except Exception:
                        _log.debug("on_delta callback failed", exc_info=True)

            # Track the final result event
            if event is not None and event.get("type") == "result":
                result_event = event

            # Detect compaction events
            if (
                event is not None
                and event.get("type") == "stream_event"
                and event.get("event", {}).get("type") == "content_block_delta"
                and event["event"].get("delta", {}).get("type") == "compaction_delta"
            ):
                delta_obj = event["event"]["delta"]
                compaction_summary = delta_obj.get("summary", delta_obj.get("text", ""))
    finally:
        sel.unregister(proc.stdout)
        sel.close()

    # Prefer canonical result text over accumulated deltas
    if result_event is not None and "result" in result_event:
        final_text = result_event["result"]
    else:
        final_text = "".join(text_parts)

    return _StreamResult(
        final_text, result_event, timed_out, oversized, compaction_summary
    )


def _drain_stderr(proc: subprocess.Popen) -> list[str]:
    """Read all stderr lines from a process in the current thread.

    Stops accumulating after ``_MAX_STDERR_BYTES`` to prevent memory exhaustion.

    Args:
        proc: The subprocess whose stderr to drain.

    Returns:
        List of stderr lines.
    """
    lines: list[str] = []
    total_bytes = 0
    for line in proc.stderr:
        total_bytes += len(line)
        if total_bytes > _MAX_STDERR_BYTES:
            lines.append("[stderr truncated]\n")
            break
        lines.append(line)
    return lines


def invoke_agent(
    config: SessionConfig,
    agent: str,
    prompt: str,
    system_prompt: str | None = None,
    timeout: int = 600,
    session_id: str | None = None,
    readonly: bool = False,
    on_delta: Callable[[str], None] | None = None,
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
        readonly: When True, omit Write and Edit tools.
        on_delta: Optional callback invoked with each text delta chunk
            during streaming.

    Returns:
        AgentResponse with the agent's text response.
    """
    resolved_session_id = session_id or _get_session_id(config, agent)
    cwd = config.session_dir()

    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        # --verbose is required for stream-json to emit the final result event
        "--verbose",
        # --include-partial-messages emits content_block_delta stream events
        # as the model generates text, enabling real-time streaming display
        "--include-partial-messages",
    ]
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
    with _process_lock:
        _active_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            start_new_session=True,
        )
        proc = _active_process

    try:
        # Write prompt to stdin and close to signal EOF
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except OSError:
            # Process may have died before we finished writing (BrokenPipeError).
            # Suppress and fall through to collect whatever output it produced.
            with contextlib.suppress(OSError):
                proc.stdin.close()

        # Drain stderr in a daemon thread to prevent deadlock
        stderr_lines: list[str] = []
        stderr_thread = threading.Thread(
            target=lambda: stderr_lines.extend(_drain_stderr(proc)),
            daemon=True,
        )
        stderr_thread.start()

        # Stream stdout with idle timeout
        sr = _read_stream(proc, timeout, on_delta)

        # Wait for process to finish (with timeout to prevent hangs)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        stderr_thread.join(timeout=5)
        stderr_text = "".join(stderr_lines).strip()
    finally:
        with _process_lock:
            _active_process = None

    if sr.timed_out:
        return AgentResponse(
            text="[Agent timed out]",
            raw={"error": "timeout"},
            cmd=cmd,
            is_error=True,
            timed_out=True,
        )

    if sr.oversized:
        return AgentResponse(
            text="[Agent response exceeded size limit]",
            raw={"error": "response_too_large"},
            cmd=cmd,
            is_error=True,
        )

    if proc.returncode != 0:
        return AgentResponse(
            text=f"[Agent error: {stderr_text}]",
            raw={"error": stderr_text, "returncode": proc.returncode},
            cmd=cmd,
            is_error=True,
        )

    raw = sr.result_event if sr.result_event is not None else {"result": sr.text}
    usage = raw.get("usage") if isinstance(raw, dict) else None
    return AgentResponse(
        text=sr.text,
        raw=raw,
        cmd=cmd,
        compaction_summary=sr.compaction_summary,
        usage=usage,
    )
