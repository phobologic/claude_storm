"""Tests for debug logging utilities."""

from claude_storm.debug import (
    write_debug_entry,
    write_debug_request,
    write_debug_response,
)

SAMPLE_DIRECTIVES = {
    "memories": [("Key Idea", ["design"], "Use REST")],
    "memory_searches": [],
    "artifacts": [("api.yaml", "openapi: 3.0")],
    "done": None,
    "ask_user": None,
}

EMPTY_DIRECTIVES = {
    "memories": [],
    "memory_searches": [],
    "artifacts": [],
    "done": None,
    "ask_user": None,
}


class TestWriteDebugRequest:
    def test_writes_header_and_prompts(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_request(
            log_path=log_path,
            turn=1,
            agent_label="Agent A",
            system_prompt="You are a brainstormer",
            turn_prompt="Start the discussion",
        )

        content = log_path.read_text()
        assert "=== Turn 1 - Agent A ===" in content
        assert "--- SYSTEM PROMPT ---" in content
        assert "You are a brainstormer" in content
        assert "--- TURN PROMPT ---" in content
        assert "Start the discussion" in content

    def test_omits_system_prompt_when_none(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_request(
            log_path=log_path,
            turn=2,
            agent_label="Agent B",
            system_prompt=None,
            turn_prompt="Continue",
        )

        content = log_path.read_text()
        assert "--- SYSTEM PROMPT ---" not in content
        assert "--- TURN PROMPT ---" in content
        assert "Continue" in content

    def test_does_not_contain_response_sections(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_request(
            log_path=log_path,
            turn=1,
            agent_label="Agent A",
            system_prompt="sys",
            turn_prompt="prompt",
        )

        content = log_path.read_text()
        assert "--- CLI COMMAND ---" not in content
        assert "--- RAW RESPONSE ---" not in content
        assert "--- DIRECTIVES ---" not in content


class TestWriteDebugResponse:
    def test_writes_cmd_response_directives(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_response(
            log_path=log_path,
            cmd=["claude", "-p", "--output-format", "json"],
            raw_response={"result": "Hello"},
            directives=SAMPLE_DIRECTIVES,
        )

        content = log_path.read_text()
        assert "--- CLI COMMAND ---" in content
        assert "claude -p --output-format json" in content
        assert "--- RAW RESPONSE ---" in content
        assert '"result": "Hello"' in content
        assert "--- DIRECTIVES ---" in content
        assert "Key Idea" in content
        assert "api.yaml" in content

    def test_does_not_contain_header(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_response(
            log_path=log_path,
            cmd=["claude", "-p"],
            raw_response={"result": "Ok"},
            directives=EMPTY_DIRECTIVES,
        )

        content = log_path.read_text()
        assert "=== Turn" not in content
        assert "--- TURN PROMPT ---" not in content
        assert "--- SYSTEM PROMPT ---" not in content


class TestRequestThenResponse:
    def test_combined_matches_full_format(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_request(
            log_path=log_path,
            turn=1,
            agent_label="Agent A",
            system_prompt="You are a brainstormer",
            turn_prompt="Start the discussion",
        )
        write_debug_response(
            log_path=log_path,
            cmd=["claude", "-p", "--output-format", "json"],
            raw_response={"result": "Hello"},
            directives=SAMPLE_DIRECTIVES,
        )

        content = log_path.read_text()
        # All sections present in order
        assert "=== Turn 1 - Agent A ===" in content
        assert "--- SYSTEM PROMPT ---" in content
        assert "--- TURN PROMPT ---" in content
        assert "--- CLI COMMAND ---" in content
        assert "--- RAW RESPONSE ---" in content
        assert "--- DIRECTIVES ---" in content

        # Verify ordering: header before prompts before response
        header_pos = content.index("=== Turn 1")
        system_pos = content.index("--- SYSTEM PROMPT ---")
        turn_pos = content.index("--- TURN PROMPT ---")
        cmd_pos = content.index("--- CLI COMMAND ---")
        response_pos = content.index("--- RAW RESPONSE ---")
        directives_pos = content.index("--- DIRECTIVES ---")
        assert (
            header_pos < system_pos < turn_pos < cmd_pos < response_pos < directives_pos
        )


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
            directives=SAMPLE_DIRECTIVES,
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
            directives=EMPTY_DIRECTIVES,
        )

        content = log_path.read_text()
        assert "--- SYSTEM PROMPT ---" not in content
        assert "--- TURN PROMPT ---" in content

    def test_appends_multiple_entries(self, tmp_path):
        log_path = tmp_path / "debug.log"
        for i in range(3):
            write_debug_entry(
                log_path=log_path,
                turn=i + 1,
                agent_label=f"Agent {'A' if i % 2 == 0 else 'B'}",
                cmd=["claude", "-p"],
                system_prompt=None,
                turn_prompt=f"Turn {i + 1}",
                raw_response={"result": f"Response {i + 1}"},
                directives=EMPTY_DIRECTIVES,
            )

        content = log_path.read_text()
        assert content.count("=== Turn") == 3
