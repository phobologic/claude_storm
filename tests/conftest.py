"""Shared test fixtures."""

import pytest
from pathlib import Path

from claude_storm.config import SessionConfig


@pytest.fixture
def tmp_storms(tmp_path):
    """Create a .storms/ temp directory and return its path."""
    storms = tmp_path / ".storms"
    storms.mkdir()
    return storms


@pytest.fixture
def sample_config(tmp_storms):
    """Create and return a sample SessionConfig using .storms/ layout."""
    config = SessionConfig(
        session_id="test123",
        topic="Test topic",
        goal="Test goal",
        role_a="Architect",
        role_b="Critic",
        claude_session_a="sess-a-uuid",
        claude_session_b="sess-b-uuid",
        max_turns=10,
        auto_complete=False,
        interactive=False,
        model="sonnet",
        current_turn=0,
        started_at="2025-01-31T10:00:00+00:00",
        status="active",
        deliverables=[],
        reference_dirs=[],
        storms_dir=str(tmp_storms),
    )
    config.ensure_dirs()
    config.save()
    return config


@pytest.fixture
def agent_a_dir(sample_config):
    """Return agent A's directory."""
    return sample_config.session_dir() / "agent-a"


@pytest.fixture
def agent_b_dir(sample_config):
    """Return agent B's directory."""
    return sample_config.session_dir() / "agent-b"
