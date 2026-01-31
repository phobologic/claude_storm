"""Tests for agent CLI invocation."""

import json
from unittest.mock import patch, MagicMock

from claude_storm.agents import invoke_agent, _extract_text, _build_allowed_tools, AgentResponse
from claude_storm.config import SessionConfig


def _make_config(tmp_path, monkeypatch):
    storms_dir = tmp_path / ".storms"
    storms_dir.mkdir(exist_ok=True)
    config = SessionConfig(
        session_id="test",
        topic="Test",
        claude_session_a="sess-a",
        claude_session_b="sess-b",
        model="sonnet",
        storms_dir=str(storms_dir),
    )
    config.ensure_dirs()
    return config


class TestInvokeAgent:
    def test_first_turn_uses_session_id(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"result": "Hello from agent A"})
        mock_result.stderr = ""

        with patch("claude_storm.agents.subprocess.run", return_value=mock_result) as mock_run:
            response = invoke_agent(
                config, "a", "Start the brainstorm",
                system_prompt="You are an architect",
            )

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--session-id" in cmd
        assert "sess-a" in cmd
        assert "--system-prompt" in cmd
        assert "--model" in cmd
        assert "--allowedTools" in cmd
        assert response.text == "Hello from agent A"
        assert response.cmd is not None
        assert "claude" in response.cmd

    def test_first_turn_has_path_scoped_tools(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"result": "ok"})
        mock_result.stderr = ""

        with patch("claude_storm.agents.subprocess.run", return_value=mock_result) as mock_run:
            invoke_agent(config, "a", "prompt", system_prompt="sys")

        cmd = mock_run.call_args[0][0]
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

    def test_subsequent_turn_uses_resume(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"result": "Continuing..."})
        mock_result.stderr = ""

        with patch("claude_storm.agents.subprocess.run", return_value=mock_result) as mock_run:
            response = invoke_agent(config, "b", "Your turn")

        cmd = mock_run.call_args[0][0]
        assert "--resume" in cmd
        assert "sess-b" in cmd
        assert "--session-id" not in cmd
        assert response.text == "Continuing..."

    def test_timeout_returns_error(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
        import subprocess
        with patch(
            "claude_storm.agents.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=300),
        ):
            response = invoke_agent(config, "a", "prompt", timeout=300)

        assert response.is_error
        assert "timed out" in response.text

    def test_nonzero_exit_returns_error(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Some error"

        with patch("claude_storm.agents.subprocess.run", return_value=mock_result):
            response = invoke_agent(config, "a", "prompt")

        assert response.is_error
        assert "Some error" in response.text

    def test_cmd_populated_on_error(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "fail"

        with patch("claude_storm.agents.subprocess.run", return_value=mock_result):
            response = invoke_agent(config, "a", "prompt")

        assert response.cmd is not None
        assert "claude" in response.cmd

    def test_invalid_json_falls_back(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Plain text response"
        mock_result.stderr = ""

        with patch("claude_storm.agents.subprocess.run", return_value=mock_result):
            response = invoke_agent(config, "a", "prompt")

        assert response.text == "Plain text response"
        assert not response.is_error


class TestBuildAllowedTools:
    def test_session_dir_only(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
        tools = _build_allowed_tools(config)
        session_path = str(config.session_dir().resolve()).lstrip("/")
        assert f"Read(//{session_path}/**)" in tools
        assert f"Glob(//{session_path}/**)" in tools
        assert f"Grep(//{session_path}/**)" in tools
        assert f"Write(//{session_path}/**)" in tools
        assert f"Edit(//{session_path}/**)" in tools
        # Only 5 tool entries when no reference dir
        assert len(tools) == 5

    def test_with_reference_dir(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
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

    def test_with_multiple_reference_dirs(self, tmp_path, monkeypatch):
        config = _make_config(tmp_path, monkeypatch)
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
