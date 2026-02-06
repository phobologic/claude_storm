"""Tests for session configuration."""

import json
import os
import stat

import pytest

from claude_storm.config import SessionConfig

# ---------- Security tests ----------


class TestSessionIdValidation:
    """Issue .4: Session ID path traversal prevention."""

    def test_load_rejects_path_traversal(self, tmp_storms):
        with pytest.raises(ValueError, match="Invalid session ID"):
            SessionConfig.load("../../../etc/passwd", storms_dir=str(tmp_storms))

    def test_load_rejects_slash_in_id(self, tmp_storms):
        with pytest.raises(ValueError, match="Invalid session ID"):
            SessionConfig.load("foo/bar", storms_dir=str(tmp_storms))

    def test_load_rejects_empty_id(self, tmp_storms):
        with pytest.raises(ValueError, match="Invalid session ID"):
            SessionConfig.load("", storms_dir=str(tmp_storms))

    def test_load_accepts_valid_hex_id(self, sample_config, tmp_storms):
        loaded = SessionConfig.load("test123", storms_dir=str(tmp_storms))
        assert loaded.session_id == "test123"

    def test_load_accepts_hyphens_and_underscores(self, tmp_storms):
        session_dir = tmp_storms / "my-session_01"
        session_dir.mkdir()
        data = {
            "session_id": "my-session_01",
            "topic": "Test",
            "storms_dir": str(tmp_storms),
        }
        (session_dir / "session.json").write_text(json.dumps(data))
        loaded = SessionConfig.load("my-session_01", storms_dir=str(tmp_storms))
        assert loaded.session_id == "my-session_01"


class TestLoadStripsUnknownFields:
    """Issue .6: Unknown fields from tampered JSON are stripped."""

    def test_unknown_keys_ignored(self, tmp_storms):
        session_dir = tmp_storms / "tampered01"
        session_dir.mkdir()
        data = {
            "session_id": "tampered01",
            "topic": "Test",
            "storms_dir": str(tmp_storms),
            "evil_field": "injected",
            "another_unknown": 42,
        }
        (session_dir / "session.json").write_text(json.dumps(data))
        loaded = SessionConfig.load("tampered01", storms_dir=str(tmp_storms))
        assert loaded.session_id == "tampered01"
        assert not hasattr(loaded, "evil_field")


class TestDirectoryPermissions:
    """Issue .9: Session directories restricted to owner-only."""

    def test_save_restricts_session_dir(self, tmp_storms):
        config = SessionConfig.create(topic="Perm test", storms_dir=str(tmp_storms))
        config.save()
        session_dir = config.session_dir()
        mode = stat.S_IMODE(os.stat(session_dir).st_mode)
        assert mode == 0o700

    def test_save_restricts_storms_dir(self, tmp_storms):
        config = SessionConfig.create(topic="Perm test", storms_dir=str(tmp_storms))
        config.save()
        mode = stat.S_IMODE(os.stat(tmp_storms).st_mode)
        assert mode == 0o700


class TestSessionConfig:
    def test_create_generates_ids(self):
        config = SessionConfig.create(topic="Test topic")
        assert len(config.session_id) == 12
        assert all(c in "0123456789abcdef" for c in config.session_id)
        assert len(config.claude_session_a) == 36  # UUID format
        assert len(config.claude_session_b) == 36
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
        assert config.done_signals == {}

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

    def test_reference_dirs_default_empty(self):
        config = SessionConfig.create(topic="Test")
        assert config.reference_dirs == []

    def test_create_with_reference_dirs(self, tmp_storms):
        config = SessionConfig.create(
            topic="Test",
            reference_dirs=["/some/path", "/other/path"],
            storms_dir=str(tmp_storms),
        )
        config.save()
        loaded = SessionConfig.load(config.session_id, storms_dir=str(tmp_storms))
        assert loaded.reference_dirs == ["/some/path", "/other/path"]

    def test_load_migrates_legacy_reference_dir(self, tmp_storms):
        """Old reference_dir key migrates to reference_dirs."""
        import json

        session_dir = tmp_storms / "legacy123"
        session_dir.mkdir()
        data = {
            "session_id": "legacy123",
            "topic": "Legacy",
            "reference_dir": "/old/path",
            "storms_dir": str(tmp_storms),
        }
        (session_dir / "session.json").write_text(json.dumps(data))
        loaded = SessionConfig.load("legacy123", storms_dir=str(tmp_storms))
        assert loaded.reference_dirs == ["/old/path"]

    def test_load_migrates_empty_reference_dir(self, tmp_storms):
        """Loading a session.json with empty reference_dir results in empty list."""
        import json

        session_dir = tmp_storms / "legacy456"
        session_dir.mkdir()
        data = {
            "session_id": "legacy456",
            "topic": "Legacy",
            "reference_dir": "",
            "storms_dir": str(tmp_storms),
        }
        (session_dir / "session.json").write_text(json.dumps(data))
        loaded = SessionConfig.load("legacy456", storms_dir=str(tmp_storms))
        assert loaded.reference_dirs == []

    def test_load_migrates_done_signals_list_to_dict(self, tmp_storms):
        """Loading a session.json with old list done_signals migrates to dict."""
        session_dir = tmp_storms / "legacy789"
        session_dir.mkdir()
        data = {
            "session_id": "legacy789",
            "topic": "Legacy",
            "done_signals": ["a"],
            "storms_dir": str(tmp_storms),
        }
        (session_dir / "session.json").write_text(json.dumps(data))
        loaded = SessionConfig.load("legacy789", storms_dir=str(tmp_storms))
        assert loaded.done_signals == {"a": "complete"}

    def test_load_migrates_empty_done_signals_list(self, tmp_storms):
        """Empty list done_signals migrates to empty dict."""
        session_dir = tmp_storms / "legacy000"
        session_dir.mkdir()
        data = {
            "session_id": "legacy000",
            "topic": "Legacy",
            "done_signals": [],
            "storms_dir": str(tmp_storms),
        }
        (session_dir / "session.json").write_text(json.dumps(data))
        loaded = SessionConfig.load("legacy000", storms_dir=str(tmp_storms))
        assert loaded.done_signals == {}
