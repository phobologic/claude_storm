"""Tests for debug logging utilities."""

from pathlib import Path
from unittest.mock import MagicMock

from claude_storm.debug import write_debug_entry, debug_pause


class TestWriteDebugEntry:
    def test_writes_sections(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_entry(
            log_path=log_path,
            turn=1,
            agent_label="Agent A",
            cmd=["claude", "-p", "--output-format", "json"],
            system_prompt="You are a brainstormer",
            turn_prompt="Start the discussion",
            raw_response={"result": "Hello"},
            directives={
                "memories": [("Key Idea", ["design"], "Use REST")],
                "memory_searches": [],
                "artifacts": [("api.yaml", "openapi: 3.0")],
                "done": None,
                "ask_user": None,
            },
        )

        content = log_path.read_text()
        assert "=== Turn 1 - Agent A ===" in content
        assert "--- CLI COMMAND ---" in content
        assert "claude -p --output-format json" in content
        assert "--- SYSTEM PROMPT ---" in content
        assert "You are a brainstormer" in content
        assert "--- TURN PROMPT ---" in content
        assert "Start the discussion" in content
        assert "--- RAW RESPONSE ---" in content
        assert '"result": "Hello"' in content
        assert "--- DIRECTIVES ---" in content
        assert "Key Idea" in content
        assert "api.yaml" in content

    def test_omits_system_prompt_when_none(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_entry(
            log_path=log_path,
            turn=2,
            agent_label="Agent B",
            cmd=["claude", "-p", "--resume", "sess-id"],
            system_prompt=None,
            turn_prompt="Continue",
            raw_response={"result": "Ok"},
            directives={
                "memories": [],
                "memory_searches": [],
                "artifacts": [],
                "done": None,
                "ask_user": None,
            },
        )

        content = log_path.read_text()
        assert "--- SYSTEM PROMPT ---" not in content
        assert "--- TURN PROMPT ---" in content

    def test_appends_multiple_entries(self, tmp_path):
        log_path = tmp_path / "debug.log"
        directives = {
            "memories": [],
            "memory_searches": [],
            "artifacts": [],
            "done": None,
            "ask_user": None,
        }
        for i in range(3):
            write_debug_entry(
                log_path=log_path,
                turn=i + 1,
                agent_label=f"Agent {'A' if i % 2 == 0 else 'B'}",
                cmd=["claude", "-p"],
                system_prompt=None,
                turn_prompt=f"Turn {i + 1}",
                raw_response={"result": f"Response {i + 1}"},
                directives=directives,
            )

        content = log_path.read_text()
        assert content.count("=== Turn") == 3


class TestDebugPause:
    def test_calls_console_input(self):
        console = MagicMock()
        console.input = MagicMock(return_value="")
        debug_pause(console)
        console.input.assert_called_once()
        call_arg = console.input.call_args[0][0]
        assert "Press Enter" in call_arg
