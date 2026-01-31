"""Tests for project directory configuration and pacing."""

import pytest
from pathlib import Path

from claude_storm.project import (
    load_project_config,
    scaffold_config,
    format_pacing_block,
    migrate_config,
    STORM_CONFIG_FILENAME,
)


class TestLoadProjectConfig:
    def test_loads_minimal_toml(self, tmp_path):
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text('[session]\ntopic = "Design an API"\n')
        config = load_project_config(toml)
        assert config["topic"] == "Design an API"

    def test_loads_full_toml(self, tmp_path):
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text(
            '[session]\n'
            'topic = "Design a queue"\n'
            'goal = "Produce architecture doc"\n'
            'role_a = "Architect"\n'
            'role_b = "Critic"\n'
            'deliverables = ["Doc A", "Doc B"]\n'
            '\n'
            '[options]\n'
            'max_turns = 30\n'
            'model = "opus"\n'
            'auto_complete = true\n'
            'interactive = false\n'
        )
        config = load_project_config(toml)
        assert config["topic"] == "Design a queue"
        assert config["goal"] == "Produce architecture doc"
        assert config["role_a"] == "Architect"
        assert config["role_b"] == "Critic"
        assert config["deliverables"] == ["Doc A", "Doc B"]
        assert config["max_turns"] == 30
        assert config["model"] == "opus"
        assert config["auto_complete"] is True
        assert config["interactive"] is False

    def test_strips_multiline_whitespace(self, tmp_path):
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text(
            '[session]\n'
            'topic = """\n'
            '  Design a distributed\n'
            '  task queue system\n'
            '"""\n'
        )
        config = load_project_config(toml)
        assert config["topic"].startswith("Design")
        assert not config["topic"].startswith(" ")
        assert not config["topic"].startswith("\n")

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_project_config(tmp_path / "nonexistent.toml")

    def test_missing_topic_raises(self, tmp_path):
        toml = tmp_path / STORM_CONFIG_FILENAME
        toml.write_text('[session]\ngoal = "something"\n')
        with pytest.raises(ValueError, match="topic"):
            load_project_config(toml)


class TestScaffoldConfig:
    def test_scaffold_creates_file(self, tmp_path):
        path = scaffold_config(tmp_path)
        assert path.exists()
        assert path.name == STORM_CONFIG_FILENAME
        content = path.read_text()
        assert "[session]" in content
        assert "topic" in content
        assert "reference_dirs" in content

    def test_scaffold_with_topic(self, tmp_path):
        path = scaffold_config(tmp_path, topic="My cool topic")
        content = path.read_text()
        assert "My cool topic" in content

    def test_scaffold_refuses_overwrite(self, tmp_path):
        scaffold_config(tmp_path)
        with pytest.raises(FileExistsError):
            scaffold_config(tmp_path)

    def test_scaffold_force_overwrites(self, tmp_path):
        scaffold_config(tmp_path, topic="first")
        path = scaffold_config(tmp_path, topic="second", force=True)
        assert "second" in path.read_text()


class TestFormatPacingBlock:
    def test_format_pacing_block_early(self):
        block = format_pacing_block(turn=3, max_turns=20)
        assert "Turn 3 of 20" in block
        assert "15%" in block
        assert "Continue the brainstorm" in block
        assert "halfway" not in block
        assert "75%" not in block
        assert "final turns" not in block

    def test_format_pacing_block_halfway(self):
        block = format_pacing_block(turn=10, max_turns=20)
        assert "Turn 10 of 20" in block
        assert "50%" in block
        assert "halfway" in block

    def test_format_pacing_block_75pct(self):
        block = format_pacing_block(turn=15, max_turns=20)
        assert "75%" in block
        assert "producing deliverables" in block

    def test_format_pacing_block_final(self):
        block = format_pacing_block(turn=19, max_turns=20)
        assert "final turns" in block

    def test_format_pacing_block_last_turn(self):
        block = format_pacing_block(turn=20, max_turns=20)
        assert "final turns" in block

    def test_format_pacing_with_deliverables(self):
        block = format_pacing_block(
            turn=5, max_turns=20,
            deliverables=["Doc A", "Doc B"],
        )
        assert "Expected deliverables" in block
        assert "Doc A" in block
        assert "Doc B" in block

    def test_format_pacing_final_with_deliverables_includes_artifact_instruction(self):
        block = format_pacing_block(
            turn=19, max_turns=20,
            deliverables=["Doc A", "Doc B"],
        )
        assert "final turns" in block
        assert "[ARTIFACT" in block
        assert "[DONE]" in block
        assert "Doc A" in block
        assert "Doc B" in block

    def test_format_pacing_final_without_deliverables_no_artifact_instruction(self):
        block = format_pacing_block(turn=19, max_turns=20)
        assert "final turns" in block
        assert "[ARTIFACT" not in block


class TestMigrateConfig:
    def test_renames_uncommented_reference_dir(self, tmp_path):
        config = tmp_path / STORM_CONFIG_FILENAME
        config.write_text(
            '[session]\ntopic = "Test"\nreference_dir = "/my/notes"\n\n[options]\n'
        )
        messages = migrate_config(config)
        text = config.read_text()
        assert "reference_dir" not in text or "reference_dirs" in text
        assert 'reference_dirs = ["/my/notes"]' in text
        assert any("Renamed" in m for m in messages)

    def test_renames_commented_reference_dir(self, tmp_path):
        config = tmp_path / STORM_CONFIG_FILENAME
        config.write_text(
            '[session]\ntopic = "Test"\n# reference_dir = "/path/to/notes"\n\n[options]\n'
        )
        messages = migrate_config(config)
        text = config.read_text()
        assert "# reference_dirs" in text
        assert "reference_dir =" not in text.replace("reference_dirs", "")

    def test_appends_missing_keys(self, tmp_path):
        config = tmp_path / STORM_CONFIG_FILENAME
        config.write_text('[session]\ntopic = "Test"\n')
        messages = migrate_config(config)
        text = config.read_text()
        assert "# reference_dirs" in text
        assert "# max_turns" in text
        assert "# model" in text
        assert "# auto_complete" in text
        assert "# interactive" in text
        assert len(messages) >= 5  # one per missing key

    def test_no_changes_when_up_to_date(self, tmp_path):
        config = tmp_path / STORM_CONFIG_FILENAME
        scaffold_config(tmp_path, topic="Test")
        messages = migrate_config(config)
        assert messages == []

    def test_does_not_duplicate_existing_keys(self, tmp_path):
        config = tmp_path / STORM_CONFIG_FILENAME
        config.write_text(
            '[session]\ntopic = "Test"\n# reference_dirs = []\n\n'
            '[options]\nmax_turns = 10\n# model = "opus"\n'
            '# auto_complete = false\n# interactive = true\n'
        )
        messages = migrate_config(config)
        # Only missing keys should be added, existing ones left alone
        text = config.read_text()
        assert text.count("max_turns") == 1
        assert text.count("reference_dirs") == 1
