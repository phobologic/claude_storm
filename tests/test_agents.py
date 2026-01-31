"""Tests for agent CLI invocation."""

import json
from unittest.mock import patch, MagicMock

from claude_storm.agents import invoke_agent, _extract_text, AgentResponse
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
        assert response.text == "Hello from agent A"
        assert response.cmd is not None
        assert "claude" in response.cmd

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
