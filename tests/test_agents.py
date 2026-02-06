"""Tests for agent CLI invocation."""

import io
import json
import logging
from unittest.mock import MagicMock, patch

from claude_storm.agents import (
    _MAX_RESPONSE_BYTES,
    _MAX_STDERR_BYTES,
    _build_allowed_tools,
    _drain_stderr,
    _parse_stream_event,
    _read_stream,
    _StreamResult,
    _validate_model,
    _validate_reference_dir,
    invoke_agent,
)

# ---------- Security tests ----------


class TestValidateReferenceDir:
    """Issue .3: Reference directory validation."""

    def test_rejects_root(self):
        assert _validate_reference_dir("/") is False

    def test_rejects_etc(self):
        assert _validate_reference_dir("/etc") is False

    def test_rejects_var(self):
        assert _validate_reference_dir("/var") is False

    def test_accepts_normal_path(self):
        assert _validate_reference_dir("/some/ref/dir") is True

    def test_accepts_home_subdir(self):
        assert _validate_reference_dir("/Users/mike/projects") is True


class TestValidateModel:
    """Issue .3: Model identifier validation."""

    def test_valid_model(self):
        assert _validate_model("sonnet") == "sonnet"
        assert _validate_model("opus") == "opus"
        assert _validate_model("claude-3.5-sonnet") == "claude-3.5-sonnet"

    def test_invalid_model_falls_back(self):
        assert _validate_model("'; rm -rf /") == "sonnet"
        assert _validate_model("model --flag") == "sonnet"
        assert _validate_model("") == "sonnet"


class TestSensitiveRefDirFiltered:
    """Issue .3: Sensitive reference dirs excluded from allowed tools."""

    def test_root_dir_filtered(self, make_config):
        config = make_config()
        config.reference_dirs = ["/"]
        tools = _build_allowed_tools(config)
        # Only session dir tools, root should be filtered out
        assert len(tools) == 5
        assert not any("Read(///**)" in t for t in tools)

    def test_etc_dir_filtered(self, make_config):
        config = make_config()
        config.reference_dirs = ["/etc"]
        tools = _build_allowed_tools(config)
        assert len(tools) == 5
        assert not any("Read(//etc/**)" in t for t in tools)


_SEL_PATCH = "claude_storm.agents.selectors.DefaultSelector"
_POPEN_PATCH = "claude_storm.agents.subprocess.Popen"

# ---------- Stream event parsing ----------


class TestParseStreamEvent:
    """Test _parse_stream_event NDJSON line parser."""

    def test_text_delta_extracted(self):
        line = json.dumps(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "hello"},
                },
            }
        )
        delta, event = _parse_stream_event(line)
        assert delta == "hello"
        assert event is not None

    def test_result_event(self):
        line = json.dumps(
            {"type": "result", "subtype": "success", "result": "full text"}
        )
        delta, event = _parse_stream_event(line)
        assert delta is None
        assert event["type"] == "result"
        assert event["result"] == "full text"

    def test_system_init_ignored(self):
        line = json.dumps({"type": "system", "subtype": "init"})
        delta, event = _parse_stream_event(line)
        assert delta is None
        assert event["type"] == "system"

    def test_message_start_ignored(self):
        line = json.dumps({"type": "stream_event", "event": {"type": "message_start"}})
        delta, event = _parse_stream_event(line)
        assert delta is None
        assert event is not None

    def test_invalid_json(self):
        delta, event = _parse_stream_event("not json")
        assert delta is None
        assert event is None

    def test_empty_line(self):
        delta, event = _parse_stream_event("")
        assert delta is None
        assert event is None


# ---------- Stream reader ----------


def _make_stream_lines(events):
    """Build NDJSON text from a list of event dicts."""
    return "\n".join(json.dumps(e) for e in events) + "\n"


def _mock_stream_popen(events, returncode=0, stderr=""):
    """Create a mock Popen yielding NDJSON events on stdout.

    Uses io.StringIO for stdout/stderr. Also mocks stdin.
    """
    stdout_text = _make_stream_lines(events)
    mock_proc = MagicMock()
    mock_proc.stdout = io.StringIO(stdout_text)
    mock_proc.stderr = io.StringIO(stderr)
    mock_proc.stdin = MagicMock()
    mock_proc.returncode = returncode
    mock_proc.wait.return_value = returncode
    mock_proc.kill = MagicMock()
    return mock_proc


class TestStreamReader:
    """Test _read_stream with mocked selector and StringIO."""

    def _run_read_stream(self, events, timeout=600, on_delta=None):
        """Helper to run _read_stream with mocked selectors."""
        proc = _mock_stream_popen(events)

        # Mock the selector since StringIO doesn't have a real fd
        mock_sel = MagicMock()

        # sel.select() should return a truthy list for each line,
        # then eventually readline() returns "" (EOF)
        mock_sel.select.return_value = [(None, None)]

        with patch(_SEL_PATCH, return_value=mock_sel):
            sr = _read_stream(proc, timeout, on_delta)

        return sr.text, sr.result_event, sr.timed_out, sr.oversized, proc

    def test_normal_streaming(self):
        """Multiple deltas followed by a result event."""
        events = [
            {"type": "system", "subtype": "init"},
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "hello"},
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": " world"},
                },
            },
            {"type": "result", "subtype": "success", "result": "hello world"},
        ]
        text, result_event, timed_out, oversized, _ = self._run_read_stream(events)
        assert text == "hello world"
        assert result_event is not None
        assert result_event["type"] == "result"
        assert not timed_out
        assert not oversized

    def test_on_delta_callback(self):
        """on_delta is called for each text delta."""
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
        self._run_read_stream(events, on_delta=deltas.append)
        assert deltas == ["chunk1", "chunk2"]

    def test_canonical_result_preferred(self):
        """Result event text is preferred over accumulated deltas."""
        events = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "partial"},
                },
            },
            {"type": "result", "subtype": "success", "result": "canonical text"},
        ]
        text, _, _, _, _ = self._run_read_stream(events)
        assert text == "canonical text"

    def test_idle_timeout(self):
        """Selector returning empty triggers idle timeout."""
        proc = _mock_stream_popen([])

        mock_sel = MagicMock()
        # Empty list = timeout
        mock_sel.select.return_value = []

        with patch(_SEL_PATCH, return_value=mock_sel):
            sr = _read_stream(proc, 10, None)

        assert sr.timed_out
        assert not sr.oversized
        proc.kill.assert_called_once()
        # proc.wait() must be called after kill to reap the zombie
        proc.wait.assert_called()

    def test_eof_mid_stream(self):
        """EOF without a result event uses accumulated text."""
        events = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "partial"},
                },
            },
            # No result event — EOF after this
        ]
        text, result_event, timed_out, _oversized, _ = self._run_read_stream(events)
        assert text == "partial"
        assert result_event is None
        assert not timed_out


# ---------- Response size limit ----------


class TestResponseSizeLimit:
    """Issue .8: Large responses are rejected."""

    def test_oversized_response_returns_error(self, make_config):
        config = make_config()
        # Create events that exceed the byte limit
        big_text = "x" * (_MAX_RESPONSE_BYTES + 1)
        events = [
            {"type": "result", "subtype": "success", "result": big_text},
        ]
        mock_proc = _mock_stream_popen(events)

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH) as mock_sel_cls,
        ):
            mock_sel = MagicMock()
            mock_sel.select.return_value = [(None, None)]
            mock_sel_cls.return_value = mock_sel
            response = invoke_agent(config, "a", "prompt")

        assert response.is_error
        assert "size limit" in response.text

    def test_normal_response_passes(self, make_config):
        config = make_config()
        events = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "normal"},
                },
            },
            {"type": "result", "subtype": "success", "result": "normal response"},
        ]
        mock_proc = _mock_stream_popen(events)

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH) as mock_sel_cls,
        ):
            mock_sel = MagicMock()
            mock_sel.select.return_value = [(None, None)]
            mock_sel_cls.return_value = mock_sel
            response = invoke_agent(config, "a", "prompt")

        assert not response.is_error
        assert response.text == "normal response"


# ---------- invoke_agent ----------


class TestInvokeAgent:
    def _invoke_with_events(self, config, events, agent="a", **kwargs):
        """Helper to invoke_agent with mocked streaming subprocess."""
        mock_proc = _mock_stream_popen(events)

        with (
            patch(_POPEN_PATCH, return_value=mock_proc) as mock_popen_cls,
            patch(_SEL_PATCH) as mock_sel_cls,
        ):
            mock_sel = MagicMock()
            mock_sel.select.return_value = [(None, None)]
            mock_sel_cls.return_value = mock_sel
            response = invoke_agent(config, agent, **kwargs)

        return response, mock_popen_cls

    def test_first_turn_uses_session_id(self, make_config):
        config = make_config()
        events = [
            {"type": "result", "subtype": "success", "result": "Hello from agent A"},
        ]
        response, mock_popen_cls = self._invoke_with_events(
            config,
            events,
            prompt="Start the brainstorm",
            system_prompt="You are an architect",
        )

        cmd = mock_popen_cls.call_args[0][0]
        assert "--session-id" in cmd
        assert "sess-a-uuid" in cmd
        assert "--system-prompt" in cmd
        assert "--model" in cmd
        assert "--allowedTools" in cmd
        assert "--output-format" in cmd
        idx = cmd.index("--output-format")
        assert cmd[idx + 1] == "stream-json"
        assert "--verbose" in cmd
        assert response.text == "Hello from agent A"
        assert response.cmd is not None
        assert "claude" in response.cmd

    def test_first_turn_has_path_scoped_tools(self, make_config):
        config = make_config()
        events = [{"type": "result", "subtype": "success", "result": "ok"}]
        _, mock_popen_cls = self._invoke_with_events(
            config, events, prompt="prompt", system_prompt="sys"
        )

        cmd = mock_popen_cls.call_args[0][0]
        session_path = str(config.session_dir().resolve()).lstrip("/")
        # Write/Edit scoped to session dir only
        assert f"Write(//{session_path}/**)" in cmd
        assert f"Edit(//{session_path}/**)" in cmd
        # Read/Glob/Grep scoped to session dir
        assert f"Read(//{session_path}/**)" in cmd
        assert f"Glob(//{session_path}/**)" in cmd
        assert f"Grep(//{session_path}/**)" in cmd
        # No bare tool names
        for arg in cmd:
            if arg in ("Read", "Write", "Edit", "Glob", "Grep"):
                raise AssertionError(f"Found unscoped tool: {arg}")

    def test_subsequent_turn_uses_resume(self, make_config):
        config = make_config()
        events = [{"type": "result", "subtype": "success", "result": "Continuing..."}]
        response, mock_popen_cls = self._invoke_with_events(
            config, events, agent="b", prompt="Your turn"
        )

        cmd = mock_popen_cls.call_args[0][0]
        assert "--resume" in cmd
        assert "sess-b-uuid" in cmd
        assert "--session-id" not in cmd
        assert "--allowedTools" in cmd
        assert response.text == "Continuing..."

    def test_resume_includes_reference_dir_tools(self, make_config):
        config = make_config()
        config.reference_dirs = ["/some/ref/dir"]
        events = [{"type": "result", "subtype": "success", "result": "ok"}]
        _, mock_popen_cls = self._invoke_with_events(config, events, prompt="Continue")

        cmd = mock_popen_cls.call_args[0][0]
        assert "--resume" in cmd
        assert "Read(//some/ref/dir/**)" in cmd
        assert "Glob(//some/ref/dir/**)" in cmd
        assert "Grep(//some/ref/dir/**)" in cmd

    def test_timeout_returns_error(self, make_config):
        config = make_config()

        # Create a proc that triggers idle timeout
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = io.StringIO("")
        mock_proc.stderr = io.StringIO("")
        mock_proc.returncode = -9
        mock_proc.wait.return_value = -9

        mock_sel = MagicMock()
        mock_sel.select.return_value = []  # Idle timeout

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = invoke_agent(config, "a", "prompt", timeout=300)

        assert response.is_error
        assert response.timed_out
        assert "timed out" in response.text

    def test_nonzero_exit_returns_error(self, make_config):
        config = make_config()
        mock_proc = _mock_stream_popen([], returncode=1, stderr="Some error")

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = invoke_agent(config, "a", "prompt")

        assert response.is_error
        assert "Some error" in response.text

    def test_cmd_populated_on_error(self, make_config):
        config = make_config()
        mock_proc = _mock_stream_popen([], returncode=1, stderr="fail")

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = invoke_agent(config, "a", "prompt")

        assert response.cmd is not None
        assert "claude" in response.cmd

    def test_on_delta_callback_wired(self, make_config):
        """on_delta callback is invoked during invoke_agent."""
        config = make_config()
        events = [
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
        deltas = []
        mock_proc = _mock_stream_popen(events)

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = invoke_agent(config, "a", "prompt", on_delta=deltas.append)

        assert deltas == ["streamed"]
        assert response.text == "streamed"


class TestBuildAllowedTools:
    def test_session_dir_only(self, make_config):
        config = make_config()
        tools = _build_allowed_tools(config)
        session_path = str(config.session_dir().resolve()).lstrip("/")
        assert f"Read(//{session_path}/**)" in tools
        assert f"Glob(//{session_path}/**)" in tools
        assert f"Grep(//{session_path}/**)" in tools
        assert f"Write(//{session_path}/**)" in tools
        assert f"Edit(//{session_path}/**)" in tools
        # Only 5 tool entries when no reference dir
        assert len(tools) == 5

    def test_with_reference_dir(self, make_config):
        config = make_config()
        config.reference_dirs = ["/some/ref/dir"]
        tools = _build_allowed_tools(config)
        # Read tools for both dirs
        assert "Read(//some/ref/dir/**)" in tools
        assert "Glob(//some/ref/dir/**)" in tools
        assert "Grep(//some/ref/dir/**)" in tools
        # Write/Edit only for session dir
        assert not any("Write" in t and "some/ref" in t for t in tools)
        assert not any("Edit" in t and "some/ref" in t for t in tools)
        # 8 total: 3 read tools * 2 dirs + 2 write tools * 1 dir
        assert len(tools) == 8

    def test_with_multiple_reference_dirs(self, make_config):
        config = make_config()
        config.reference_dirs = ["/ref/one", "/ref/two"]
        tools = _build_allowed_tools(config)
        # Read tools for all 3 dirs (session + 2 ref)
        assert "Read(//ref/one/**)" in tools
        assert "Read(//ref/two/**)" in tools
        assert "Glob(//ref/one/**)" in tools
        assert "Glob(//ref/two/**)" in tools
        # Write/Edit only for session dir
        assert not any("Write" in t and "ref/one" in t for t in tools)
        assert not any("Write" in t and "ref/two" in t for t in tools)
        # 11 total: 3 read tools * 3 dirs + 2 write tools * 1 dir
        assert len(tools) == 11

    def test_readonly_excludes_write_edit(self, make_config):
        config = make_config()
        tools = _build_allowed_tools(config, readonly=True)
        assert not any("Write" in t for t in tools)
        assert not any("Edit" in t for t in tools)
        # Read/Glob/Grep should still be present
        assert any("Read" in t for t in tools)
        assert any("Glob" in t for t in tools)
        assert any("Grep" in t for t in tools)
        # Only 3 tool entries (read-only for session dir)
        assert len(tools) == 3

    def test_readonly_with_reference_dir(self, make_config):
        config = make_config()
        config.reference_dirs = ["/some/ref/dir"]
        tools = _build_allowed_tools(config, readonly=True)
        assert not any("Write" in t for t in tools)
        assert not any("Edit" in t for t in tools)
        # 6 total: 3 read tools * 2 dirs
        assert len(tools) == 6


class TestStreamResult:
    """_StreamResult NamedTuple behaves as expected."""

    def test_named_access(self):
        sr = _StreamResult("hello", None, False, False)
        assert sr.text == "hello"
        assert sr.result_event is None
        assert not sr.timed_out
        assert not sr.oversized

    def test_tuple_unpacking(self):
        """NamedTuple is backward-compatible with tuple unpacking."""
        sr = _StreamResult("hello", {"type": "result"}, True, False)
        text, result_event, timed_out, oversized = sr
        assert text == "hello"
        assert result_event == {"type": "result"}
        assert timed_out
        assert not oversized


class TestBrokenPipeError:
    """BrokenPipeError on stdin.write produces an error response."""

    def test_broken_pipe_returns_error(self, make_config):
        config = make_config()
        mock_proc = _mock_stream_popen([], returncode=1, stderr="broken pipe")
        mock_proc.stdin.write.side_effect = BrokenPipeError("pipe broken")

        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        with (
            patch(_POPEN_PATCH, return_value=mock_proc),
            patch(_SEL_PATCH, return_value=mock_sel),
        ):
            response = invoke_agent(config, "a", "prompt")

        assert response.is_error


class TestUnparseableLine:
    """Unparseable NDJSON lines are logged at debug level."""

    def test_logged_at_debug(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="claude_storm.agents"):
            delta, event = _parse_stream_event("not valid json {{{")
        assert delta is None
        assert event is None
        assert "Unparseable stream line" in caplog.text

    def test_failing_callback_preserves_text(self):
        """A failing on_delta callback does not lose accumulated text."""
        events = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "kept"},
                },
            },
            {"type": "result", "subtype": "success", "result": "kept"},
        ]
        proc = _mock_stream_popen(events)
        mock_sel = MagicMock()
        mock_sel.select.return_value = [(None, None)]

        def bad_callback(text):
            raise RuntimeError("boom")

        with patch(_SEL_PATCH, return_value=mock_sel):
            sr = _read_stream(proc, 600, bad_callback)

        # Text should still be accumulated despite callback failure
        assert sr.text == "kept"


class TestStderrCap:
    """Stderr accumulation is capped at _MAX_STDERR_BYTES."""

    def test_large_stderr_truncated(self):
        big_line = "x" * (_MAX_STDERR_BYTES + 100) + "\n"
        mock_proc = MagicMock()
        mock_proc.stderr = io.StringIO(big_line)

        lines = _drain_stderr(mock_proc)
        joined = "".join(lines)
        assert "[stderr truncated]" in joined
