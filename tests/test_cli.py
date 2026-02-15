"""Tests for CLI commands, directive parsing, session logic, and compilation."""

import json
from collections import deque
from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from claude_storm.agents import AgentResponse
from claude_storm.cli import _load_and_migrate_toml, _resolve_start_config, app
from claude_storm.compilation import (
    compile_deliverables,
    find_matching_artifacts,
    generate_summary,
)
from claude_storm.config import SessionConfig
from claude_storm.directives import _parse_attrs, _remove_spans, parse_directives
from claude_storm.project import STORM_CONFIG_FILENAME
from claude_storm.session import check_stop, merge_user_input, process_directives

runner = CliRunner()


class TestParseDirectives:
    def test_parse_memory(self):
        text = (
            'Some text [MEMORY title="API Design" tags="api,rest"]'
            "Use REST[/MEMORY] more text"
        )
        result = parse_directives(text)
        assert len(result.memories) == 1
        assert result.memories[0] == ("API Design", ["api", "rest"], "Use REST")
        assert "Some text" in result.clean_text
        assert "more text" in result.clean_text
        assert "[MEMORY" not in result.clean_text

    def test_parse_memory_search(self):
        text = 'Let me check [MEMORY_SEARCH query="auth approaches"]'
        result = parse_directives(text)
        assert result.memory_searches == ["auth approaches"]

    def test_parse_artifact(self):
        text = '[ARTIFACT filename="api.yaml"]openapi: 3.0\npaths: {}[/ARTIFACT]'
        result = parse_directives(text)
        assert len(result.artifacts) == 1
        assert result.artifacts[0][0] == "api.yaml"
        assert "openapi: 3.0" in result.artifacts[0][1]

    def test_parse_done_with_reason(self):
        text = 'I think we covered everything\n[DONE reason="Topic well explored"]'
        result = parse_directives(text)
        assert result.done == "Topic well explored"

    def test_parse_done_without_reason(self):
        text = "I think we're done here\n[DONE]"
        result = parse_directives(text)
        assert result.done == "complete"
        assert "[DONE]" not in result.clean_text

    def test_parse_done_bare_cleans_text(self):
        text = "Final thoughts.\n[DONE]\nThat's all."
        result = parse_directives(text)
        assert result.done == "complete"
        assert "Final thoughts." in result.clean_text
        assert "That's all." in result.clean_text
        assert "[DONE]" not in result.clean_text

    def test_parse_done_with_leading_whitespace(self):
        text = "Some preamble\n  [DONE]\nMore text"
        result = parse_directives(text)
        assert result.done == "complete"

    def test_parse_done_mid_sentence_no_trigger(self):
        text = "Should we follow this plan or aim for [DONE] sooner?"
        result = parse_directives(text)
        assert result.done is None

    def test_parse_done_quoted_context_no_trigger(self):
        text = 'The agent can signal [DONE reason="..."] when finished.'
        result = parse_directives(text)
        assert result.done is None

    def test_parse_ask_user(self):
        text = "What do you think? [ASK_USER]Should we use JWT or OAuth?[/ASK_USER]"
        result = parse_directives(text)
        assert result.ask_user == "Should we use JWT or OAuth?"

    def test_no_directives(self):
        text = "Just a regular response with no special directives."
        result = parse_directives(text)
        assert result.memories == []
        assert result.memory_searches == []
        assert result.artifacts == []
        assert result.done is None
        assert result.ask_user is None
        assert result.clean_text == text

    def test_multiple_memories(self):
        text = (
            '[MEMORY title="A" tags="x"]content A[/MEMORY] '
            '[MEMORY title="B" tags="y"]content B[/MEMORY]'
        )
        result = parse_directives(text)
        assert len(result.memories) == 2

    def test_parse_propose(self):
        text = (
            'Let me propose [PROPOSE title="Use REST"]'
            "We should use REST for the API[/PROPOSE] done"
        )
        result = parse_directives(text)
        assert len(result.proposals) == 1
        assert result.proposals[0] == ("Use REST", "We should use REST for the API")
        assert "[PROPOSE" not in result.clean_text
        assert "Let me propose" in result.clean_text

    def test_parse_accept(self):
        text = 'I agree with that. [ACCEPT id="a3f2"]'
        result = parse_directives(text)
        assert result.accepts == ["a3f2"]
        assert "[ACCEPT" not in result.clean_text

    def test_parse_reject(self):
        text = 'I disagree. [REJECT id="a3f2" reason="Too complex"]'
        result = parse_directives(text)
        assert result.rejects == [("a3f2", "Too complex")]
        assert "[REJECT" not in result.clean_text

    def test_parse_revise(self):
        text = '[REVISE id="a3f2"]Updated: use REST with caching[/REVISE]'
        result = parse_directives(text)
        assert len(result.revisions) == 1
        assert result.revisions[0] == ("a3f2", "Updated: use REST with caching")
        assert "[REVISE" not in result.clean_text

    def test_parse_revise_empty_body_ignored(self):
        result = parse_directives('[REVISE id="abc"][/REVISE]')
        assert result.revisions == []

    def test_parse_multiple_accepts(self):
        text = '[ACCEPT id="a3f2"] [ACCEPT id="b7c1"]'
        result = parse_directives(text)
        assert result.accepts == ["a3f2", "b7c1"]

    def test_no_agreement_directives(self):
        text = "Just a regular response."
        result = parse_directives(text)
        assert result.proposals == []
        assert result.accepts == []
        assert result.rejects == []
        assert result.revisions == []

    def test_artifact_with_extra_title_attr(self):
        """The motivating bug: extra title= attribute should not break parsing."""
        text = '[ARTIFACT title="Act 1" filename="act1.md"]Scene 1 content[/ARTIFACT]'
        result = parse_directives(text)
        assert len(result.artifacts) == 1
        assert result.artifacts[0] == ("act1.md", "Scene 1 content")
        assert "[ARTIFACT" not in result.clean_text

    def test_artifact_attrs_reversed_order(self):
        """Attribute order should not matter."""
        text = '[ARTIFACT filename="ch1.md" title="Chapter 1"]Chapter text[/ARTIFACT]'
        result = parse_directives(text)
        assert len(result.artifacts) == 1
        assert result.artifacts[0][0] == "ch1.md"
        assert result.artifacts[0][1] == "Chapter text"

    def test_memory_with_extra_attrs(self):
        """Extra attributes on MEMORY should be silently ignored."""
        text = '[MEMORY title="Note" tags="a,b" priority="high"]content[/MEMORY]'
        result = parse_directives(text)
        assert len(result.memories) == 1
        assert result.memories[0] == ("Note", ["a", "b"], "content")

    def test_reject_with_extra_attrs(self):
        """Extra attributes on self-closing directives should be ignored."""
        text = '[REJECT id="x1" reason="Too slow" priority="high"]'
        result = parse_directives(text)
        assert result.rejects == [("x1", "Too slow")]
        assert "[REJECT" not in result.clean_text

    def test_reject_attrs_reversed_order(self):
        """Attribute order should not matter for self-closing directives."""
        text = '[REJECT reason="Overengineered" id="p5"]'
        result = parse_directives(text)
        assert result.rejects == [("p5", "Overengineered")]

    def test_mixed_block_and_self_closing(self):
        """Block and self-closing directives coexist in one response."""
        text = (
            "Here is my analysis.\n"
            '[MEMORY title="Key Point" tags="design"]Important insight[/MEMORY]\n'
            '[ACCEPT id="prop1"]\n'
            '[ARTIFACT filename="out.md"]# Output[/ARTIFACT]'
        )
        result = parse_directives(text)
        assert len(result.memories) == 1
        assert result.accepts == ["prop1"]
        assert len(result.artifacts) == 1
        assert "Here is my analysis." in result.clean_text
        assert "[MEMORY" not in result.clean_text
        assert "[ACCEPT" not in result.clean_text
        assert "[ARTIFACT" not in result.clean_text


class TestParseAttrs:
    def test_single_attr(self):
        assert _parse_attrs(' filename="api.yaml"') == {"filename": "api.yaml"}

    def test_multiple_attrs(self):
        result = _parse_attrs(' title="Act 1" filename="act1.md"')
        assert result == {"title": "Act 1", "filename": "act1.md"}

    def test_empty_string(self):
        assert _parse_attrs("") == {}

    def test_empty_value(self):
        assert _parse_attrs(' tags=""') == {"tags": ""}

    def test_attr_with_spaces_in_value(self):
        result = _parse_attrs(' reason="Too complex for MVP"')
        assert result == {"reason": "Too complex for MVP"}


class TestRemoveSpans:
    def test_no_spans(self):
        assert _remove_spans("hello world", []) == "hello world"

    def test_single_span(self):
        assert _remove_spans("hello [TAG] world", [(6, 11)]) == "hello  world"

    def test_multiple_non_overlapping(self):
        text = "AA[X]BB[Y]CC"
        result = _remove_spans(text, [(2, 5), (7, 10)])
        assert result == "AABBCC"

    def test_overlapping_spans_merged(self):
        text = "0123456789"
        # Spans (2,5) and (4,7) overlap — should remove indices 2..7
        result = _remove_spans(text, [(2, 5), (4, 7)])
        assert result == "01789"

    def test_adjacent_spans(self):
        text = "AABBCC"
        result = _remove_spans(text, [(2, 4), (4, 6)])
        assert result == "AA"


class TestCheckStop:
    def test_max_turns(self):
        config = SessionConfig(session_id="t", topic="t", max_turns=5, current_turn=5)
        assert check_stop(config, 0) == "max_turns"

    def test_below_max_turns(self):
        config = SessionConfig(session_id="t", topic="t", max_turns=5, current_turn=3)
        assert check_stop(config, float("inf")) is None

    def test_auto_complete(self):
        config = SessionConfig(
            session_id="t",
            topic="t",
            max_turns=20,
            current_turn=5,
            auto_complete=True,
            done_signals={"a": "complete", "b": "agreed"},
        )
        assert check_stop(config, float("inf")) == "auto_complete"

    def test_auto_complete_one_signal(self):
        config = SessionConfig(
            session_id="t",
            topic="t",
            max_turns=20,
            current_turn=5,
            auto_complete=True,
            done_signals={"a": "complete"},
        )
        assert check_stop(config, float("inf")) is None


class TestStopReason:
    def test_config_has_stop_reason_fields(self):
        config = SessionConfig(session_id="t", topic="t")
        assert config.stop_reason is None
        assert config.stop_error is None

    def test_stop_reason_persisted_in_json(self, make_config):
        config = make_config(
            session_id="sr-test",
            stop_reason="max_turns",
            stop_error=None,
        )
        config.save()
        loaded = SessionConfig.load("sr-test", storms_dir=config.storms_dir)
        assert loaded.stop_reason == "max_turns"
        assert loaded.stop_error is None

    def test_stop_error_persisted_in_json(self, make_config):
        config = make_config(
            session_id="se-test",
            stop_reason="agent_error",
            stop_error="[Agent error: connection reset]",
        )
        config.save()
        loaded = SessionConfig.load("se-test", storms_dir=config.storms_dir)
        assert loaded.stop_reason == "agent_error"
        assert loaded.stop_error == "[Agent error: connection reset]"

    def test_legacy_session_loads_without_stop_fields(self, tmp_storms):
        """Sessions saved before stop_reason existed should load fine."""
        session_dir = tmp_storms / "legacy-sr"
        session_dir.mkdir()
        data = {
            "session_id": "legacy-sr",
            "topic": "t",
            "claude_session_a": "",
            "claude_session_b": "",
            "max_turns": 10,
            "current_turn": 5,
            "started_at": "",
            "status": "paused",
            "done_signals": {},
            "deliverables": [],
            "reference_dirs": [],
            "truncate_conversation": True,
            "storms_dir": str(tmp_storms),
        }
        (session_dir / "session.json").write_text(json.dumps(data))
        loaded = SessionConfig.load("legacy-sr", storms_dir=str(tmp_storms))
        assert loaded.stop_reason is None
        assert loaded.stop_error is None

    def test_show_displays_stop_reason(self, mock_storms_dir):
        config = SessionConfig(
            session_id="show-sr",
            topic="Test topic",
            max_turns=10,
            current_turn=5,
            status="paused",
            started_at="2025-01-31T10:00:00",
            stop_reason="agent_timeout",
            stop_error="[Agent timed out]",
            storms_dir=str(mock_storms_dir),
        )
        config.ensure_dirs()
        config.save()
        result = runner.invoke(app, ["show", "show-sr"])
        assert result.exit_code == 0
        assert "agent_timeout" in result.output
        assert "[Agent timed out]" in result.output


class TestCLICommands:
    def test_list_no_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "claude_storm.cli.get_storms_dir", lambda p: tmp_path / "empty"
        )
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No sessions" in result.output

    def test_list_with_sessions(self, mock_storms_dir):
        config = SessionConfig(
            session_id="abc123",
            topic="Test brainstorm",
            max_turns=10,
            current_turn=3,
            status="completed",
            storms_dir=str(mock_storms_dir),
        )
        config.ensure_dirs()
        config.save()

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "abc123" in result.output
        assert "Test brainstorm" in result.output

    def test_show_session(self, mock_storms_dir):
        config = SessionConfig(
            session_id="show123",
            topic="Show me",
            role_a="Thinker",
            role_b="Doer",
            max_turns=10,
            current_turn=5,
            status="completed",
            model="sonnet",
            started_at="2025-01-31T10:00:00",
            storms_dir=str(mock_storms_dir),
        )
        config.ensure_dirs()
        config.save()

        result = runner.invoke(app, ["show", "show123"])
        assert result.exit_code == 0
        assert "Show me" in result.output
        assert "Thinker" in result.output
        assert "completed" in result.output

    def test_show_displays_duration_and_cost(self, mock_storms_dir):
        config = SessionConfig(
            session_id="showstats",
            topic="Stats test",
            max_turns=10,
            current_turn=8,
            status="completed",
            started_at="2026-02-14T10:00:00+00:00",
            ended_at="2026-02-14T10:38:12+00:00",
            storms_dir=str(mock_storms_dir),
        )
        config.agent_watermarks["a"] = {
            "total_cost_usd": 0.50,
            "total_input_tokens": 10000,
            "total_output_tokens": 500,
        }
        config.agent_watermarks["b"] = {
            "total_cost_usd": 0.30,
            "total_input_tokens": 8000,
            "total_output_tokens": 400,
        }
        config.ensure_dirs()
        config.save()

        result = runner.invoke(app, ["show", "showstats"])
        assert result.exit_code == 0
        assert "38m 12s" in result.output
        assert "$0.8000" in result.output
        assert "18,000" in result.output

    def test_show_nonexistent(self, mock_storms_dir):
        result = runner.invoke(app, ["show", "nonexistent"])
        assert result.exit_code == 1

    def test_resume_nonexistent(self, mock_storms_dir):
        result = runner.invoke(app, ["resume", "nonexistent"])
        assert result.exit_code == 1

    def test_debug_flag_accepted_on_start(self):
        """Verify --debug is accepted as a top-level option before start."""
        result = runner.invoke(app, ["--debug", "start", "--help"])
        assert result.exit_code == 0

    def test_debug_flag_accepted_on_resume(self):
        """Verify --debug is accepted as a top-level option before resume."""
        result = runner.invoke(app, ["--debug", "resume", "--help"])
        assert result.exit_code == 0

    def test_init_creates_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / STORM_CONFIG_FILENAME).exists()

    def test_init_with_topic(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "--topic", "My topic"])
        assert result.exit_code == 0
        content = (tmp_path / STORM_CONFIG_FILENAME).read_text()
        assert "My topic" in content

    def test_init_refuses_overwrite(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / STORM_CONFIG_FILENAME).write_text("existing")
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 1

    @patch("claude_storm.cli.run_session")
    def test_start_reads_config_file(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text(
            '[session]\ntopic = "From TOML"\ngoal = "TOML goal"\n'
            "\n[options]\nmax_turns = 5\n"
        )
        result = runner.invoke(app, ["start"])
        assert result.exit_code == 0
        config = mock_run.call_args[0][0]
        assert config.topic == "From TOML"
        assert config.goal == "TOML goal"
        assert config.max_turns == 5

    @patch("claude_storm.cli.run_session")
    def test_start_topic_arg_backward_compatible(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["start", "Quick topic"])
        assert result.exit_code == 0
        config = mock_run.call_args[0][0]
        assert config.topic == "Quick topic"

    def test_start_no_topic_no_config_errors(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["start"])
        assert result.exit_code == 1
        assert "No topic" in result.output

    @patch("claude_storm.cli.run_session")
    def test_start_with_reference_dir(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ref_dir = tmp_path / "notes"
        ref_dir.mkdir()
        result = runner.invoke(app, ["start", "Topic", "--reference-dir", str(ref_dir)])
        assert result.exit_code == 0
        config = mock_run.call_args[0][0]
        assert config.reference_dirs == [str(ref_dir)]

    @patch("claude_storm.cli.run_session")
    def test_start_with_multiple_reference_dirs(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ref1 = tmp_path / "notes"
        ref1.mkdir()
        ref2 = tmp_path / "docs"
        ref2.mkdir()
        result = runner.invoke(
            app,
            [
                "start",
                "Topic",
                "--reference-dir",
                str(ref1),
                "--reference-dir",
                str(ref2),
            ],
        )
        assert result.exit_code == 0
        config = mock_run.call_args[0][0]
        assert len(config.reference_dirs) == 2
        assert str(ref1) in config.reference_dirs
        assert str(ref2) in config.reference_dirs

    def test_start_reference_dir_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app, ["start", "Topic", "--reference-dir", "/nonexistent/path"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_init_update_migrates_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / STORM_CONFIG_FILENAME
        config_file.write_text(
            '[session]\ntopic = "Test"\nreference_dir = "/old"\n\n[options]\n'
        )
        result = runner.invoke(app, ["init", "--update"])
        assert result.exit_code == 0
        assert "reference_dirs" in config_file.read_text()

    def test_init_update_no_file_errors(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "--update"])
        assert result.exit_code == 1


class TestConsensus:
    def test_done_signal_stored_in_dict(self, make_config, capture_display):
        config = make_config(
            session_id="consensus-test",
            max_turns=20,
            current_turn=5,
            auto_complete=True,
        )
        display, _buf = capture_display
        directives = parse_directives('[DONE reason="All covered"]')
        process_directives(config, "a", directives, display)
        assert config.done_signals == {"a": "All covered"}

    def test_both_agents_agree(self, make_config, capture_display):
        config = make_config(
            session_id="consensus-test",
            max_turns=20,
            current_turn=5,
            auto_complete=True,
        )
        display, _buf = capture_display
        # Agent A signals DONE
        dir_a = parse_directives('[DONE reason="All covered"]')
        process_directives(config, "a", dir_a, display)
        # Agent B also signals DONE (agreement)
        dir_b = parse_directives('[DONE reason="Agreed"]')
        process_directives(config, "b", dir_b, display)
        assert len(config.done_signals) == 2

    def test_disagreement_clears_done(self, make_config, capture_display):
        config = make_config(
            session_id="consensus-test",
            max_turns=20,
            current_turn=5,
            auto_complete=True,
        )
        display, _buf = capture_display
        # Agent A signals DONE
        dir_a = parse_directives('[DONE reason="All covered"]')
        process_directives(config, "a", dir_a, display)
        assert "a" in config.done_signals
        # Agent B responds without DONE (disagreement)
        dir_b = parse_directives("I think we still need to discuss error handling.")
        process_directives(config, "b", dir_b, display)
        assert config.done_signals == {}

    def test_disagreement_display_message(self, make_config, capture_display):
        config = make_config(
            session_id="consensus-test",
            max_turns=20,
            current_turn=5,
            auto_complete=True,
        )
        display, buf = capture_display
        # Agent A signals DONE
        dir_a = parse_directives('[DONE reason="All covered"]')
        process_directives(config, "a", dir_a, display)
        # Agent B disagrees
        dir_b = parse_directives("More to discuss.")
        process_directives(config, "b", dir_b, display)
        output = buf.getvalue()
        assert "disagrees" in output
        assert "DONE" in output


class TestCompileDeliverables:
    def test_skips_when_no_deliverables(self, make_config, capture_display):
        config = make_config(
            session_id="compile-test",
            current_turn=10,
            status="completed",
            deliverables=[],
        )
        display, _buf = capture_display
        with patch("claude_storm.compilation.invoke_agent") as mock_invoke:
            compile_deliverables(config, display)
            mock_invoke.assert_not_called()

    def test_writes_artifact_files(self, make_config, capture_display):
        config = make_config(
            session_id="compile-test",
            current_turn=10,
            status="completed",
            deliverables=["Chapter Summaries", "Character Profiles"],
        )
        # Create some memory files
        mem_dir = config.session_dir() / "agent-a" / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "note1.md").write_text("Some memory content")
        # Create conversation log
        (config.session_dir() / "conversation.md").write_text("## Turn 1\nHello")

        display, _buf = capture_display

        mock_response = AgentResponse(
            text="# Chapter Summaries\n\nChapter 1...", raw={}
        )
        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        artifacts_dir = config.session_dir() / "artifacts"
        assert artifacts_dir.exists()
        files = list(artifacts_dir.glob("*.md"))
        assert len(files) == 2

    def test_shows_error_on_failed_deliverable(self, make_config, capture_display):
        config = make_config(
            session_id="compile-test",
            current_turn=10,
            status="completed",
            deliverables=["Chapter Summaries", "Character Profiles"],
        )
        (config.session_dir() / "conversation.md").write_text("")
        display, buf = capture_display

        error_response = AgentResponse(
            text="[Agent error: timeout]", raw={"error": "timeout"}, is_error=True
        )
        with patch(
            "claude_storm.compilation.invoke_agent", return_value=error_response
        ):
            compile_deliverables(config, display)

        output = buf.getvalue()
        assert "Failed to compile deliverable" in output
        # No artifact files should be written
        artifacts_dir = config.session_dir() / "artifacts"
        md_files = list(artifacts_dir.glob("*.md")) if artifacts_dir.exists() else []
        assert len(md_files) == 0

    def test_uses_distinct_session_ids(self, make_config, capture_display):
        config = make_config(
            session_id="compile-test",
            current_turn=10,
            status="completed",
            deliverables=["Chapter Summaries", "Character Profiles"],
        )
        (config.session_dir() / "conversation.md").write_text("")
        display, _buf = capture_display

        mock_response = AgentResponse(text="content", raw={})
        session_ids = []

        def capture_invoke(**kwargs):
            session_ids.append(kwargs.get("session_id"))
            return mock_response

        with patch("claude_storm.compilation.invoke_agent", side_effect=capture_invoke):
            compile_deliverables(config, display)

        # Should have one session_id per deliverable, all unique and non-None
        assert len(session_ids) == 2
        assert all(sid is not None for sid in session_ids)
        assert session_ids[0] != session_ids[1]
        # None of them should be the agent's brainstorming session ID
        assert all(sid != config.claude_session_a for sid in session_ids)

    def test_sanitizes_filenames(self, make_config, capture_display):
        config = make_config(
            session_id="compile-test",
            current_turn=10,
            status="completed",
            deliverables=["Chapter: Summaries (All)"],
        )
        (config.session_dir() / "conversation.md").write_text("")
        display, _buf = capture_display

        mock_response = AgentResponse(text="content", raw={})
        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        artifacts_dir = config.session_dir() / "artifacts"
        files = list(artifacts_dir.glob("*.md"))
        assert len(files) == 1
        # Should not contain colons or parens
        assert ":" not in files[0].name
        assert "(" not in files[0].name


class TestCompileDeliverablesDebug:
    def test_debug_logging_called_during_compilation(
        self, make_config, capture_display
    ):
        config = make_config(
            session_id="debug-test",
            current_turn=10,
            status="completed",
            deliverables=["Summary Doc"],
            debug=True,
        )
        (config.session_dir() / "conversation.md").write_text("")
        display, _buf = capture_display

        mock_response = AgentResponse(text="content", raw={})
        with (
            patch("claude_storm.compilation.invoke_agent", return_value=mock_response),
            patch("claude_storm.compilation.write_debug_request") as mock_req,
            patch("claude_storm.compilation.write_debug_response") as mock_resp,
        ):
            compile_deliverables(config, display)

        assert mock_req.call_count == 1
        assert mock_resp.call_count == 1

    def test_debug_logging_called_during_summary(self, make_config, capture_display):
        config = make_config(
            session_id="debug-test",
            current_turn=10,
            status="completed",
            deliverables=["Summary Doc"],
            debug=True,
        )
        display, _buf = capture_display

        mock_response = AgentResponse(text="summary content", raw={})
        with (
            patch("claude_storm.compilation.invoke_agent", return_value=mock_response),
            patch("claude_storm.compilation.write_debug_request") as mock_req,
            patch("claude_storm.compilation.write_debug_response") as mock_resp,
        ):
            generate_summary(config, display)

        assert mock_req.call_count == 1
        assert mock_resp.call_count == 1

    def test_readonly_passed_during_compilation(self, make_config, capture_display):
        config = make_config(
            session_id="debug-test",
            current_turn=10,
            status="completed",
            deliverables=["Summary Doc"],
            debug=True,
        )
        (config.session_dir() / "conversation.md").write_text("")
        display, _buf = capture_display

        mock_response = AgentResponse(text="content", raw={})
        with patch(
            "claude_storm.compilation.invoke_agent", return_value=mock_response
        ) as mock_invoke:
            compile_deliverables(config, display)

        assert mock_invoke.call_args.kwargs.get("readonly") is True

    def test_readonly_passed_during_summary(self, make_config, capture_display):
        config = make_config(
            session_id="debug-test",
            current_turn=10,
            status="completed",
            deliverables=["Summary Doc"],
            debug=True,
        )
        display, _buf = capture_display

        mock_response = AgentResponse(text="summary content", raw={})
        with patch(
            "claude_storm.compilation.invoke_agent", return_value=mock_response
        ) as mock_invoke:
            generate_summary(config, display)

        assert mock_invoke.call_args.kwargs.get("readonly") is True


class TestMergeUserInput:
    def test_both_none(self):
        assert merge_user_input(None, None) is None

    def test_ask_user_only(self):
        result = merge_user_input("Q: Should we use JWT?\nA: Yes", None)
        assert "[Agent asked the user a question]:" in result
        assert "Q: Should we use JWT?" in result
        assert "A: Yes" in result

    def test_buffer_only(self):
        q = deque(["focus on security"])
        result = merge_user_input(None, q)
        assert ">>> HUMAN USER INPUT (not from the other agent) <<<" in result
        assert "[User nudge]: focus on security" in result
        assert ">>> END USER INPUT <<<" in result
        # Queue should be drained
        assert len(q) == 0

    def test_both_present(self):
        q = deque(["also consider caching"])
        result = merge_user_input("Q: JWT?\nA: Yes", q)
        assert "[Agent asked the user a question]:" in result
        assert "Q: JWT?" in result
        assert "[User nudge]: also consider caching" in result

    def test_empty_buffer_returns_ask_only(self):
        q: deque[str] = deque()
        result = merge_user_input("Q: JWT?\nA: Yes", q)
        assert "[Agent asked the user a question]:" in result
        assert "Q: JWT?" in result

    def test_empty_buffer_and_no_ask(self):
        q: deque[str] = deque()
        assert merge_user_input(None, q) is None


class TestProcessDirectivesRevisions:
    def test_revise_confirmed_agreement(self, make_config, capture_display):
        """REVISE on a confirmed agreement creates a new proposal."""
        config = make_config(
            session_id="revise-test",
            max_turns=20,
            current_turn=5,
        )
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "summary": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 2,
                "accepted_turn": 3,
                "revises": None,
            }
        ]
        display, _buf = capture_display
        directives = parse_directives('[REVISE id="a3f2"]REST with caching[/REVISE]')
        process_directives(config, "b", directives, display)
        # Original agreement untouched
        assert len(config.accepted_agreements) == 1
        # New pending proposal created
        assert len(config.pending_proposals) == 1
        proposal = config.pending_proposals[0]
        assert proposal["title"] == "Use REST"
        assert proposal["content"] == "REST with caching"
        assert proposal["revises"] == "a3f2"

    def test_revise_pending_proposal(self, make_config, capture_display):
        """REVISE on a pending proposal removes it and creates a replacement."""
        config = make_config(
            session_id="revise-test",
            max_turns=20,
            current_turn=5,
        )
        config.pending_proposals = [
            {
                "id": "b7c1",
                "title": "Add GraphQL",
                "content": "Add a GraphQL gateway.",
                "summary": "Add a GraphQL gateway.",
                "proposed_by": "a",
                "turn": 3,
                "revises": None,
            }
        ]
        display, _buf = capture_display
        directives = parse_directives(
            '[REVISE id="b7c1"]GraphQL with subscriptions[/REVISE]'
        )
        process_directives(config, "b", directives, display)
        # Original pending proposal removed, replaced with revision
        assert len(config.pending_proposals) == 1
        proposal = config.pending_proposals[0]
        assert proposal["id"] != "b7c1"
        assert proposal["title"] == "Add GraphQL"
        assert proposal["content"] == "GraphQL with subscriptions"
        assert proposal["revises"] == "b7c1"
        assert proposal["proposed_by"] == "b"

    def test_revise_unknown_id_uses_fallback_title(self, make_config, capture_display):
        """REVISE on an unknown ID creates a proposal with fallback title."""
        config = make_config(
            session_id="revise-test",
            max_turns=20,
            current_turn=5,
        )
        display, _buf = capture_display
        directives = parse_directives('[REVISE id="zzzz"]Some new content[/REVISE]')
        process_directives(config, "a", directives, display)
        assert len(config.pending_proposals) == 1
        proposal = config.pending_proposals[0]
        assert proposal["title"] == "Revised agreement"
        assert proposal["content"] == "Some new content"
        assert proposal["revises"] == "zzzz"

    def test_revise_own_pending_proposal_skipped(self, make_config, capture_display):
        """REVISE on own pending proposal is rejected with a warning."""
        config = make_config(
            session_id="revise-test",
            max_turns=20,
            current_turn=5,
        )
        config.pending_proposals = [
            {
                "id": "b7c1",
                "title": "Add GraphQL",
                "content": "Add a GraphQL gateway.",
                "summary": "Add a GraphQL gateway.",
                "proposed_by": "a",
                "turn": 3,
                "revises": None,
            }
        ]
        display, buf = capture_display
        directives = parse_directives(
            '[REVISE id="b7c1"]GraphQL with subscriptions[/REVISE]'
        )
        process_directives(config, "a", directives, display)
        # Original proposal unchanged
        assert len(config.pending_proposals) == 1
        assert config.pending_proposals[0]["id"] == "b7c1"
        assert config.pending_proposals[0]["content"] == "Add a GraphQL gateway."
        # Warning displayed
        output = buf.getvalue()
        assert "cannot revise its own pending proposal" in output

    def test_revise_unknown_id_shows_warning(self, make_config, capture_display):
        """REVISE on an unknown ID shows a warning before creating fallback."""
        config = make_config(
            session_id="revise-test",
            max_turns=20,
            current_turn=5,
        )
        display, buf = capture_display
        directives = parse_directives('[REVISE id="zzzz"]Some new content[/REVISE]')
        process_directives(config, "a", directives, display)
        # Fallback proposal still created
        assert len(config.pending_proposals) == 1
        assert config.pending_proposals[0]["title"] == "Revised agreement"
        # Warning displayed
        output = buf.getvalue()
        assert "REVISE target" in output
        assert "not found" in output

    def test_revise_targets_pending_with_accepted_present(
        self, make_config, capture_display
    ):
        """REVISE finds pending target when accepted agreements also exist."""
        config = make_config(
            session_id="revise-test",
            max_turns=20,
            current_turn=5,
        )
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "summary": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 2,
                "accepted_turn": 3,
                "revises": None,
            }
        ]
        config.pending_proposals = [
            {
                "id": "p5k8",
                "title": "Add caching",
                "content": "Redis cache.",
                "summary": "Redis cache.",
                "proposed_by": "a",
                "turn": 3,
                "revises": None,
            }
        ]
        display, _buf = capture_display
        directives = parse_directives('[REVISE id="p5k8"]Memcached instead[/REVISE]')
        process_directives(config, "b", directives, display)
        # Pending removed, revision created with pending's title
        assert len(config.pending_proposals) == 1
        proposal = config.pending_proposals[0]
        assert proposal["title"] == "Add caching"
        assert proposal["content"] == "Memcached instead"
        assert proposal["revises"] == "p5k8"
        assert proposal["proposed_by"] == "b"
        # Accepted agreement untouched
        assert len(config.accepted_agreements) == 1


class TestProcessDirectivesAskUser:
    def test_ask_user_includes_question_and_answer(self, make_config, capture_display):
        """process_directives formats user_input with both Q and A."""
        config = make_config(
            session_id="ask-test",
            max_turns=20,
            current_turn=5,
            interactive=True,
        )
        display, _buf = capture_display
        directives = parse_directives(
            "[ASK_USER]Should we use JWT or OAuth?[/ASK_USER]"
        )

        with patch.object(
            display, "prompt_user", return_value="Use JWT"
        ) as mock_prompt:
            _, user_input = process_directives(config, "a", directives, display)

        mock_prompt.assert_called_once_with("Should we use JWT or OAuth?")
        assert user_input == "Q: Should we use JWT or OAuth?\nA: Use JWT"


class TestFindMatchingArtifacts:
    def test_finds_matching_files(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "chapter_summaries.md").write_text("# Summaries")
        (artifacts_dir / "unrelated.md").write_text("# Other")

        result = find_matching_artifacts(artifacts_dir, "Chapter Summaries")
        assert "chapter_summaries.md" in result
        assert result["chapter_summaries.md"] == "# Summaries"
        assert "unrelated.md" not in result

    def test_returns_empty_for_no_matches(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "something_else.md").write_text("content")

        result = find_matching_artifacts(artifacts_dir, "Chapter Summaries")
        assert result == {}

    def test_returns_empty_for_missing_dir(self, tmp_path):
        result = find_matching_artifacts(tmp_path / "nonexistent", "Doc")
        assert result == {}

    def test_matches_partial_overlap(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "act_1_chapters.md").write_text("# Act 1")
        (artifacts_dir / "act_2_chapters.md").write_text("# Act 2")

        result = find_matching_artifacts(artifacts_dir, "chapters")
        assert "act_1_chapters.md" in result
        assert "act_2_chapters.md" in result

    def test_compile_passes_existing_artifacts(self, make_config, capture_display):
        config = make_config(
            session_id="artifact-test",
            current_turn=10,
            status="completed",
            deliverables=["Chapter Summaries"],
        )

        # Create pre-existing artifact
        artifacts_dir = config.session_dir() / "artifacts"
        (artifacts_dir / "chapter_summaries.md").write_text("# Draft content")
        (config.session_dir() / "conversation.md").write_text("## Turn 1\nHello")

        display, _buf = capture_display
        mock_response = AgentResponse(text="# Final Summaries\n\nDone", raw={})

        prompts_captured = []

        def capture_invoke(**kwargs):
            prompts_captured.append(kwargs.get("prompt", ""))
            return mock_response

        with patch("claude_storm.compilation.invoke_agent", side_effect=capture_invoke):
            compile_deliverables(config, display)

        # The prompt should contain the draft content
        assert len(prompts_captured) == 1
        assert "Draft Content" in prompts_captured[0]
        assert "# Draft content" in prompts_captured[0]


class TestLoadAndMigrateToml:
    def test_no_config_returns_empty(self, tmp_path, monkeypatch):
        """No config file in CWD and no explicit path returns ({}, None)."""
        monkeypatch.chdir(tmp_path)
        console = Console()
        result = _load_and_migrate_toml(None, console)
        assert result == ({}, None)

    def test_auto_detects_storm_toml(self, tmp_path, monkeypatch):
        """Auto-detects storm.toml in CWD."""
        monkeypatch.chdir(tmp_path)
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text('[session]\ntopic = "Auto"\n\n[options]\nmax_turns = 7\n')
        console = Console()
        config, path = _load_and_migrate_toml(None, console)
        assert config["topic"] == "Auto"
        assert config["max_turns"] == 7
        assert path == toml

    def test_explicit_path(self, tmp_path):
        """Explicit config path is used directly."""
        toml = tmp_path / "custom.toml"
        toml.write_text('[session]\ntopic = "Explicit"\n')
        console = Console()
        config, path = _load_and_migrate_toml(toml, console)
        assert config["topic"] == "Explicit"
        assert path == toml

    def test_missing_file_exits(self, tmp_path):
        """Explicit path to missing file raises typer.Exit."""
        from click.exceptions import Exit

        missing = tmp_path / "nope.toml"
        console = Console()
        with pytest.raises(Exit):
            _load_and_migrate_toml(missing, console)

    def test_reference_dir_compat_shim(self, tmp_path, monkeypatch):
        """Old reference_dir key is migrated to reference_dirs."""
        monkeypatch.chdir(tmp_path)
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text('[session]\ntopic = "Compat"\nreference_dir = "/old/path"\n')
        console = Console()
        config, _ = _load_and_migrate_toml(None, console)
        assert "reference_dirs" in config
        assert config["reference_dirs"] == ["/old/path"]
        assert "reference_dir" not in config


class TestResolveStartConfig:
    @patch("claude_storm.cli.run_session")
    def test_basic_topic_returns_config(self, mock_run, tmp_path, monkeypatch):
        """A simple topic argument produces a valid SessionConfig."""
        monkeypatch.chdir(tmp_path)
        console = Console()
        config = _resolve_start_config(
            topic="Test topic",
            config_path=None,
            goal=None,
            roles=None,
            max_turns=None,
            max_minutes=None,
            auto_complete=None,
            interactive=None,
            model=None,
            deliverable=None,
            reference_dir=None,
            agent_timeout=None,
            debug=False,
            console=console,
        )
        assert config.topic == "Test topic"
        assert config.max_turns == 20  # default
        assert config.model == "sonnet"  # default

    def test_cli_overrides_toml(self, tmp_path, monkeypatch):
        """CLI flags override TOML values."""
        monkeypatch.chdir(tmp_path)
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text('[session]\ntopic = "TOML topic"\n\n[options]\nmax_turns = 5\n')
        console = Console()
        config = _resolve_start_config(
            topic="CLI topic",
            config_path=None,
            goal=None,
            roles=None,
            max_turns=15,
            max_minutes=None,
            auto_complete=None,
            interactive=None,
            model=None,
            deliverable=None,
            reference_dir=None,
            agent_timeout=None,
            debug=False,
            console=console,
        )
        assert config.topic == "CLI topic"
        assert config.max_turns == 15

    def test_no_topic_exits(self, tmp_path, monkeypatch):
        """Missing topic raises typer.Exit."""
        from click.exceptions import Exit

        monkeypatch.chdir(tmp_path)
        console = Console()
        with pytest.raises(Exit):
            _resolve_start_config(
                topic=None,
                config_path=None,
                goal=None,
                roles=None,
                max_turns=None,
                max_minutes=None,
                auto_complete=None,
                interactive=None,
                model=None,
                deliverable=None,
                reference_dir=None,
                agent_timeout=None,
                debug=False,
                console=console,
            )

    def test_invalid_reference_dir_exits(self, tmp_path, monkeypatch):
        """Non-existent reference dir raises typer.Exit."""
        from pathlib import Path as P

        from click.exceptions import Exit

        monkeypatch.chdir(tmp_path)
        console = Console()
        with pytest.raises(Exit):
            _resolve_start_config(
                topic="Topic",
                config_path=None,
                goal=None,
                roles=None,
                max_turns=None,
                max_minutes=None,
                auto_complete=None,
                interactive=None,
                model=None,
                deliverable=None,
                reference_dir=[P("/nonexistent/path")],
                agent_timeout=None,
                debug=False,
                console=console,
            )

    def test_debug_passed_through(self, tmp_path, monkeypatch):
        """Debug flag is passed through to SessionConfig."""
        monkeypatch.chdir(tmp_path)
        console = Console()
        config = _resolve_start_config(
            topic="Debug test",
            config_path=None,
            goal=None,
            roles=None,
            max_turns=None,
            max_minutes=None,
            auto_complete=None,
            interactive=None,
            model=None,
            deliverable=None,
            reference_dir=None,
            agent_timeout=None,
            debug=True,
            console=console,
        )
        assert config.debug is True
