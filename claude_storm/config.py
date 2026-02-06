"""Session configuration dataclass and JSON persistence."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
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
    stop_reason: str | None = None
    stop_error: str | None = None
    agent_watermarks: dict[str, dict] = field(default_factory=dict)

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
            started_at=datetime.now(UTC).isoformat(),
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
            data["done_signals"] = dict.fromkeys(data["done_signals"], "complete")
        # Ensure new agreement fields exist for legacy sessions
        data.setdefault("pending_proposals", [])
        data.setdefault("accepted_agreements", [])
        data.setdefault("stop_reason", None)
        data.setdefault("stop_error", None)
        data.setdefault("agent_watermarks", {})
        # Backfill summary on legacy agreement/proposal dicts
        for a in data["accepted_agreements"]:
            if "summary" not in a:
                first_line = a.get("content", "").strip().split("\n")[0][:120]
                a["summary"] = re.sub(r"^#+\s*", "", first_line)
        for p in data["pending_proposals"]:
            if "summary" not in p:
                first_line = p.get("content", "").strip().split("\n")[0][:120]
                p["summary"] = re.sub(r"^#+\s*", "", first_line)
        return cls(**data)

    def ensure_dirs(self) -> None:
        """Create all required subdirectories for the session."""
        d = self.session_dir()
        (d / "agent-a" / "memory").mkdir(parents=True, exist_ok=True)
        (d / "agent-b" / "memory").mkdir(parents=True, exist_ok=True)
        (d / "artifacts").mkdir(parents=True, exist_ok=True)
        (d / "agreements").mkdir(parents=True, exist_ok=True)

    def get_watermark(self, agent: str) -> dict:
        """Return the watermark for an agent, with defaults for missing keys.

        Args:
            agent: Which agent ('a' or 'b').

        Returns:
            Dict with memory_count, agreement_count, seen_proposal_ids,
            and last_turn.
        """
        defaults = {
            "memory_count": 0,
            "agreement_count": 0,
            "seen_proposal_ids": [],
            "last_turn": -1,
        }
        wm = self.agent_watermarks.get(agent, {})
        return {**defaults, **wm}

    def update_watermark(self, agent: str, memory_count: int) -> None:
        """Snapshot the current state into the agent's watermark.

        Args:
            agent: Which agent ('a' or 'b').
            memory_count: Number of memories the agent currently has.
        """
        self.agent_watermarks[agent] = {
            "memory_count": memory_count,
            "agreement_count": len(self.accepted_agreements),
            "seen_proposal_ids": [p["id"] for p in self.pending_proposals],
            "last_turn": self.current_turn,
        }

    def agent_label(self, agent: str) -> str:
        """Return a display label for an agent ('a' or 'b')."""
        if agent == "a":
            return self.role_a or "Agent A"
        return self.role_b or "Agent B"
