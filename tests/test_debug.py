"""Tests for debug logging utilities."""

import os
import re
import stat

from claude_storm.debug import (
    write_debug_entry,
    write_debug_phase_banner,
    write_debug_request,
    write_debug_response,
    write_debug_summary,
)

# ---------- Security tests ----------


class TestDebugLogPermissions:
    """Issue .5: Debug logs created with restricted permissions."""

    def test_new_log_has_owner_only_permissions(self, tmp_path):
        log_path = tmp_path / "secure_debug.log"
        write_debug_request(
            log_path=log_path,
            turn=1,
            agent_label="Agent A",
            system_prompt="secret system prompt",
            turn_prompt="prompt",
        )
        mode = stat.S_IMODE(os.stat(log_path).st_mode)
        assert mode == 0o600

    def test_appended_log_retains_permissions(self, tmp_path):
        log_path = tmp_path / "append_debug.log"
        write_debug_request(
            log_path=log_path,
            turn=1,
            agent_label="Agent A",
            system_prompt=None,
            turn_prompt="first",
        )
        write_debug_response(
            log_path=log_path,
            cmd=["claude", "-p"],
            raw_response={"result": "ok"},
            directives={
                "memories": [],
                "memory_searches": [],
                "artifacts": [],
                "done": None,
                "ask_user": None,
            },
        )
        mode = stat.S_IMODE(os.stat(log_path).st_mode)
        assert mode == 0o600


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

    def test_header_contains_iso_timestamp(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_request(
            log_path=log_path,
            turn=1,
            agent_label="Agent A",
            system_prompt=None,
            turn_prompt="prompt",
        )
        content = log_path.read_text()
        # Timestamp in ISO format with seconds precision
        assert re.search(r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", content)

    def test_prompt_size_annotations(self, tmp_path):
        log_path = tmp_path / "debug.log"
        system = "line1\nline2\nline3"
        turn = "single line prompt"
        write_debug_request(
            log_path=log_path,
            turn=1,
            agent_label="Agent A",
            system_prompt=system,
            turn_prompt=turn,
        )
        content = log_path.read_text()
        # System prompt: 3 lines
        assert f"[{len(system):,} chars" in content
        assert "3 lines]" in content
        # Turn prompt: 1 line
        assert f"[{len(turn):,} chars" in content
        assert "1 line]" in content

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

    def test_response_text_excerpt(self, tmp_path):
        log_path = tmp_path / "debug.log"
        result_text = "\n".join(f"Line {i}" for i in range(100))
        write_debug_response(
            log_path=log_path,
            cmd=["claude", "-p"],
            raw_response={"result": result_text},
            directives=EMPTY_DIRECTIVES,
        )
        content = log_path.read_text()
        assert "--- RESPONSE TEXT (first 80 lines) ---" in content
        # Extract just the excerpt section
        excerpt_start = content.index("--- RESPONSE TEXT")
        excerpt_end = content.index("--- DIRECTIVES ---")
        excerpt = content[excerpt_start:excerpt_end]
        assert "Line 0" in excerpt
        assert "Line 79" in excerpt
        # Line 80+ should be truncated from the excerpt
        assert "Line 80" not in excerpt

    def test_no_response_text_when_empty(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_response(
            log_path=log_path,
            cmd=["claude", "-p"],
            raw_response={"result": ""},
            directives=EMPTY_DIRECTIVES,
        )
        content = log_path.read_text()
        assert "--- RESPONSE TEXT" not in content

    def test_usage_none_skips_summary(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_response(
            log_path=log_path,
            cmd=["claude", "-p"],
            raw_response={"result": "ok", "usage": None},
            directives=EMPTY_DIRECTIVES,
        )
        content = log_path.read_text()
        assert "--- USAGE SUMMARY ---" not in content

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


class TestWriteDebugPhaseBanner:
    def test_writes_banner(self, tmp_path):
        log_path = tmp_path / "debug.log"
        write_debug_phase_banner(log_path, "COMPILATION PHASE")
        content = log_path.read_text()
        assert "=======================================" in content
        assert "=== COMPILATION PHASE ===" in content

    def test_appends_to_existing(self, tmp_path):
        log_path = tmp_path / "debug.log"
        log_path.write_text("existing content\n")
        write_debug_phase_banner(log_path, "SUMMARY PHASE")
        content = log_path.read_text()
        assert "existing content" in content
        assert "=== SUMMARY PHASE ===" in content


class TestWriteDebugSummary:
    def test_writes_summary_with_duration(self, make_config):
        config = make_config(current_turn=10)
        config.status = "completed"
        config.stop_reason = "max_turns"
        config.agent_watermarks["a"] = {
            "total_cost_usd": 0.50,
            "total_input_tokens": 10000,
            "total_output_tokens": 500,
            "compaction_count": 1,
        }
        config.agent_watermarks["b"] = {
            "total_cost_usd": 0.30,
            "total_input_tokens": 8000,
            "total_output_tokens": 400,
            "compaction_count": 0,
        }
        log_path = config.session_dir() / "debug.log"
        write_debug_summary(log_path, config, duration_s=2292)
        content = log_path.read_text()
        assert "=== SESSION SUMMARY ===" in content
        assert "Turns: 10/10" in content
        assert "Duration: 38m 12s" in content
        assert "completed (max_turns)" in content
        assert "$0.8000" in content
        assert "18,000" in content
        assert "900" in content
        assert "Compactions: 1" in content
        assert "Per-agent breakdown:" in content
        assert "Architect" in content
        assert "Critic" in content

    def test_writes_summary_without_duration(self, make_config):
        config = make_config(current_turn=5)
        config.status = "paused"
        log_path = config.session_dir() / "debug.log"
        write_debug_summary(log_path, config, duration_s=None)
        content = log_path.read_text()
        assert "=== SESSION SUMMARY ===" in content
        assert "Turns: 5/10" in content
        assert "Duration:" not in content
        assert "Status: paused" in content
