"""Shared test fixtures."""

from io import StringIO

import pytest
from rich.console import Console

from claude_storm.config import SessionConfig
from claude_storm.display import Display


@pytest.fixture
def tmp_storms(tmp_path):
    """Create a .storms/ temp directory and return its path."""
    storms = tmp_path / ".storms"
    storms.mkdir()
    return storms


@pytest.fixture
def make_config(tmp_storms):
    """Factory fixture for SessionConfig with test defaults and optional dirs."""

    def _factory(*, ensure_dirs=True, save=False, **overrides):
        defaults = {
            "session_id": "test",
            "topic": "Test topic",
            "goal": "Test goal",
            "role_a": "Architect",
            "role_b": "Critic",
            "claude_session_a": "sess-a-uuid",
            "claude_session_b": "sess-b-uuid",
            "max_turns": 10,
            "current_turn": 0,
            "auto_complete": False,
            "interactive": False,
            "model": "sonnet",
            "status": "active",
            "storms_dir": str(tmp_storms),
        }
        defaults.update(overrides)
        config = SessionConfig(**defaults)
        if ensure_dirs:
            config.ensure_dirs()
        if save:
            config.save()
        return config

    return _factory


@pytest.fixture
def sample_config(make_config):
    """Create and return a sample SessionConfig (saved to disk)."""
    return make_config(
        session_id="test123",
        started_at="2025-01-31T10:00:00+00:00",
        deliverables=[],
        reference_dirs=[],
        save=True,
    )


@pytest.fixture
def agent_a_dir(sample_config):
    """Return agent A's directory."""
    return sample_config.session_dir() / "agent-a"


@pytest.fixture
def agent_b_dir(sample_config):
    """Return agent B's directory."""
    return sample_config.session_dir() / "agent-b"


@pytest.fixture
def capture_display():
    """Create a Display that captures output to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, no_color=True, width=120)
    return Display(console=console), buf


@pytest.fixture
def mock_storms_dir(monkeypatch, tmp_storms):
    """Patch get_storms_dir to return tmp_storms."""
    monkeypatch.setattr("claude_storm.cli.get_storms_dir", lambda p: tmp_storms)
    return tmp_storms
