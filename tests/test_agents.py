"""Tests for agent CLI invocation."""

import json
import subprocess as _subprocess
from unittest.mock import MagicMock, patch

from claude_storm.agents import _build_allowed_tools, _extract_text, invoke_agent


def _mock_popen(stdout="", stderr="", returncode=0):
    """Create a mock Popen that returns given stdout/stderr."""
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (stdout, stderr)
    mock_proc.returncode = returncode
    return mock_proc


class TestInvokeAgent:
    def test_first_turn_uses_session_id(self, make_config):
        config = make_config()
        mock_proc = _mock_popen(
            stdout=json.dumps({"result": "Hello from agent A"}),
        )

        with patch(
            "claude_storm.agents.subprocess.Popen", return_value=mock_proc
        ) as mock_popen_cls:
            response = invoke_agent(
                config,
                "a",
                "Start the brainstorm",
                system_prompt="You are an architect",
            )

        cmd = mock_popen_cls.call_args[0][0]
        assert "--session-id" in cmd
        assert "sess-a-uuid" in cmd
        assert "--system-prompt" in cmd
        assert "--model" in cmd
        assert "--allowedTools" in cmd
        assert response.text == "Hello from agent A"
        assert response.cmd is not None
        assert "claude" in response.cmd

    def test_first_turn_has_path_scoped_tools(self, make_config):
        config = make_config()
        mock_proc = _mock_popen(
            stdout=json.dumps({"result": "ok"}),
        )

        with patch(
            "claude_storm.agents.subprocess.Popen", return_value=mock_proc
        ) as mock_popen_cls:
            invoke_agent(config, "a", "prompt", system_prompt="sys")

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
        mock_proc = _mock_popen(
            stdout=json.dumps({"result": "Continuing..."}),
        )

        with patch(
            "claude_storm.agents.subprocess.Popen", return_value=mock_proc
        ) as mock_popen_cls:
            response = invoke_agent(config, "b", "Your turn")

        cmd = mock_popen_cls.call_args[0][0]
        assert "--resume" in cmd
        assert "sess-b-uuid" in cmd
        assert "--session-id" not in cmd
        assert response.text == "Continuing..."

    def test_timeout_returns_error(self, make_config):
        config = make_config()
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = _subprocess.TimeoutExpired(
            cmd="claude",
            timeout=300,
        )

        with patch("claude_storm.agents.subprocess.Popen", return_value=mock_proc):
            response = invoke_agent(config, "a", "prompt", timeout=300)

        assert response.is_error
        assert "timed out" in response.text

    def test_nonzero_exit_returns_error(self, make_config):
        config = make_config()
        mock_proc = _mock_popen(stderr="Some error", returncode=1)

        with patch("claude_storm.agents.subprocess.Popen", return_value=mock_proc):
            response = invoke_agent(config, "a", "prompt")

        assert response.is_error
        assert "Some error" in response.text

    def test_cmd_populated_on_error(self, make_config):
        config = make_config()
        mock_proc = _mock_popen(stderr="fail", returncode=1)

        with patch("claude_storm.agents.subprocess.Popen", return_value=mock_proc):
            response = invoke_agent(config, "a", "prompt")

        assert response.cmd is not None
        assert "claude" in response.cmd

    def test_invalid_json_falls_back(self, make_config):
        config = make_config()
        mock_proc = _mock_popen(stdout="Plain text response")

        with patch("claude_storm.agents.subprocess.Popen", return_value=mock_proc):
            response = invoke_agent(config, "a", "prompt")

        assert response.text == "Plain text response"
        assert not response.is_error


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


class TestExtractText:
    def test_result_field(self):
        assert _extract_text({"result": "hello"}) == "hello"

    def test_content_blocks(self):
        data = {
            "content": [
                {"type": "text", "text": "Line 1"},
                {"type": "text", "text": "Line 2"},
            ]
        }
        assert _extract_text(data) == "Line 1\nLine 2"

    def test_fallback_to_str(self):
        assert _extract_text({"unknown": "data"}) == "{'unknown': 'data'}"
