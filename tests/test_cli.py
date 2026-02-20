"""Tests for CLI commands, config loading, and start config resolution."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from claude_storm.cli import _load_and_migrate_toml, _resolve_start_config, app
from claude_storm.config import SessionConfig
from claude_storm.project import STORM_CONFIG_FILENAME

runner = CliRunner()


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


def _resolve(console, **overrides):
    """Call _resolve_start_config with all-None defaults; override as needed."""
    defaults = {
        "topic": None,
        "config_path": None,
        "goal": None,
        "roles": None,
        "max_turns": None,
        "max_minutes": None,
        "auto_complete": None,
        "interactive": None,
        "model": None,
        "deliverable": None,
        "reference_dir": None,
        "agent_timeout": None,
        "debug": False,
    }
    defaults.update(overrides)
    return _resolve_start_config(console=console, **defaults)


class TestResolveStartConfig:
    @patch("claude_storm.cli.run_session")
    def test_basic_topic_returns_config(self, mock_run, tmp_path, monkeypatch):
        """A simple topic argument produces a valid SessionConfig."""
        monkeypatch.chdir(tmp_path)
        console = Console()
        config = _resolve(console, topic="Test topic")
        assert config.topic == "Test topic"
        assert config.max_turns == 20  # default
        assert config.model == "sonnet"  # default

    def test_cli_overrides_toml(self, tmp_path, monkeypatch):
        """CLI flags override TOML values."""
        monkeypatch.chdir(tmp_path)
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text('[session]\ntopic = "TOML topic"\n\n[options]\nmax_turns = 5\n')
        console = Console()
        config = _resolve(console, topic="CLI topic", max_turns=15)
        assert config.topic == "CLI topic"
        assert config.max_turns == 15

    def test_no_topic_exits(self, tmp_path, monkeypatch):
        """Missing topic raises typer.Exit."""
        from click.exceptions import Exit

        monkeypatch.chdir(tmp_path)
        console = Console()
        with pytest.raises(Exit):
            _resolve(console)

    def test_invalid_reference_dir_exits(self, tmp_path, monkeypatch):
        """Non-existent reference dir raises typer.Exit."""
        from pathlib import Path as P

        from click.exceptions import Exit

        monkeypatch.chdir(tmp_path)
        console = Console()
        with pytest.raises(Exit):
            _resolve(console, topic="Topic", reference_dir=[P("/nonexistent/path")])

    def test_debug_passed_through(self, tmp_path, monkeypatch):
        """Debug flag is passed through to SessionConfig."""
        monkeypatch.chdir(tmp_path)
        console = Console()
        config = _resolve(console, topic="Debug test", debug=True)
        assert config.debug is True
