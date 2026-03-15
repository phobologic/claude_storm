"""Directive parsing for agent response text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Known tag names (alternation used by both block and self-closing patterns)
# ---------------------------------------------------------------------------
_TAGS = "ARTIFACT|DONE|ASK_USER|PROPOSE|ACCEPT|REJECT|REVISE"

# ---------------------------------------------------------------------------
# Generic compiled regex patterns
# ---------------------------------------------------------------------------

# Matches block directives: [TAG attrs...]body[/TAG]
# The backreference \1 ensures the closing tag matches the opening tag.
# Example: [ARTIFACT filename="x" title="y"]content[/ARTIFACT]
_BLOCK_PATTERN = re.compile(
    rf"\[({_TAGS})((?:\s+[a-zA-Z_]+=(?:\"[^\"]*\"))*)\s*\]"  # open tag + attrs
    r"(.*?)"  # body (lazy)
    r"\[/\1\]",  # matching close tag
    re.DOTALL,
)

# Matches self-closing directives: [TAG attrs...]  (no close tag)
# Example: [ACCEPT id="a3f2"]  or  [DONE reason="complete"]
_SELF_CLOSING_PATTERN = re.compile(
    rf"\[({_TAGS})((?:\s+[a-zA-Z_]+=(?:\"[^\"]*\"))*)\s*\]",
    re.DOTALL,
)

# Extracts key="value" pairs from an attribute string.
# Example: ' filename="api.yaml" title="API Spec"'
# -> {filename: api.yaml, title: API Spec}
_ATTR_PATTERN = re.compile(r'([a-zA-Z_]+)="([^"]*)"')


# ---------------------------------------------------------------------------
# Public artifact container
# ---------------------------------------------------------------------------
class ArtifactDirective(NamedTuple):
    """A parsed ARTIFACT directive with write-mode metadata."""

    filename: str
    content: str
    action: str  # "overwrite" (default) or "append"


# ---------------------------------------------------------------------------
# Intermediate representation
# ---------------------------------------------------------------------------
@dataclass
class _RawDirective:
    """A single matched directive before dispatch."""

    tag: str
    attrs: dict[str, str]
    body: str  # empty string for self-closing tags
    span: tuple[int, int]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _parse_attrs(attr_string: str) -> dict[str, str]:
    """Extract key="value" pairs from a raw attribute string.

    Args:
        attr_string: The raw attribute portion of a directive tag,
            e.g. ' filename="api.yaml" title="API Spec"'.

    Returns:
        Dict mapping attribute names to their values.
    """
    return dict(_ATTR_PATTERN.findall(attr_string))


def _is_line_start(text: str, pos: int) -> bool:
    """Check whether *pos* is at the start of a line.

    Checks if *pos* is optionally preceded only by whitespace.

    Used to enforce the DONE directive's line-start requirement so that
    mid-sentence occurrences like ``aim for [DONE] sooner`` are ignored.

    Args:
        text: The full text being parsed.
        pos: The character index of the opening bracket.

    Returns:
        True if every character between the preceding newline (or start of
        string) and *pos* is whitespace.
    """
    line_start = text.rfind("\n", 0, pos) + 1  # 0 when no newline found
    return text[line_start:pos].strip() == ""


def _remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Remove character spans from *text* in a single pass.

    Spans may overlap; they are merged first so no region is double-removed.

    Args:
        text: The original text.
        spans: List of (start, end) index pairs to remove.

    Returns:
        Text with all span regions excised.
    """
    if not spans:
        return text
    # Sort and merge overlapping spans
    sorted_spans = sorted(spans)
    merged: list[tuple[int, int]] = [sorted_spans[0]]
    for start, end in sorted_spans[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    # Build result by keeping text between merged spans
    parts: list[str] = []
    cursor = 0
    for start, end in merged:
        parts.append(text[cursor:start])
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


# ---------------------------------------------------------------------------
# ParsedDirectives dataclass — public interface (unchanged)
# ---------------------------------------------------------------------------
@dataclass
class ParsedDirectives:
    """Typed container for parsed agent directives."""

    artifacts: list[ArtifactDirective] = field(default_factory=list)
    done: str | None = None
    ask_user: str | None = None
    proposals: list[tuple[str, str]] = field(default_factory=list)
    accepts: list[str] = field(default_factory=list)
    rejects: list[tuple[str, str]] = field(default_factory=list)
    revisions: list[tuple[str, str]] = field(default_factory=list)
    clean_text: str = ""


# ---------------------------------------------------------------------------
# Handler functions — one per directive tag
# ---------------------------------------------------------------------------
def _handle_artifact(directive: _RawDirective, result: ParsedDirectives) -> None:
    filename = directive.attrs.get("filename", "")
    if filename:
        action = directive.attrs.get("action", "overwrite")
        result.artifacts.append(
            ArtifactDirective(
                filename=filename, content=directive.body.strip(), action=action
            )
        )


def _handle_done(directive: _RawDirective, result: ParsedDirectives) -> None:
    result.done = directive.attrs.get("reason", "complete")


def _handle_ask_user(directive: _RawDirective, result: ParsedDirectives) -> None:
    result.ask_user = directive.body.strip()


def _handle_propose(directive: _RawDirective, result: ParsedDirectives) -> None:
    title = directive.attrs.get("title", "")
    result.proposals.append((title, directive.body.strip()))


def _handle_accept(directive: _RawDirective, result: ParsedDirectives) -> None:
    id_ = directive.attrs.get("id", "")
    if id_:
        result.accepts.append(id_)


def _handle_reject(directive: _RawDirective, result: ParsedDirectives) -> None:
    id_ = directive.attrs.get("id", "")
    reason = directive.attrs.get("reason", "")
    if id_:
        result.rejects.append((id_, reason))


def _handle_revise(directive: _RawDirective, result: ParsedDirectives) -> None:
    id_ = directive.attrs.get("id", "")
    body = directive.body.strip()
    if id_ and body:
        result.revisions.append((id_, body))


# Tag name -> handler mapping
_HANDLERS: dict[str, object] = {
    "ARTIFACT": _handle_artifact,
    "DONE": _handle_done,
    "ASK_USER": _handle_ask_user,
    "PROPOSE": _handle_propose,
    "ACCEPT": _handle_accept,
    "REJECT": _handle_reject,
    "REVISE": _handle_revise,
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def parse_directives(text: str) -> ParsedDirectives:
    """Parse structured directives from agent response text.

    Uses a two-pass approach:
      1. Find all block directives ([TAG ...]...[/TAG]) and record their spans.
      2. Find all self-closing directives ([TAG ...]), discarding any whose
         span overlaps a block match (since block opening tags also match the
         self-closing pattern).

    Args:
        text: Raw agent response text.

    Returns:
        ParsedDirectives with typed fields for each directive type.
    """
    result = ParsedDirectives(clean_text=text)
    directives: list[_RawDirective] = []
    block_spans: list[tuple[int, int]] = []

    # Pass 1: block directives
    for match in _BLOCK_PATTERN.finditer(text):
        tag = match.group(1)
        attrs = _parse_attrs(match.group(2))
        body = match.group(3)
        span = (match.start(), match.end())

        # DONE must be at line-start to avoid mid-sentence false positives
        if tag == "DONE" and not _is_line_start(text, match.start()):
            continue

        directives.append(_RawDirective(tag=tag, attrs=attrs, body=body, span=span))
        block_spans.append(span)

    # Pass 2: self-closing directives (discard overlaps with block spans)
    for match in _SELF_CLOSING_PATTERN.finditer(text):
        span = (match.start(), match.end())

        # Skip if this match overlaps any block directive span
        if any(bs <= span[0] < be for bs, be in block_spans):
            continue

        tag = match.group(1)
        attrs = _parse_attrs(match.group(2))

        # DONE must be at line-start
        if tag == "DONE" and not _is_line_start(text, match.start()):
            continue

        directives.append(_RawDirective(tag=tag, attrs=attrs, body="", span=span))

    # Dispatch to handlers and collect spans for cleaning
    all_spans: list[tuple[int, int]] = []
    for directive in directives:
        handler = _HANDLERS.get(directive.tag)
        if handler:
            handler(directive, result)
        all_spans.append(directive.span)

    # Clean text: remove all matched directive spans in one pass
    result.clean_text = _remove_spans(text, all_spans).strip()

    return result
