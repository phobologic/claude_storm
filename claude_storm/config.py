"""Session configuration dataclass and JSON persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass
class SessionConfig:
    """Configuration for a brainstorming session."""

    session_id: str
    topic: str
    goal: str = ""
    role_a: str | None = None
    role_b: str | None = None
    claude_session_a: str = ""
    claude_session_b: str = ""
    max_turns: int = 20
    max_minutes: int | None = None
    auto_complete: bool = False
    interactive: bool = False
    debug: bool = False
    model: str = "sonnet"
    current_turn: int = 0
    started_at: str = ""
    status: str = "active"
    done_signals: dict[str, str] = field(default_factory=dict)
    deliverables: list[str] = field(default_factory=list)
    reference_dirs: list[str] = field(default_factory=list)
    truncate_conversation: bool = True
    pending_proposals: list[dict] = field(default_factory=list)
    accepted_agreements: list[dict] = field(default_factory=list)
    storms_dir: str = ""

    @classmethod
    def create(
        cls,
        topic: str,
        goal: str = "",
        role_a: str | None = None,
        role_b: str | None = None,
        max_turns: int = 20,
        max_minutes: int | None = None,
        auto_complete: bool = False,
        interactive: bool = False,
        debug: bool = False,
        model: str = "sonnet",
        deliverables: list[str] | None = None,
        reference_dirs: list[str] | None = None,
        truncate_conversation: bool = True,
        storms_dir: str = "",
    ) -> SessionConfig:
        """Create a new session config with generated IDs."""
        return cls(
            session_id=uuid4().hex[:12],
            topic=topic,
            goal=goal,
            role_a=role_a,
            role_b=role_b,
            claude_session_a=str(uuid4()),
            claude_session_b=str(uuid4()),
            max_turns=max_turns,
            max_minutes=max_minutes,
            auto_complete=auto_complete,
            interactive=interactive,
            debug=debug,
            model=model,
            started_at=datetime.now(timezone.utc).isoformat(),
            status="active",
            deliverables=deliverables or [],
            reference_dirs=reference_dirs or [],
            truncate_conversation=truncate_conversation,
            storms_dir=storms_dir,
        )

    def session_dir(self) -> Path:
        """Return the session directory path."""
        if self.storms_dir:
            return Path(self.storms_dir) / self.session_id
        # Fallback for legacy sessions
        return Path("sessions") / self.session_id

    def save(self) -> None:
        """Save config to session directory as session.json."""
        d = self.session_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / "session.json").write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, session_id: str, storms_dir: str = "") -> SessionConfig:
        """Load config from a session directory.

        Args:
            session_id: The session ID to load.
            storms_dir: Base directory containing sessions. Falls back to
                        "sessions" for legacy compatibility.
        """
        if storms_dir:
            path = Path(storms_dir) / session_id / "session.json"
        else:
            path = Path("sessions") / session_id / "session.json"
        data = json.loads(path.read_text())
        # Migrate legacy reference_dir → reference_dirs
        if "reference_dir" in data:
            old = data.pop("reference_dir")
            if old and "reference_dirs" not in data:
                data["reference_dirs"] = [old]
        # Migrate legacy done_signals list → dict
        if isinstance(data.get("done_signals"), list):
            data["done_signals"] = {a: "complete" for a in data["done_signals"]}
        # Ensure new agreement fields exist for legacy sessions
        data.setdefault("pending_proposals", [])
        data.setdefault("accepted_agreements", [])
        return cls(**data)

    def ensure_dirs(self) -> None:
        """Create all required subdirectories for the session."""
        d = self.session_dir()
        (d / "agent-a" / "memory").mkdir(parents=True, exist_ok=True)
        (d / "agent-b" / "memory").mkdir(parents=True, exist_ok=True)
        (d / "artifacts").mkdir(parents=True, exist_ok=True)

    def agent_label(self, agent: str) -> str:
        """Return a display label for an agent ('a' or 'b')."""
        if agent == "a":
            return self.role_a or "Agent A"
        return self.role_b or "Agent B"
