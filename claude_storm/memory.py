"""Per-agent markdown memory filesystem with JSON index."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from claude_storm.config import slugify


def _index_path(agent_dir: Path) -> Path:
    """Return path to the agent's memory index file."""
    return agent_dir / "memory" / "_index.json"


def _load_index(agent_dir: Path) -> list[dict]:
    """Load the memory index, returning empty list if not found."""
    path = _index_path(agent_dir)
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_index(agent_dir: Path, index: list[dict]) -> None:
    """Write the memory index to disk."""
    path = _index_path(agent_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2) + "\n")


def _slugify(title: str) -> str:
    """Convert a title to a filename-safe slug."""
    return slugify(title)


def save_memory(agent_dir: Path, title: str, tags: list[str], content: str) -> str:
    """Save a memory note and update the index.

    Args:
        agent_dir: Path to the agent's directory (e.g., sessions/abc/agent-a).
        title: Title of the memory note.
        tags: List of tag strings.
        content: Markdown content of the note.

    Returns:
        The filename of the saved note.

    Raises:
        ValueError: If the generated filename contains path separators.
    """
    index = _load_index(agent_dir)
    num = len(index) + 1
    slug = _slugify(title)
    filename = f"{num:03d}-{slug}.md"
    # Explicit safety check: reject filenames with path separators
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError(f"Unsafe memory filename: {filename!r}")
    mem_dir = agent_dir / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / filename).write_text(content.strip() + "\n")

    # Build summary from first line of content
    first_line = content.strip().split("\n")[0][:120]
    summary = re.sub(r"^#+\s*", "", first_line)

    index.append(
        {
            "filename": filename,
            "title": title,
            "tags": tags,
            "summary": summary,
            "updated": datetime.now(UTC).isoformat(),
        }
    )
    _save_index(agent_dir, index)
    return filename


def get_memory_index(agent_dir: Path) -> list[dict]:
    """Return the memory index for an agent."""
    return _load_index(agent_dir)


def get_recent_memories(agent_dir: Path, n: int = 3) -> list[tuple[str, str]]:
    """Return the last N memory notes as (title, content) tuples.

    Args:
        agent_dir: Path to the agent's directory.
        n: Number of recent memories to return.

    Returns:
        List of (title, content) tuples, most recent first.
    """
    index = _load_index(agent_dir)
    recent = index[-n:] if index else []
    recent.reverse()
    results = []
    mem_dir = agent_dir / "memory"
    for entry in recent:
        filename = entry["filename"]
        if "/" in filename or "\\" in filename or ".." in filename:
            continue
        path = mem_dir / filename
        if path.exists() and path.resolve().is_relative_to(mem_dir.resolve()):
            results.append((entry["title"], path.read_text()))
    return results


def search_memory(agent_dir: Path, query: str) -> list[tuple[str, str]]:
    """Search memories by keyword matching on title, tags, and summary.

    Args:
        agent_dir: Path to the agent's directory.
        query: Search query string.

    Returns:
        List of (title, content) tuples for matching memories.
    """
    index = _load_index(agent_dir)
    query_lower = query.lower()
    terms = query_lower.split()
    results = []
    mem_dir = agent_dir / "memory"
    for entry in index:
        searchable = " ".join(
            [entry["title"], " ".join(entry["tags"]), entry.get("summary", "")]
        ).lower()
        if any(term in searchable for term in terms):
            filename = entry["filename"]
            if "/" in filename or "\\" in filename or ".." in filename:
                continue
            path = mem_dir / filename
            if path.exists() and path.resolve().is_relative_to(mem_dir.resolve()):
                results.append((entry["title"], path.read_text()))
    return results


def format_memory_index(agent_dir: Path, since_count: int = 0) -> str:
    """Format the memory index for inclusion in a prompt.

    Args:
        agent_dir: Path to the agent's directory.
        since_count: Number of memories the agent has already seen.
            0 means first turn (full index). When positive, only new
            entries are listed.

    Returns:
        A formatted string listing memories.
    """
    index = _load_index(agent_dir)
    if not index:
        return "You have no saved notes."

    total = len(index)
    new_count = max(0, total - since_count)

    if since_count == 0:
        # First turn: full index
        lines = [f"You have {total} saved note(s):"]
        entries_to_show = index
    elif new_count > 0:
        lines = [f"You have {total} saved note(s) ({new_count} new):"]
        entries_to_show = index[since_count:]
    else:
        return f"You have {total} saved note(s) (no new entries)."

    for entry in entries_to_show:
        tags_str = ", ".join(entry["tags"]) if entry["tags"] else "none"
        lines.append(f'- "{entry["title"]}" [{tags_str}]')
    return "\n".join(lines)


def format_recent_memories(agent_dir: Path, n: int = 3, since_count: int = 0) -> str:
    """Format recent memories for inclusion in a prompt.

    Args:
        agent_dir: Path to the agent's directory.
        n: Number of recent memories.
        since_count: Number of memories the agent has already seen.
            When positive and no new memories exist, returns empty string.
            When positive with new memories, shows only memories after
            the watermark position.

    Returns:
        Formatted string with recent memory contents.
    """
    index = _load_index(agent_dir)
    if not index:
        return ""

    if since_count > 0 and len(index) <= since_count:
        # No new memories since last watermark
        return ""

    if since_count > 0:
        # Only show memories added after the watermark
        new_entries = index[since_count:]
        new_entries = list(reversed(new_entries))
    else:
        # First turn: show last n
        new_entries = index[-n:] if index else []
        new_entries = list(reversed(new_entries))

    parts = []
    mem_dir = agent_dir / "memory"
    for entry in new_entries:
        filename = entry["filename"]
        if "/" in filename or "\\" in filename or ".." in filename:
            continue
        path = mem_dir / filename
        if path.exists() and path.resolve().is_relative_to(mem_dir.resolve()):
            parts.append(f"## {entry['title']}\n{path.read_text().strip()}")
    return "\n\n".join(parts)


def format_search_results(agent_dir: Path, query: str) -> str:
    """Format search results for inclusion in a prompt.

    Args:
        agent_dir: Path to the agent's directory.
        query: Search query.

    Returns:
        Formatted string with search result contents.
    """
    results = search_memory(agent_dir, query)
    if not results:
        return f'No results found for "{query}".'
    parts = [f'Results for "{query}":']
    for title, content in results:
        parts.append(f"## {title}\n{content.strip()}")
    return "\n\n".join(parts)
