"""Tests for AgentBackend protocol and implementations."""

import io
import json
from unittest.mock import MagicMock, patch

from claude_storm.agents import (
    AgentBackend,
    LongRunningBackend,
    SubprocessBackend,
    _read_until_result,
    create_backend,
)

_SEL_PATCH = "claude_storm.agents.selectors.DefaultSelector"
_POPEN_PATCH = "claude_storm.agents.subprocess.Popen"


def _make_ndjson(*events):
    """Build NDJSON text from event dicts."""
    return "\n".join(json.dumps(e) for e in events) + "\n"


def _mock_long_running_proc(events, returncode=None):
    """Create a mock Popen that yields NDJSON events and stays alive.

    Unlike the one-shot mock, poll() returns None (process alive) unless
    returncode is set.
    """
    stdout_text = _make_ndjson(*events)
    mock_proc = MagicMock()
    mock_proc.stdout = io.StringIO(stdout_text)
    mock_proc.stderr = io.StringIO("")
    mock_proc.stdin = MagicMock()
    mock_proc.returncode = returncode
    mock_proc.poll.return_value = returncode
    mock_proc.wait.return_value = 0
    mock_proc.kill = MagicMock()
    mock_proc.terminate = MagicMock()
    return mock_proc


# ---------- Protocol conformance ----------


class TestProtocolConformance:
    """Both backends satisfy the AgentBackend protocol."""

    def test_subprocess_is_backend(self):
        assert isinstance(SubprocessBackend(), AgentBackend)

    def test_long_running_is_backend(self):
        assert isinstance(LongRunningBackend(), AgentBackend)


# ---------- create_backend factory ----------


class TestCreateBackend:
    def test_default_is_subprocess(self):
        backend = create_backend()
        assert isinstance(backend, SubprocessBackend)

    def test_subprocess_mode(self):
        assert isinstance(create_backend("subprocess"), SubprocessBackend)

    def test_long_running_mode(self):
        assert isinstance(create_backend("long-running"), LongRunningBackend)

    def test_unknown_falls_back_to_subprocess(self):
        assert isinstance(create_backend("bogus"), SubprocessBackend)


# ---------- SubprocessBackend ----------


class TestSubprocessBackend:
    def test_invoke_delegates_to_invoke_agent(self, make_config):
        """SubprocessBackend.invoke calls through to invoke_agent."""
        config = make_config()
        backend = SubprocessBackend()

        events = [
            {"type": "result", "subtype": "success", "result": "hello from subprocess"},
        ]
        stdout_text = _make_ndjson(*events)
        mock_proc = MagicMock()
        mock_proc.stdout = io.StringIO(stdout_text)
        mock_proc.stderr = io.StringIO("")
        mock_proc.stdin = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = backend.invoke(
                config=config,
                agent="a",
                prompt="test prompt",
                system_prompt="You are a test",
            )

        assert response.text == "hello from subprocess"
        assert not response.is_error

    def test_cancel_calls_cancel_active(self):
        backend = SubprocessBackend()
        with patch("claude_storm.agents.cancel_active") as mock_cancel:
            backend.cancel()
            mock_cancel.assert_called_once()

    def test_shutdown_calls_cancel_active(self):
        backend = SubprocessBackend()
        with patch("claude_storm.agents.cancel_active") as mock_cancel:
            backend.shutdown()
            mock_cancel.assert_called_once()


# ---------- _read_until_result ----------


class TestReadUntilResult:
    """Test the result-boundary reader used by LongRunningBackend."""

    def _run(self, events, timeout=600, on_delta=None):
        """Run _read_until_result with mocked selectors."""
        proc = _mock_long_running_proc(events)
        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        with patch(_SEL_PATCH, return_value=mock_sel):
            sr = _read_until_result(proc, timeout, on_delta)
        return sr, proc

    def test_stops_at_result_event(self):
        """Reader stops at the result event, not at EOF."""
        events = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "hello"},
                },
            },
            {"type": "result", "subtype": "success", "result": "hello world"},
        ]
        sr, proc = self._run(events)
        assert sr.text == "hello world"
        assert sr.result_event is not None
        assert not sr.timed_out
        # Process should NOT be killed (it stays alive)
        proc.kill.assert_not_called()

    def test_on_delta_called(self):
        events = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "chunk1"},
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "chunk2"},
                },
            },
            {"type": "result", "subtype": "success", "result": "chunk1chunk2"},
        ]
        deltas = []
        self._run(events, on_delta=deltas.append)
        assert deltas == ["chunk1", "chunk2"]

    def test_idle_timeout(self):
        """Empty selector means idle timeout."""
        proc = _mock_long_running_proc([])
        mock_sel = MagicMock()
        mock_sel.select.return_value = []

        with patch(_SEL_PATCH, return_value=mock_sel):
            sr = _read_until_result(proc, 10, None)

        assert sr.timed_out
        assert sr.result_event is None

    def test_eof_without_result(self):
        """EOF (process died) without a result event."""
        events = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "partial"},
                },
            },
        ]
        sr, _ = self._run(events)
        assert sr.text == "partial"
        assert sr.result_event is None
        assert not sr.timed_out


# ---------- LongRunningBackend ----------


class TestLongRunningBackend:
    def _make_backend_with_proc(self, config, agent, events):
        """Create a LongRunningBackend with a pre-started mock process.

        Returns (backend, mock_proc).
        """
        backend = LongRunningBackend()

        init_events = [{"type": "system", "subtype": "init", "session_id": "test-uuid"}]
        init_text = _make_ndjson(*init_events)
        turn_text = _make_ndjson(*events)
        combined_text = init_text + turn_text

        mock_proc = MagicMock()
        mock_proc.stdout = io.StringIO(combined_text)
        mock_proc.stderr = io.StringIO("")
        mock_proc.stdin = MagicMock()
        mock_proc.returncode = None
        mock_proc.poll.return_value = None
        mock_proc.wait.return_value = 0
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = backend.invoke(
                config=config,
                agent=agent,
                prompt="First prompt",
                system_prompt="You are a test agent",
            )

        return backend, mock_proc, response

    def test_first_turn_starts_process(self, make_config):
        """First invoke starts a new process with --session-id."""
        config = make_config()
        events = [
            {"type": "result", "subtype": "success", "result": "first response"},
        ]
        backend, mock_proc, response = self._make_backend_with_proc(config, "a", events)

        assert response.text == "first response"
        assert not response.is_error
        # Process should still be alive (not killed)
        mock_proc.kill.assert_not_called()
        backend.shutdown()

    def test_first_turn_cmd_has_input_format(self, make_config):
        """First invoke uses --input-format stream-json."""
        config = make_config()
        events = [
            {"type": "result", "subtype": "success", "result": "ok"},
        ]

        mock_proc = _mock_long_running_proc(
            [{"type": "system", "subtype": "init", "session_id": "test-uuid"}, *events]
        )

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        backend = LongRunningBackend()
        with (
            patch(_POPEN_PATCH, return_value=mock_proc) as mock_popen_cls,
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            backend.invoke(
                config=config,
                agent="a",
                prompt="Hello",
                system_prompt="System",
            )

        cmd = mock_popen_cls.call_args[0][0]
        assert "--input-format" in cmd
        assert "stream-json" in cmd
        assert "--session-id" in cmd
        assert "--system-prompt" in cmd
        # Should NOT have --resume on first turn
        assert "--resume" not in cmd
        backend.shutdown()

    def test_sends_ndjson_message_on_stdin(self, make_config):
        """Prompt is sent as NDJSON user message, not raw text."""
        config = make_config()
        events = [
            {"type": "result", "subtype": "success", "result": "ok"},
        ]
        backend, mock_proc, _ = self._make_backend_with_proc(config, "a", events)

        # Check what was written to stdin
        write_calls = mock_proc.stdin.write.call_args_list
        assert len(write_calls) >= 1
        written = write_calls[0][0][0]
        msg = json.loads(written.strip())
        assert msg["type"] == "user"
        assert msg["message"]["role"] == "user"
        assert msg["message"]["content"] == "First prompt"
        backend.shutdown()

    def test_subsequent_turn_reuses_process(self, make_config):
        """Second invoke reuses the existing process (no new Popen)."""
        config = make_config()

        # Build combined stdout: init + turn1 result + turn2 result
        all_events = [
            {"type": "system", "subtype": "init", "session_id": "test-uuid"},
            {"type": "result", "subtype": "success", "result": "turn 1"},
            {"type": "result", "subtype": "success", "result": "turn 2"},
        ]
        mock_proc = _mock_long_running_proc(all_events)

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        backend = LongRunningBackend()
        with (
            patch(_POPEN_PATCH, return_value=mock_proc) as mock_popen_cls,
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            # Turn 1 (starts process)
            r1 = backend.invoke(
                config=config, agent="a", prompt="Turn 1", system_prompt="Sys"
            )
            # Turn 2 (reuses process)
            r2 = backend.invoke(config=config, agent="a", prompt="Turn 2")

        assert r1.text == "turn 1"
        assert r2.text == "turn 2"
        # Popen should have been called exactly once
        assert mock_popen_cls.call_count == 1
        backend.shutdown()

    def test_oneshot_session_id_uses_subprocess(self, make_config):
        """Explicit session_id falls back to invoke_agent (subprocess)."""
        config = make_config()
        backend = LongRunningBackend()

        events = [
            {"type": "result", "subtype": "success", "result": "one-shot"},
        ]
        mock_proc = MagicMock()
        mock_proc.stdout = io.StringIO(_make_ndjson(*events))
        mock_proc.stderr = io.StringIO("")
        mock_proc.stdin = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = backend.invoke(
                config=config,
                agent="a",
                prompt="Compile deliverable",
                session_id="one-shot-uuid",
            )

        assert response.text == "one-shot"
        # No persistent process should have been stored
        assert "a" not in backend._agents
        backend.shutdown()

    def test_timeout_kills_process(self, make_config):
        """Idle timeout on a long-running process returns error and cleans up."""
        config = make_config()

        # Start with init event, then nothing (will timeout)
        init_events = [{"type": "system", "subtype": "init", "session_id": "t"}]
        mock_proc = _mock_long_running_proc(init_events)

        mock_sel = MagicMock()
        call_count = [0]

        def select_side_effect(timeout=None):
            call_count[0] += 1
            if call_count[0] <= 1:
                # First call returns ready (for init event)
                return [(None, None)]
            # Subsequent calls: timeout on init reading done, now
            # we re-register for the turn reading and timeout there
            return []

        mock_sel.select.side_effect = select_side_effect

        backend = LongRunningBackend()
        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = backend.invoke(
                config=config,
                agent="a",
                prompt="This will timeout",
                system_prompt="Sys",
                timeout=1,
            )

        assert response.is_error
        assert response.timed_out
        assert "timed out" in response.text
        backend.shutdown()

    def test_process_death_returns_error(self, make_config):
        """Process dying mid-turn returns an error."""
        config = make_config()

        # Init event only, then EOF (process dies)
        init_events = [{"type": "system", "subtype": "init", "session_id": "t"}]
        mock_proc = _mock_long_running_proc(init_events)
        # After init, poll returns non-None (process died)
        mock_proc.poll.side_effect = [None, 1]
        mock_proc.returncode = 1

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        backend = LongRunningBackend()
        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = backend.invoke(
                config=config,
                agent="a",
                prompt="Prompt",
                system_prompt="Sys",
            )

        # Should get an error about process death
        assert response.is_error
        backend.shutdown()

    def test_shutdown_terminates_all(self, make_config):
        """shutdown() terminates all agent processes."""
        config = make_config()
        events = [
            {"type": "result", "subtype": "success", "result": "ok"},
        ]
        backend, mock_proc, _ = self._make_backend_with_proc(config, "a", events)

        backend.shutdown()
        mock_proc.terminate.assert_called()

    def test_cancel_terminates_running(self, make_config):
        """cancel() sends SIGTERM to running processes."""
        config = make_config()
        events = [
            {"type": "result", "subtype": "success", "result": "ok"},
        ]
        backend, mock_proc, _ = self._make_backend_with_proc(config, "a", events)

        backend.cancel()
        mock_proc.terminate.assert_called()
        backend.shutdown()

    def test_resume_uses_resume_flag(self, make_config):
        """When no system_prompt, process starts with --resume."""
        config = make_config()

        all_events = [
            {"type": "system", "subtype": "init", "session_id": "test-uuid"},
            {"type": "result", "subtype": "success", "result": "resumed"},
        ]
        mock_proc = _mock_long_running_proc(all_events)

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        backend = LongRunningBackend()
        with (
            patch(_POPEN_PATCH, return_value=mock_proc) as mock_popen_cls,
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = backend.invoke(
                config=config,
                agent="a",
                prompt="Continue",
                system_prompt=None,  # resuming, no system prompt
            )

        cmd = mock_popen_cls.call_args[0][0]
        assert "--resume" in cmd
        assert "--session-id" not in cmd
        assert "--system-prompt" not in cmd
        assert response.text == "resumed"
        backend.shutdown()

    def test_on_delta_wired_through(self, make_config):
        """on_delta callback receives streaming chunks."""
        config = make_config()

        all_events = [
            {"type": "system", "subtype": "init", "session_id": "test-uuid"},
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "streamed"},
                },
            },
            {"type": "result", "subtype": "success", "result": "streamed"},
        ]
        mock_proc = _mock_long_running_proc(all_events)

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        deltas = []
        backend = LongRunningBackend()
        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = backend.invoke(
                config=config,
                agent="a",
                prompt="Stream test",
                system_prompt="Sys",
                on_delta=deltas.append,
            )

        assert "streamed" in deltas
        assert response.text == "streamed"
        backend.shutdown()
