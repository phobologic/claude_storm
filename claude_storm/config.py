"""Session configuration dataclass and JSON persistence."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

# Allowed characters in session IDs (hex chars from uuid4().hex[:12])
_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# Paths that should never be granted as reference directories
_SENSITIVE_PATHS = frozenset(
    {
        "/",
        "/etc",
        "/var",
        "/root",
        "/private",
        "/private/etc",
        "/private/var",
    }
)


def _validate_reference_dir(path: str) -> bool:
    """Check whether a reference directory path is safe to use.

    Rejects paths that resolve to sensitive system directories.

    Args:
        path: The directory path to validate.

    Returns:
        True if the path is safe, False otherwise.
    """
    try:
        resolved = str(Path(path).resolve())
    except (OSError, ValueError):
        return False
    return resolved not in _SENSITIVE_PATHS


def validate_reference_dirs(dirs: list[str]) -> list[str]:
    """Resolve and validate a list of reference directory paths.

    Each path is resolved to an absolute path and checked for existence.

    Args:
        dirs: List of directory path strings to validate.

    Returns:
        List of resolved absolute path strings.

    Raises:
        ValueError: If any directory does not exist.
    """
    resolved: list[str] = []
    for ref in dirs:
        ref_path = Path(ref).resolve()
        if not ref_path.is_dir():
            raise ValueError(f"Reference directory not found: {ref_path}")
        resolved.append(str(ref_path))
    return resolved


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
    agent_timeout: int = 600
    truncate_conversation: bool = True
    pending_proposals: list[dict] = field(default_factory=list)
    accepted_agreements: list[dict] = field(default_factory=list)
    storms_dir: str = ""
    stop_reason: str | None = None
    stop_error: str | None = None
    agent_watermarks: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._failed_ref_indices: set[int] = set()

    def ref_symlink_paths(self) -> dict[int, Path]:
        """Return a mapping of 1-based index to symlink path for each reference dir.

        Returns:
            Dict mapping index to ``session_dir/refs/ref_<index>`` for each
            entry in ``reference_dirs``.
        """
        refs_dir = self.session_dir() / "refs"
        return {
            i: refs_dir / f"ref_{i}" for i in range(1, len(self.reference_dirs) + 1)
        }

    def ref_symlink_failed(self, index: int) -> bool:
        """Return whether symlink creation failed for the given 1-based index.

        Args:
            index: The 1-based reference directory index.

        Returns:
            True if the symlink for this index failed to create.
        """
        return index in self._failed_ref_indices

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
        agent_timeout: int = 600,
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
            agent_timeout=agent_timeout,
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
        """Save config to session directory as session.json.

        Restricts the storms parent directory and session directory
        to owner-only access (mode 0o700) to protect sensitive session data.
        """
        d = self.session_dir()
        d.mkdir(parents=True, exist_ok=True)
        # Restrict permissions on the storms parent dir and session dir
        if d.parent.exists():
            d.parent.chmod(0o700)
        d.chmod(0o700)
        (d / "session.json").write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, session_id: str, storms_dir: str = "") -> SessionConfig:
        """Load config from a session directory.

        Args:
            session_id: The session ID to load.
            storms_dir: Base directory containing sessions. Falls back to
                        "sessions" for legacy compatibility.

        Raises:
            ValueError: If session_id contains invalid characters.
        """
        if not _SESSION_ID_RE.match(session_id):
            raise ValueError(
                f"Invalid session ID: {session_id!r} "
                "(must contain only alphanumeric, hyphens, underscores)"
            )
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
        # Strip unknown keys to prevent unexpected fields from tampered JSON
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**data)

    def ensure_dirs(self) -> None:
        """Create all required subdirectories for the session.

        Also creates symlinks in ``refs/`` for each reference directory,
        giving agents short, LLM-friendly paths to use instead of the
        raw (potentially complex) directory paths.
        """
        d = self.session_dir()
        (d / "agent-a" / "memory").mkdir(parents=True, exist_ok=True)
        (d / "agent-b" / "memory").mkdir(parents=True, exist_ok=True)
        (d / "artifacts").mkdir(parents=True, exist_ok=True)
        (d / "agreements").mkdir(parents=True, exist_ok=True)
        self._create_ref_symlinks()

    def _create_ref_symlinks(self) -> None:
        """Create symlinks in ``refs/`` pointing to each reference directory.

        Symlinks are named ``ref_1``, ``ref_2``, etc.  Existing correct
        symlinks are left alone (idempotent on resume).  Broken or
        mis-targeted symlinks are removed and recreated.  Failures are
        logged as warnings and tracked in ``_failed_ref_indices`` so that
        downstream code can fall back to raw paths.

        After creation, stale ``ref_N`` symlinks left from a previous run
        with more reference dirs are removed.
        """
        self._failed_ref_indices.clear()
        refs_dir = self.session_dir() / "refs"

        if self.reference_dirs:
            symlink_paths = self.ref_symlink_paths()
            refs_dir.mkdir(parents=True, exist_ok=True)
            for i, raw_path in enumerate(self.reference_dirs, start=1):
                if not _validate_reference_dir(raw_path):
                    logger.warning(
                        "Skipping sensitive reference dir %s (index %d)", raw_path, i
                    )
                    self._failed_ref_indices.add(i)
                    continue
                link = symlink_paths[i]
                target = Path(raw_path)
                if not target.is_dir():
                    logger.warning(
                        "Reference dir does not exist: %s (index %d)", raw_path, i
                    )
                    self._failed_ref_indices.add(i)
                    continue
                try:
                    if link.is_symlink():
                        if link.resolve() == target.resolve():
                            continue
                        # Broken or mis-targeted — remove and recreate
                        link.unlink()
                    link.symlink_to(target)
                except OSError:
                    logger.warning(
                        "Failed to create ref symlink %s -> %s",
                        link,
                        target,
                        exc_info=True,
                    )
                    self._failed_ref_indices.add(i)

        # Remove stale ref_N symlinks from a previous run with more dirs.
        if refs_dir.is_dir():
            n = len(self.reference_dirs)
            for entry in refs_dir.iterdir():
                if not entry.name.startswith("ref_"):
                    continue
                try:
                    idx = int(entry.name.split("_", 1)[1])
                except (ValueError, IndexError):
                    continue
                if idx > n:
                    try:
                        entry.unlink()
                    except OSError:
                        logger.warning(
                            "Failed to remove stale ref symlink %s",
                            entry,
                            exc_info=True,
                        )

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
        """Return a display label for an agent ('a' or 'b').

        When the role is a multi-line string, only the first line is used
        as the label (the remaining lines are treated as description).
        """
        role = self.role_a if agent == "a" else self.role_b
        if role:
            return role.strip().splitlines()[0].strip()
        return "Agent A" if agent == "a" else "Agent B"
