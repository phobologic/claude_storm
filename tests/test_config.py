"""Tests for session configuration."""

import json

from claude_storm.config import SessionConfig


class TestSessionConfig:
    def test_create_generates_ids(self):
        config = SessionConfig.create(topic="Test topic")
        assert config.session_id
        assert config.claude_session_a
        assert config.claude_session_b
        assert config.claude_session_a != config.claude_session_b
        assert config.status == "active"
        assert config.started_at

    def test_create_with_options(self):
        config = SessionConfig.create(
            topic="Design an API",
            goal="RESTful endpoints",
            role_a="Architect",
            role_b="Critic",
            max_turns=30,
            max_minutes=60,
            auto_complete=True,
            interactive=True,
            model="opus",
        )
        assert config.topic == "Design an API"
        assert config.goal == "RESTful endpoints"
        assert config.role_a == "Architect"
        assert config.role_b == "Critic"
        assert config.max_turns == 30
        assert config.max_minutes == 60
        assert config.auto_complete is True
        assert config.interactive is True
        assert config.model == "opus"

    def test_save_and_load(self, sample_config, tmp_storms):
        loaded = SessionConfig.load(
            sample_config.session_id, storms_dir=str(tmp_storms)
        )
        assert loaded.session_id == sample_config.session_id
        assert loaded.topic == sample_config.topic
        assert loaded.role_a == sample_config.role_a
        assert loaded.role_b == sample_config.role_b
        assert loaded.claude_session_a == sample_config.claude_session_a
        assert loaded.max_turns == sample_config.max_turns

    def test_save_creates_json_file(self, sample_config):
        path = sample_config.session_dir() / "session.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["topic"] == "Test topic"

    def test_ensure_dirs(self, sample_config):
        d = sample_config.session_dir()
        assert (d / "agent-a" / "memory").is_dir()
        assert (d / "agent-b" / "memory").is_dir()
        assert (d / "artifacts").is_dir()

    def test_agent_label_with_roles(self, sample_config):
        assert sample_config.agent_label("a") == "Architect"
        assert sample_config.agent_label("b") == "Critic"

    def test_agent_label_without_roles(self):
        config = SessionConfig(
            session_id="nolabel",
            topic="Test",
        )
        assert config.agent_label("a") == "Agent A"
        assert config.agent_label("b") == "Agent B"

    def test_session_dir_with_storms_dir(self, sample_config, tmp_storms):
        assert sample_config.session_dir() == tmp_storms / "test123"

    def test_session_dir_fallback(self):
        config = SessionConfig(session_id="x", topic="t")
        assert config.session_dir().name == "x"
        assert "sessions" in str(config.session_dir())

    def test_done_signals_default(self):
        config = SessionConfig(session_id="x", topic="t")
        assert config.done_signals == []

    def test_debug_default_false(self):
        config = SessionConfig.create(topic="Test")
        assert config.debug is False

    def test_debug_enabled(self):
        config = SessionConfig.create(topic="Test", debug=True)
        assert config.debug is True

    def test_debug_serializes(self, tmp_storms):
        config = SessionConfig.create(
            topic="Debug test", debug=True, storms_dir=str(tmp_storms)
        )
        config.save()
        loaded = SessionConfig.load(config.session_id, storms_dir=str(tmp_storms))
        assert loaded.debug is True

    def test_create_with_deliverables(self, tmp_storms):
        config = SessionConfig.create(
            topic="Test",
            deliverables=["Doc A", "Doc B"],
            storms_dir=str(tmp_storms),
        )
        config.save()
        loaded = SessionConfig.load(config.session_id, storms_dir=str(tmp_storms))
        assert loaded.deliverables == ["Doc A", "Doc B"]

    def test_deliverables_default_empty(self):
        config = SessionConfig.create(topic="Test")
        assert config.deliverables == []
