"""Integration tests for run_session() turn loop."""

from unittest.mock import patch

import pytest

from claude_storm.agents import AgentResponse
from claude_storm.session import run_session


def _make_response(
    text="Agent response.",
    usage=None,
    is_error=False,
    timed_out=False,
    cost_usd=None,
):
    """Build an AgentResponse with sensible defaults."""
    raw = {"result": text}
    if cost_usd is not None:
        raw["total_cost_usd"] = cost_usd
    return AgentResponse(
        text=text,
        raw=raw,
        cmd=["claude", "-p"],
        is_error=is_error,
        timed_out=timed_out,
        usage=usage or {"input_tokens": 100, "output_tokens": 50},
    )


class TestRunSession:
    """Integration tests for the run_session() main loop."""

    @pytest.fixture(autouse=True)
    def _setup(self, make_config, capture_display):
        self.make_config = make_config
        self.display, self.buf = capture_display

    # ------------------------------------------------------------------ #
    # Basic turn mechanics
    # ------------------------------------------------------------------ #

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_basic_two_turn_session(self, mock_invoke, mock_compile, mock_summary):
        """max_turns=2 → both agents called, status=completed, compilation triggered."""
        mock_invoke.side_effect = [
            _make_response("Turn 1 from A"),
            _make_response("Turn 2 from B"),
        ]
        config = self.make_config(max_turns=2)

        run_session(config, self.display)

        assert mock_invoke.call_count == 2
        assert config.status == "completed"
        assert config.stop_reason == "max_turns"
        mock_compile.assert_called_once_with(config, self.display)
        mock_summary.assert_called_once_with(config, self.display)

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_turn_alternation(self, mock_invoke, mock_compile, mock_summary):
        """Agent A at turn 0, Agent B at turn 1."""
        mock_invoke.side_effect = [
            _make_response("A says hello"),
            _make_response("B responds"),
        ]
        config = self.make_config(max_turns=2)

        run_session(config, self.display)

        calls = mock_invoke.call_args_list
        assert calls[0].kwargs["agent"] == "a"
        assert calls[1].kwargs["agent"] == "b"

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_zero_turns(self, mock_invoke, mock_compile, mock_summary):
        """max_turns=0 → immediate completion, invoke_agent never called."""
        config = self.make_config(max_turns=0)

        run_session(config, self.display)

        mock_invoke.assert_not_called()
        assert config.status == "completed"
        assert config.stop_reason == "max_turns"

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_single_turn(self, mock_invoke, mock_compile, mock_summary):
        """max_turns=1 → only Agent A runs."""
        mock_invoke.side_effect = [_make_response("Only A")]
        config = self.make_config(max_turns=1)

        run_session(config, self.display)

        assert mock_invoke.call_count == 1
        assert mock_invoke.call_args.kwargs["agent"] == "a"
        assert config.current_turn == 1

    # ------------------------------------------------------------------ #
    # Auto-complete / done signals
    # ------------------------------------------------------------------ #

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_auto_complete_consensus(self, mock_invoke, mock_compile, mock_summary):
        """Both agents [DONE] → early stop, stop_reason=auto_complete."""
        mock_invoke.side_effect = [
            _make_response('A is done\n[DONE reason="consensus"]'),
            _make_response('B agrees\n[DONE reason="consensus"]'),
            _make_response("Should not be called"),
        ]
        config = self.make_config(max_turns=10, auto_complete=True)

        run_session(config, self.display)

        assert mock_invoke.call_count == 2
        assert config.stop_reason == "auto_complete"
        assert config.status == "completed"

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_done_disagreement_clears_signal(
        self, mock_invoke, mock_compile, mock_summary
    ):
        """A sends [DONE], B doesn't → A's signal cleared, runs all turns."""
        mock_invoke.side_effect = [
            _make_response('A done\n[DONE reason="finished"]'),
            _make_response("B disagrees, no DONE"),
            _make_response("A continues"),
            _make_response("B continues"),
        ]
        config = self.make_config(max_turns=4, auto_complete=True)

        run_session(config, self.display)

        assert config.stop_reason == "max_turns"
        assert config.current_turn == 4

    # ------------------------------------------------------------------ #
    # Directive processing — memory
    # ------------------------------------------------------------------ #

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_directive_memory_saved(self, mock_invoke, mock_compile, mock_summary):
        """[MEMORY] in response → file created in agent-a/memory/."""
        mock_invoke.side_effect = [
            _make_response(
                'Some text\n[MEMORY title="key-insight" tags="arch"]'
                "This is important[/MEMORY]"
            ),
        ]
        config = self.make_config(max_turns=1)

        run_session(config, self.display)

        memory_dir = config.session_dir() / "agent-a" / "memory"
        memory_files = list(memory_dir.glob("*.md"))
        assert len(memory_files) == 1
        content = memory_files[0].read_text()
        assert "This is important" in content

    # ------------------------------------------------------------------ #
    # Watermark updates
    # ------------------------------------------------------------------ #

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_watermark_updates(self, mock_invoke, mock_compile, mock_summary):
        """After each turn, watermark has correct usage/cost/last_turn."""
        mock_invoke.side_effect = [
            _make_response(
                "A turn",
                usage={"input_tokens": 200, "output_tokens": 100},
                cost_usd=0.05,
            ),
            _make_response(
                "B turn",
                usage={"input_tokens": 300, "output_tokens": 150},
                cost_usd=0.08,
            ),
        ]
        config = self.make_config(max_turns=2)

        run_session(config, self.display)

        wm_a = config.get_watermark("a")
        assert wm_a["last_turn"] == 0
        assert wm_a["total_input_tokens"] == 200
        assert wm_a["total_cost_usd"] == pytest.approx(0.05)

        wm_b = config.get_watermark("b")
        assert wm_b["last_turn"] == 1
        assert wm_b["total_input_tokens"] == 300
        assert wm_b["total_cost_usd"] == pytest.approx(0.08)

    # ------------------------------------------------------------------ #
    # Error / timeout → paused
    # ------------------------------------------------------------------ #

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_agent_error_pauses_session(self, mock_invoke, mock_compile, mock_summary):
        """is_error=True → status=paused, stop_reason=agent_error."""
        mock_invoke.side_effect = [
            _make_response("Error occurred", is_error=True),
        ]
        config = self.make_config(max_turns=4)

        run_session(config, self.display)

        assert config.status == "paused"
        assert config.stop_reason == "agent_error"

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_agent_timeout_pauses(self, mock_invoke, mock_compile, mock_summary):
        """timed_out=True → stop_reason=agent_timeout."""
        mock_invoke.side_effect = [
            _make_response("Timed out", is_error=True, timed_out=True),
        ]
        config = self.make_config(max_turns=4)

        run_session(config, self.display)

        assert config.status == "paused"
        assert config.stop_reason == "agent_timeout"

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_compilation_not_triggered_on_pause(
        self, mock_invoke, mock_compile, mock_summary
    ):
        """Error path → compile/summary not called."""
        mock_invoke.side_effect = [
            _make_response("Boom", is_error=True),
        ]
        config = self.make_config(max_turns=4)

        run_session(config, self.display)

        mock_compile.assert_not_called()
        mock_summary.assert_not_called()

    # ------------------------------------------------------------------ #
    # Conversation log
    # ------------------------------------------------------------------ #

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_conversation_log_written(self, mock_invoke, mock_compile, mock_summary):
        """conversation.md contains both agents' text."""
        mock_invoke.side_effect = [
            _make_response("Alpha says hello"),
            _make_response("Beta responds nicely"),
        ]
        config = self.make_config(max_turns=2)

        run_session(config, self.display)

        conv = (config.session_dir() / "conversation.md").read_text()
        assert "Alpha says hello" in conv
        assert "Beta responds nicely" in conv

    # ------------------------------------------------------------------ #
    # ended_at
    # ------------------------------------------------------------------ #

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_ended_at_set_on_success(self, mock_invoke, mock_compile, mock_summary):
        """ended_at populated on successful completion."""
        mock_invoke.side_effect = [_make_response("Done")]
        config = self.make_config(max_turns=1)

        run_session(config, self.display)

        assert config.ended_at != ""

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_ended_at_set_on_error(self, mock_invoke, mock_compile, mock_summary):
        """ended_at populated on error path too."""
        mock_invoke.side_effect = [
            _make_response("Error", is_error=True),
        ]
        config = self.make_config(max_turns=4)

        run_session(config, self.display)

        assert config.ended_at != ""

    # ------------------------------------------------------------------ #
    # Resume mid-session
    # ------------------------------------------------------------------ #

    @patch("claude_storm.session.generate_summary")
    @patch("claude_storm.session.compile_deliverables")
    @patch("claude_storm.session.invoke_agent")
    def test_resume_mid_session(self, mock_invoke, mock_compile, mock_summary):
        """current_turn=2 → picks up with Agent A, runs remaining turns."""
        mock_invoke.side_effect = [
            _make_response("A resumes"),
            _make_response("B follows"),
        ]
        config = self.make_config(max_turns=4, current_turn=2)

        run_session(config, self.display)

        calls = mock_invoke.call_args_list
        # Turn 2 → agent A (even turns), turn 3 → agent B (odd turns)
        assert calls[0].kwargs["agent"] == "a"
        assert calls[1].kwargs["agent"] == "b"
        assert config.current_turn == 4
