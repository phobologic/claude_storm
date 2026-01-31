"""Tests for CLI commands and directive parsing."""

import json
from io import StringIO
from unittest.mock import patch, MagicMock

from rich.console import Console

from typer.testing import CliRunner

from claude_storm.cli import app, _parse_directives, _check_stop, _compile_deliverables
from claude_storm.agents import AgentResponse
from claude_storm.config import SessionConfig
from claude_storm.display import Display
from claude_storm.project import STORM_CONFIG_FILENAME

runner = CliRunner()


class TestParseDirectives:
    def test_parse_memory(self):
        text = 'Some text [MEMORY title="API Design" tags="api,rest"]Use REST[/MEMORY] more text'
        result = _parse_directives(text)
        assert len(result["memories"]) == 1
        assert result["memories"][0] == ("API Design", ["api", "rest"], "Use REST")
        assert "Some text" in result["clean_text"]
        assert "more text" in result["clean_text"]
        assert "[MEMORY" not in result["clean_text"]

    def test_parse_memory_search(self):
        text = 'Let me check [MEMORY_SEARCH query="auth approaches"]'
        result = _parse_directives(text)
        assert result["memory_searches"] == ["auth approaches"]

    def test_parse_artifact(self):
        text = '[ARTIFACT filename="api.yaml"]openapi: 3.0\npaths: {}[/ARTIFACT]'
        result = _parse_directives(text)
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0][0] == "api.yaml"
        assert "openapi: 3.0" in result["artifacts"][0][1]

    def test_parse_done_with_reason(self):
        text = 'I think we covered everything [DONE reason="Topic well explored"]'
        result = _parse_directives(text)
        assert result["done"] == "Topic well explored"

    def test_parse_done_without_reason(self):
        text = "I think we're done here [DONE]"
        result = _parse_directives(text)
        assert result["done"] == "complete"
        assert "[DONE]" not in result["clean_text"]

    def test_parse_done_bare_cleans_text(self):
        text = "Final thoughts. [DONE] That's all."
        result = _parse_directives(text)
        assert result["done"] == "complete"
        assert "Final thoughts." in result["clean_text"]
        assert "That's all." in result["clean_text"]
        assert "[DONE]" not in result["clean_text"]

    def test_parse_ask_user(self):
        text = "What do you think? [ASK_USER]Should we use JWT or OAuth?[/ASK_USER]"
        result = _parse_directives(text)
        assert result["ask_user"] == "Should we use JWT or OAuth?"

    def test_no_directives(self):
        text = "Just a regular response with no special directives."
        result = _parse_directives(text)
        assert result["memories"] == []
        assert result["memory_searches"] == []
        assert result["artifacts"] == []
        assert result["done"] is None
        assert result["ask_user"] is None
        assert result["clean_text"] == text

    def test_multiple_memories(self):
        text = (
            '[MEMORY title="A" tags="x"]content A[/MEMORY] '
            '[MEMORY title="B" tags="y"]content B[/MEMORY]'
        )
        result = _parse_directives(text)
        assert len(result["memories"]) == 2


class TestCheckStop:
    def test_max_turns(self):
        config = SessionConfig(
            session_id="t", topic="t", max_turns=5, current_turn=5
        )
        assert _check_stop(config, 0) == "max_turns"

    def test_below_max_turns(self):
        config = SessionConfig(
            session_id="t", topic="t", max_turns=5, current_turn=3
        )
        assert _check_stop(config, float("inf")) is None

    def test_auto_complete(self):
        config = SessionConfig(
            session_id="t",
            topic="t",
            max_turns=20,
            current_turn=5,
            auto_complete=True,
            done_signals=["a", "b"],
        )
        assert _check_stop(config, float("inf")) == "auto_complete"

    def test_auto_complete_one_signal(self):
        config = SessionConfig(
            session_id="t",
            topic="t",
            max_turns=20,
            current_turn=5,
            auto_complete=True,
            done_signals=["a"],
        )
        assert _check_stop(config, float("inf")) is None


class TestCLICommands:
    def test_list_no_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setattr("claude_storm.cli.get_storms_dir", lambda p: tmp_path / "empty")
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No sessions" in result.output

    def test_list_with_sessions(self, tmp_storms, monkeypatch):
        monkeypatch.setattr("claude_storm.cli.get_storms_dir", lambda p: tmp_storms)
        config = SessionConfig(
            session_id="abc123",
            topic="Test brainstorm",
            max_turns=10,
            current_turn=3,
            status="completed",
            storms_dir=str(tmp_storms),
        )
        config.ensure_dirs()
        config.save()

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "abc123" in result.output
        assert "Test brainstorm" in result.output

    def test_show_session(self, tmp_storms, monkeypatch):
        monkeypatch.setattr("claude_storm.cli.get_storms_dir", lambda p: tmp_storms)
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
            storms_dir=str(tmp_storms),
        )
        config.ensure_dirs()
        config.save()

        result = runner.invoke(app, ["show", "show123"])
        assert result.exit_code == 0
        assert "Show me" in result.output
        assert "Thinker" in result.output
        assert "completed" in result.output

    def test_show_nonexistent(self, tmp_storms, monkeypatch):
        monkeypatch.setattr("claude_storm.cli.get_storms_dir", lambda p: tmp_storms)
        result = runner.invoke(app, ["show", "nonexistent"])
        assert result.exit_code == 1

    def test_resume_nonexistent(self, tmp_storms, monkeypatch):
        monkeypatch.setattr("claude_storm.cli.get_storms_dir", lambda p: tmp_storms)
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
            '\n[options]\nmax_turns = 5\n'
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
        result = runner.invoke(
            app, ["start", "Topic", "--reference-dir", str(ref_dir)]
        )
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
            ["start", "Topic", "--reference-dir", str(ref1), "--reference-dir", str(ref2)],
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
        config_file.write_text('[session]\ntopic = "Test"\nreference_dir = "/old"\n\n[options]\n')
        result = runner.invoke(app, ["init", "--update"])
        assert result.exit_code == 0
        assert "reference_dirs" in config_file.read_text()

    def test_init_update_no_file_errors(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "--update"])
        assert result.exit_code == 1


class TestCompileDeliverables:
    def _make_config(self, tmp_storms, **kwargs):
        defaults = dict(
            session_id="compile-test",
            topic="Test topic",
            goal="Test goal",
            role_a="Agent A",
            role_b="Agent B",
            max_turns=10,
            current_turn=10,
            status="completed",
            model="sonnet",
            deliverables=["Chapter Summaries", "Character Profiles"],
            storms_dir=str(tmp_storms),
        )
        defaults.update(kwargs)
        config = SessionConfig(**defaults)
        config.ensure_dirs()
        return config

    def test_skips_when_no_deliverables(self, tmp_storms):
        config = self._make_config(tmp_storms, deliverables=[])
        display = Display(console=Console(file=StringIO(), force_terminal=True, no_color=True))
        with patch("claude_storm.cli.invoke_agent") as mock_invoke:
            _compile_deliverables(config, display)
            mock_invoke.assert_not_called()

    def test_writes_artifact_files(self, tmp_storms):
        config = self._make_config(tmp_storms)
        # Create some memory files
        mem_dir = config.session_dir() / "agent-a" / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "note1.md").write_text("Some memory content")
        # Create conversation log
        (config.session_dir() / "conversation.md").write_text("## Turn 1\nHello")

        display = Display(console=Console(file=StringIO(), force_terminal=True, no_color=True))

        mock_response = AgentResponse(text="# Chapter Summaries\n\nChapter 1...", raw={})
        with patch("claude_storm.cli.invoke_agent", return_value=mock_response):
            _compile_deliverables(config, display)

        artifacts_dir = config.session_dir() / "artifacts"
        assert artifacts_dir.exists()
        files = list(artifacts_dir.glob("*.md"))
        assert len(files) == 2

    def test_sanitizes_filenames(self, tmp_storms):
        config = self._make_config(
            tmp_storms,
            deliverables=["Chapter: Summaries (All)"],
        )
        (config.session_dir() / "conversation.md").write_text("")
        display = Display(console=Console(file=StringIO(), force_terminal=True, no_color=True))

        mock_response = AgentResponse(text="content", raw={})
        with patch("claude_storm.cli.invoke_agent", return_value=mock_response):
            _compile_deliverables(config, display)

        artifacts_dir = config.session_dir() / "artifacts"
        files = list(artifacts_dir.glob("*.md"))
        assert len(files) == 1
        # Should not contain colons or parens
        assert ":" not in files[0].name
        assert "(" not in files[0].name
