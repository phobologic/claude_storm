"""Tests for session configuration."""

import json
import logging
import os
import stat
from pathlib import Path

import pytest

from claude_storm.config import SessionConfig, _validate_reference_dir

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


class TestRefSymlinks:
    """Symlinks in refs/ for LLM-friendly reference directory access."""

    def test_ensure_dirs_creates_ref_symlinks(self, tmp_storms, tmp_path):
        """ensure_dirs creates refs/ref_N symlinks for each reference dir."""
        ref_a = tmp_path / "notes"
        ref_b = tmp_path / "iCloud~md~obsidian" / "docs"
        ref_a.mkdir()
        ref_b.mkdir(parents=True)
        config = SessionConfig(
            session_id="refsym",
            topic="Test",
            reference_dirs=[str(ref_a), str(ref_b)],
            storms_dir=str(tmp_storms),
        )
        config.session_dir().mkdir(parents=True, exist_ok=True)
        config.ensure_dirs()
        refs_dir = config.session_dir() / "refs"
        assert (refs_dir / "ref_1").is_symlink()
        assert (refs_dir / "ref_2").is_symlink()
        assert (refs_dir / "ref_1").resolve() == ref_a.resolve()
        assert (refs_dir / "ref_2").resolve() == ref_b.resolve()

    def test_ensure_dirs_idempotent(self, tmp_storms, tmp_path):
        """Calling ensure_dirs twice leaves correct symlinks intact."""
        ref = tmp_path / "data"
        ref.mkdir()
        config = SessionConfig(
            session_id="refidemp",
            topic="Test",
            reference_dirs=[str(ref)],
            storms_dir=str(tmp_storms),
        )
        config.session_dir().mkdir(parents=True, exist_ok=True)
        config.ensure_dirs()
        config.ensure_dirs()  # second call
        link = config.session_dir() / "refs" / "ref_1"
        assert link.is_symlink()
        assert link.resolve() == ref.resolve()

    def test_ensure_dirs_replaces_broken_symlink(self, tmp_storms, tmp_path):
        """A broken symlink is replaced with a correct one."""
        ref = tmp_path / "actual"
        ref.mkdir()
        config = SessionConfig(
            session_id="refbroken",
            topic="Test",
            reference_dirs=[str(ref)],
            storms_dir=str(tmp_storms),
        )
        config.session_dir().mkdir(parents=True, exist_ok=True)
        # Create a broken symlink manually
        refs_dir = config.session_dir() / "refs"
        refs_dir.mkdir()
        broken = refs_dir / "ref_1"
        broken.symlink_to(tmp_path / "nonexistent")
        assert broken.is_symlink()
        assert not broken.exists()  # broken
        config.ensure_dirs()
        assert broken.is_symlink()
        assert broken.resolve() == ref.resolve()

    def test_ensure_dirs_no_refs_without_reference_dirs(self, tmp_storms):
        """No refs/ directory is created when there are no reference dirs."""
        config = SessionConfig(
            session_id="noref",
            topic="Test",
            reference_dirs=[],
            storms_dir=str(tmp_storms),
        )
        config.session_dir().mkdir(parents=True, exist_ok=True)
        config.ensure_dirs()
        assert not (config.session_dir() / "refs").exists()


class TestRefSymlinkPaths:
    """ref_symlink_paths() returns correct mapping."""

    def test_returns_mapping(self, tmp_storms, tmp_path):
        ref_a = tmp_path / "notes"
        ref_b = tmp_path / "docs"
        ref_a.mkdir()
        ref_b.mkdir()
        config = SessionConfig(
            session_id="symmap",
            topic="Test",
            reference_dirs=[str(ref_a), str(ref_b)],
            storms_dir=str(tmp_storms),
        )
        paths = config.ref_symlink_paths()
        assert set(paths.keys()) == {1, 2}
        assert paths[1] == config.session_dir() / "refs" / "ref_1"
        assert paths[2] == config.session_dir() / "refs" / "ref_2"

    def test_empty_when_no_refs(self, tmp_storms):
        config = SessionConfig(
            session_id="nomap",
            topic="Test",
            reference_dirs=[],
            storms_dir=str(tmp_storms),
        )
        assert config.ref_symlink_paths() == {}


class TestRefSymlinkFailureTracking:
    """OSError logging and failure tracking in _create_ref_symlinks."""

    def test_oserror_logged_with_exc_info(self, tmp_storms, tmp_path, caplog):
        """OSError during symlink creation is logged with exc_info."""
        ref = tmp_path / "data"
        ref.mkdir()
        config = SessionConfig(
            session_id="errlog",
            topic="Test",
            reference_dirs=[str(ref)],
            storms_dir=str(tmp_storms),
        )
        config.session_dir().mkdir(parents=True, exist_ok=True)
        refs_dir = config.session_dir() / "refs"
        refs_dir.mkdir()
        # Create a regular file where the symlink would go to force OSError
        (refs_dir / "ref_1").write_text("blocking file")

        with caplog.at_level(logging.WARNING, logger="claude_storm.config"):
            config._create_ref_symlinks()

        assert "Failed to create ref symlink" in caplog.text
        assert config.ref_symlink_failed(1)

    def test_failure_cleared_on_retry(self, tmp_storms, tmp_path):
        """_failed_ref_indices is cleared on each call (idempotent on resume)."""
        ref = tmp_path / "data"
        ref.mkdir()
        config = SessionConfig(
            session_id="retry",
            topic="Test",
            reference_dirs=[str(ref)],
            storms_dir=str(tmp_storms),
        )
        config.session_dir().mkdir(parents=True, exist_ok=True)
        refs_dir = config.session_dir() / "refs"
        refs_dir.mkdir()

        # First call: block the symlink to cause failure
        (refs_dir / "ref_1").write_text("blocker")
        config._create_ref_symlinks()
        assert config.ref_symlink_failed(1)

        # Remove the blocker, retry should succeed and clear failures
        (refs_dir / "ref_1").unlink()
        config._create_ref_symlinks()
        assert not config.ref_symlink_failed(1)

    def test_sensitive_path_skipped(self, tmp_storms, caplog):
        """Sensitive reference dirs are skipped and tracked as failed."""
        config = SessionConfig(
            session_id="sensitive",
            topic="Test",
            reference_dirs=["/etc"],
            storms_dir=str(tmp_storms),
        )
        config.session_dir().mkdir(parents=True, exist_ok=True)

        with caplog.at_level(logging.WARNING, logger="claude_storm.config"):
            config._create_ref_symlinks()

        assert "Skipping sensitive reference dir" in caplog.text
        assert config.ref_symlink_failed(1)
        # No symlink should have been created
        refs_dir = config.session_dir() / "refs"
        assert not (refs_dir / "ref_1").exists()


class TestRefSymlinkStaleCleanup:
    """Stale symlink cleanup when reference_dirs shrinks on resume."""

    def test_stale_symlinks_removed_on_resume_with_fewer_refs(
        self, tmp_storms, tmp_path
    ):
        """Resuming with fewer reference dirs removes stale ref_N symlinks."""
        refs = [tmp_path / f"dir{i}" for i in range(1, 4)]
        for d in refs:
            d.mkdir()

        config = SessionConfig(
            session_id="stale",
            topic="Test",
            reference_dirs=[str(d) for d in refs],
            storms_dir=str(tmp_storms),
        )
        config.ensure_dirs()
        refs_dir = config.session_dir() / "refs"
        assert (refs_dir / "ref_1").is_symlink()
        assert (refs_dir / "ref_2").is_symlink()
        assert (refs_dir / "ref_3").is_symlink()

        # Resume with only 1 reference dir
        config.reference_dirs = [str(refs[0])]
        config._create_ref_symlinks()

        assert (refs_dir / "ref_1").is_symlink()
        assert not (refs_dir / "ref_2").exists()
        assert not (refs_dir / "ref_3").exists()

    def test_nonexistent_target_skipped_with_warning(
        self, tmp_storms, tmp_path, caplog
    ):
        """A reference dir that doesn't exist on disk is skipped with warning."""
        missing = tmp_path / "gone"
        config = SessionConfig(
            session_id="nodir",
            topic="Test",
            reference_dirs=[str(missing)],
            storms_dir=str(tmp_storms),
        )
        config.session_dir().mkdir(parents=True, exist_ok=True)

        with caplog.at_level(logging.WARNING, logger="claude_storm.config"):
            config._create_ref_symlinks()

        assert "Reference dir does not exist" in caplog.text
        assert config.ref_symlink_failed(1)
        link = config.session_dir() / "refs" / "ref_1"
        assert not link.exists()
        assert not link.is_symlink()

    def test_oserror_during_stale_removal_logged(
        self, tmp_storms, tmp_path, caplog, monkeypatch
    ):
        """OSError during stale symlink removal is logged, not raised."""
        ref = tmp_path / "data"
        ref.mkdir()
        config = SessionConfig(
            session_id="stalerr",
            topic="Test",
            reference_dirs=[str(ref)],
            storms_dir=str(tmp_storms),
        )
        config.ensure_dirs()

        # Manually create a stale ref_2 symlink
        refs_dir = config.session_dir() / "refs"
        stale = refs_dir / "ref_2"
        stale.symlink_to(ref)

        original_unlink = Path.unlink

        def _failing_unlink(self, *args, **kwargs):
            if self.name == "ref_2":
                raise OSError("permission denied")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", _failing_unlink)

        with caplog.at_level(logging.WARNING, logger="claude_storm.config"):
            config._create_ref_symlinks()

        assert "Failed to remove stale ref symlink" in caplog.text
        assert stale.is_symlink()


class TestValidateReferenceDirConfig:
    """_validate_reference_dir moved to config module."""

    def test_rejects_root(self):
        assert _validate_reference_dir("/") is False

    def test_accepts_normal_path(self):
        assert _validate_reference_dir("/some/ref/dir") is True
