"""Claude CLI subprocess wrapper with session management."""

from __future__ import annotations

import contextlib
import json
import logging
import re
import selectors
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import NamedTuple, Protocol, runtime_checkable

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
    finally:
        sel.unregister(proc.stdout)
        sel.close()

    # Prefer canonical result text over accumulated deltas
    if result_event is not None and "result" in result_event:
        final_text = result_event["result"]
    else:
        final_text = "".join(text_parts)

    return _StreamResult(final_text, result_event, timed_out, oversized)


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
    return AgentResponse(text=sr.text, raw=raw, cmd=cmd)


# ---------------------------------------------------------------------------
# Agent backend protocol and implementations
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentBackend(Protocol):
    """Interface for agent invocation backends.

    Two implementations exist:
    - ``SubprocessBackend``: spawns a new process per turn (original behaviour).
    - ``LongRunningBackend``: keeps a persistent ``stream-json`` process per
      agent, avoiding per-turn startup overhead.
    """

    def invoke(
        self,
        config: SessionConfig,
        agent: str,
        prompt: str,
        system_prompt: str | None = None,
        timeout: int = 600,
        session_id: str | None = None,
        readonly: bool = False,
        on_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        """Send a prompt to an agent and return the response."""
        ...

    def cancel(self) -> None:
        """Cancel the currently active agent invocation."""
        ...

    def shutdown(self) -> None:
        """Release all resources held by this backend."""
        ...


class SubprocessBackend:
    """Agent backend that spawns a new ``claude -p`` process per turn.

    This is the original behaviour and delegates entirely to
    :func:`invoke_agent`.
    """

    def invoke(
        self,
        config: SessionConfig,
        agent: str,
        prompt: str,
        system_prompt: str | None = None,
        timeout: int = 600,
        session_id: str | None = None,
        readonly: bool = False,
        on_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        """Invoke via per-turn subprocess."""
        return invoke_agent(
            config=config,
            agent=agent,
            prompt=prompt,
            system_prompt=system_prompt,
            timeout=timeout,
            session_id=session_id,
            readonly=readonly,
            on_delta=on_delta,
        )

    def cancel(self) -> None:
        """Terminate the active subprocess."""
        cancel_active()

    def shutdown(self) -> None:
        """No persistent resources to release."""
        cancel_active()


def _read_until_result(
    proc: subprocess.Popen,
    timeout: int,
    on_delta: Callable[[str], None] | None,
) -> _StreamResult:
    """Read NDJSON lines until a ``result`` event or idle timeout.

    Unlike :func:`_read_stream`, this does **not** read until EOF because the
    process is expected to stay alive after emitting the result.  The selector
    is created and torn down per call so the same stdout can be re-read on
    subsequent turns.

    Args:
        proc: The long-running subprocess.
        timeout: Idle timeout in seconds.
        on_delta: Optional callback for streaming text deltas.

    Returns:
        _StreamResult with accumulated text and the result event.
    """
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)

    text_parts: list[str] = []
    total_bytes = 0
    result_event: dict | None = None
    timed_out = False
    oversized = False

    try:
        while True:
            ready = sel.select(timeout=timeout)
            if not ready:
                timed_out = True
                break

            line = proc.stdout.readline()
            if not line:
                # EOF — process died unexpectedly
                break

            line = line.strip()
            if not line:
                continue

            total_bytes += len(line)
            if total_bytes > _MAX_RESPONSE_BYTES:
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

            if event is not None and event.get("type") == "result":
                result_event = event
                break
    finally:
        sel.unregister(proc.stdout)
        sel.close()

    if result_event is not None and "result" in result_event:
        final_text = result_event["result"]
    else:
        final_text = "".join(text_parts)

    return _StreamResult(final_text, result_event, timed_out, oversized)


@dataclass
class _AgentProcess:
    """Bookkeeping for a single persistent agent process."""

    proc: subprocess.Popen
    cmd: list[str]
    session_id: str
    stderr_thread: threading.Thread
    stderr_lines: list[str] = field(default_factory=list)


class LongRunningBackend:
    """Agent backend using persistent ``--input-format stream-json`` processes.

    Each agent gets a single long-lived ``claude`` process.  Prompts are sent
    as NDJSON messages on stdin; responses are read from stdout until a
    ``result`` event.  The process stays alive between turns, eliminating
    per-turn startup overhead.

    One-shot calls (where ``session_id`` is provided explicitly, e.g. for
    compilation) fall through to the regular per-turn subprocess path.
    """

    def __init__(self) -> None:
        self._agents: dict[str, _AgentProcess] = {}
        self._lock = threading.Lock()

    def _start_process(
        self,
        config: SessionConfig,
        agent: str,
        system_prompt: str | None,
        readonly: bool,
    ) -> _AgentProcess:
        """Spawn a persistent claude process for an agent.

        Args:
            config: Session configuration.
            agent: Agent identifier ('a' or 'b').
            system_prompt: System prompt for new sessions (None to resume).
            readonly: Whether to omit write tools.

        Returns:
            An _AgentProcess with the running subprocess.
        """
        resolved_session_id = _get_session_id(config, agent)
        cwd = config.session_dir()

        cmd = [
            "claude",
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        validated_model = _validate_model(config.model)

        if system_prompt is not None:
            cmd.extend(["--session-id", resolved_session_id])
            cmd.extend(["--system-prompt", system_prompt])
            cmd.extend(["--model", validated_model])
        else:
            # Resuming an existing session
            cmd.extend(["--resume", resolved_session_id])

        cmd.extend(["--allowedTools", *_build_allowed_tools(config, readonly=readonly)])

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
        )

        # Drain stderr continuously in a background thread
        stderr_lines: list[str] = []
        stderr_thread = threading.Thread(
            target=lambda: stderr_lines.extend(_drain_stderr(proc)),
            daemon=True,
        )
        stderr_thread.start()

        ap = _AgentProcess(
            proc=proc,
            cmd=cmd,
            session_id=resolved_session_id,
            stderr_thread=stderr_thread,
            stderr_lines=stderr_lines,
        )
        self._agents[agent] = ap

        # Read and discard the system/init event so it doesn't
        # interfere with the first turn's result reading.
        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ)
        try:
            ready = sel.select(timeout=30)
            if ready:
                line = proc.stdout.readline().strip()
                if line:
                    _, event = _parse_stream_event(line)
                    if event and event.get("type") == "system":
                        _log.debug("Long-running init: %s", event)
        finally:
            sel.unregister(proc.stdout)
            sel.close()

        return ap

    def _get_or_start(
        self,
        config: SessionConfig,
        agent: str,
        system_prompt: str | None,
        readonly: bool,
    ) -> _AgentProcess:
        """Return the existing agent process or start a new one."""
        with self._lock:
            ap = self._agents.get(agent)
            if ap is not None and ap.proc.poll() is None:
                return ap
            return self._start_process(config, agent, system_prompt, readonly)

    def invoke(
        self,
        config: SessionConfig,
        agent: str,
        prompt: str,
        system_prompt: str | None = None,
        timeout: int = 600,
        session_id: str | None = None,
        readonly: bool = False,
        on_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        """Send a prompt to a persistent agent process.

        Args:
            config: Session configuration.
            agent: Agent identifier ('a' or 'b').
            prompt: The user prompt text.
            system_prompt: System prompt (only used when starting a new process).
            timeout: Idle timeout in seconds.
            session_id: If provided, falls back to one-shot subprocess.
            readonly: Whether to omit write tools.
            on_delta: Streaming text callback.

        Returns:
            AgentResponse with the agent's text.
        """
        # One-shot calls (compilation, summary) use the subprocess path
        if session_id is not None:
            return invoke_agent(
                config=config,
                agent=agent,
                prompt=prompt,
                system_prompt=system_prompt,
                timeout=timeout,
                session_id=session_id,
                readonly=readonly,
                on_delta=on_delta,
            )

        ap = self._get_or_start(config, agent, system_prompt, readonly)

        # Check that process is still alive
        if ap.proc.poll() is not None:
            stderr_text = "".join(ap.stderr_lines).strip()
            return AgentResponse(
                text=f"[Agent process died: {stderr_text}]",
                raw={"error": "process_died", "returncode": ap.proc.returncode},
                cmd=ap.cmd,
                is_error=True,
            )

        # Send user message as NDJSON
        msg = {
            "type": "user",
            "message": {
                "role": "user",
                "content": prompt,
            },
            "session_id": ap.session_id,
            "parent_tool_use_id": None,
        }
        try:
            ap.proc.stdin.write(json.dumps(msg) + "\n")
            ap.proc.stdin.flush()
        except OSError:
            stderr_text = "".join(ap.stderr_lines).strip()
            return AgentResponse(
                text=f"[Agent write error: {stderr_text}]",
                raw={"error": "stdin_write_failed"},
                cmd=ap.cmd,
                is_error=True,
            )

        # Read until result event (process stays alive)
        sr = _read_until_result(ap.proc, timeout, on_delta)

        if sr.timed_out:
            # Kill the timed-out process so it doesn't linger
            self._kill_agent(agent)
            return AgentResponse(
                text="[Agent timed out]",
                raw={"error": "timeout"},
                cmd=ap.cmd,
                is_error=True,
                timed_out=True,
            )

        if sr.oversized:
            self._kill_agent(agent)
            return AgentResponse(
                text="[Agent response exceeded size limit]",
                raw={"error": "response_too_large"},
                cmd=ap.cmd,
                is_error=True,
            )

        # Process died during read (EOF without result)
        if sr.result_event is None and ap.proc.poll() is not None:
            stderr_text = "".join(ap.stderr_lines).strip()
            return AgentResponse(
                text=f"[Agent error: {stderr_text}]",
                raw={"error": stderr_text, "returncode": ap.proc.returncode},
                cmd=ap.cmd,
                is_error=True,
            )

        raw = sr.result_event if sr.result_event is not None else {"result": sr.text}
        return AgentResponse(text=sr.text, raw=raw, cmd=ap.cmd)

    def _kill_agent(self, agent: str) -> None:
        """Terminate and clean up a single agent process."""
        ap = self._agents.pop(agent, None)
        if ap is None:
            return
        with contextlib.suppress(OSError):
            ap.proc.terminate()
        try:
            ap.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            ap.proc.kill()
            ap.proc.wait(timeout=5)
        ap.stderr_thread.join(timeout=5)

    def cancel(self) -> None:
        """Terminate all running agent processes."""
        with self._lock:
            for agent in list(self._agents):
                ap = self._agents.get(agent)
                if ap and ap.proc.poll() is None:
                    ap.proc.terminate()

    def shutdown(self) -> None:
        """Terminate all agent processes and release resources."""
        with self._lock:
            for agent in list(self._agents):
                self._kill_agent(agent)


def create_backend(mode: str = "subprocess") -> AgentBackend:
    """Create an agent backend by name.

    Args:
        mode: ``"subprocess"`` for per-turn spawning or
              ``"long-running"`` for persistent processes.

    Returns:
        An AgentBackend instance.
    """
    if mode == "long-running":
        return LongRunningBackend()
    return SubprocessBackend()
