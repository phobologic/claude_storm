"""Directive parsing for agent response text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Module-level compiled regex patterns
_MEMORY_PATTERN = re.compile(
    r'\[MEMORY\s+title="([^"]+)"\s+tags="([^"]*)"\](.*?)\[/MEMORY\]',
    re.DOTALL,
)
_SEARCH_PATTERN = re.compile(r'\[MEMORY_SEARCH\s+query="([^"]+)"\]')
_ARTIFACT_PATTERN = re.compile(
    r'\[ARTIFACT\s+filename="([^"]+)"\](.*?)\[/ARTIFACT\]',
    re.DOTALL,
)
_DONE_PATTERN = re.compile(r'^\s*\[DONE(?:\s+reason="([^"]+)")?\]', re.MULTILINE)
_ASK_PATTERN = re.compile(r"\[ASK_USER\](.*?)\[/ASK_USER\]", re.DOTALL)
_PROPOSE_PATTERN = re.compile(
    r'\[PROPOSE\s+title="([^"]+)"\](.*?)\[/PROPOSE\]',
    re.DOTALL,
)
_ACCEPT_PATTERN = re.compile(r'\[ACCEPT\s+id="([^"]+)"\]')
_REJECT_PATTERN = re.compile(r'\[REJECT\s+id="([^"]+)"\s+reason="([^"]+)"\]')
_REVISE_PATTERN = re.compile(
    r'\[REVISE\s+id="([^"]+)"\](.*?)\[/REVISE\]',
    re.DOTALL,
)


@dataclass
class ParsedDirectives:
    """Typed container for parsed agent directives."""

    memories: list[tuple[str, list[str], str]] = field(default_factory=list)
    memory_searches: list[str] = field(default_factory=list)
    artifacts: list[tuple[str, str]] = field(default_factory=list)
    done: str | None = None
    ask_user: str | None = None
    proposals: list[tuple[str, str]] = field(default_factory=list)
    accepts: list[str] = field(default_factory=list)
    rejects: list[tuple[str, str]] = field(default_factory=list)
    revisions: list[tuple[str, str]] = field(default_factory=list)
    clean_text: str = ""


def parse_directives(text: str) -> ParsedDirectives:
    """Parse structured directives from agent response text.

    Args:
        text: Raw agent response text.

    Returns:
        ParsedDirectives with typed fields for each directive type.
    """
    result = ParsedDirectives(clean_text=text)

    # Parse [MEMORY title="..." tags="..."]content[/MEMORY]
    for match in _MEMORY_PATTERN.finditer(text):
        title = match.group(1)
        tags = [t.strip() for t in match.group(2).split(",") if t.strip()]
        content = match.group(3).strip()
        result.memories.append((title, tags, content))

    # Parse [MEMORY_SEARCH query="..."]
    for match in _SEARCH_PATTERN.finditer(text):
        result.memory_searches.append(match.group(1))

    # Parse [ARTIFACT filename="..."]content[/ARTIFACT]
    for match in _ARTIFACT_PATTERN.finditer(text):
        result.artifacts.append((match.group(1), match.group(2).strip()))

    # Parse [DONE] or [DONE reason="..."]
    done_match = _DONE_PATTERN.search(text)
    if done_match:
        result.done = done_match.group(1) or "complete"

    # Parse [ASK_USER]question[/ASK_USER]
    ask_match = _ASK_PATTERN.search(text)
    if ask_match:
        result.ask_user = ask_match.group(1).strip()

    # Parse [PROPOSE title="..."]content[/PROPOSE]
    for match in _PROPOSE_PATTERN.finditer(text):
        result.proposals.append((match.group(1), match.group(2).strip()))

    # Parse [ACCEPT id="..."]
    for match in _ACCEPT_PATTERN.finditer(text):
        result.accepts.append(match.group(1))

    # Parse [REJECT id="..." reason="..."]
    for match in _REJECT_PATTERN.finditer(text):
        result.rejects.append((match.group(1), match.group(2)))

    # Parse [REVISE id="..."]content[/REVISE]
    for match in _REVISE_PATTERN.finditer(text):
        result.revisions.append((match.group(1), match.group(2).strip()))

    # Clean text: remove all directives
    clean = text
    clean = _MEMORY_PATTERN.sub("", clean)
    clean = _SEARCH_PATTERN.sub("", clean)
    clean = _ARTIFACT_PATTERN.sub("", clean)
    clean = _DONE_PATTERN.sub("", clean)
    clean = _ASK_PATTERN.sub("", clean)
    clean = _PROPOSE_PATTERN.sub("", clean)
    clean = _ACCEPT_PATTERN.sub("", clean)
    clean = _REJECT_PATTERN.sub("", clean)
    clean = _REVISE_PATTERN.sub("", clean)
    result.clean_text = clean.strip()

    return result
