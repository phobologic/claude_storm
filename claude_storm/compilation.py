"""Post-session deliverable compilation and summary generation."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from claude_storm.agents import invoke_agent
from claude_storm.agreements import format_agreements_for_prompt
from claude_storm.config import SessionConfig
from claude_storm.debug import write_debug_request, write_debug_response
from claude_storm.display import DisplayProtocol
from claude_storm.prompts import build_deliverable_prompt, build_summary_prompt

MIN_WORD_OVERLAP_DIVISOR = 2


def find_matching_artifacts(artifacts_dir: Path, deliverable_name: str) -> dict[str, str]:
    """Find existing artifact files whose names fuzzy-match a deliverable.

    Compares normalized words from the deliverable name against each artifact
    filename. A file matches if at least half the deliverable's words appear
    in the filename.

    Args:
        artifacts_dir: Path to the artifacts directory.
        deliverable_name: Name of the deliverable to match.

    Returns:
        Dict of filename -> file content for matching artifacts.
    """
    if not artifacts_dir.exists():
        return {}

    # Normalize deliverable name into lowercase tokens
    deliv_words = set(re.sub(r'[^\w\s]', '', deliverable_name).lower().split())
    if not deliv_words:
        return {}

    matches: dict[str, str] = {}
    for path in sorted(artifacts_dir.glob("*.md")):
        stem_words = set(re.sub(r'[_\-]', ' ', path.stem).lower().split())
        overlap = deliv_words & stem_words
        if len(overlap) >= max(1, len(deliv_words) // MIN_WORD_OVERLAP_DIVISOR):
            matches[path.name] = path.read_text()

    return matches


def compile_deliverables(config: SessionConfig, display: DisplayProtocol) -> None:
    """Compile each deliverable from session materials into artifact files.

    Args:
        config: The session configuration.
        display: The display manager.
    """
    if not config.deliverables:
        return

    # Gather all memory files from both agents
    memories_parts: list[str] = []
    for agent in ("a", "b"):
        mem_dir = config.session_dir() / f"agent-{agent}" / "memory"
        if mem_dir.exists():
            for md_file in sorted(mem_dir.glob("*.md")):
                label = config.agent_label(agent)
                memories_parts.append(
                    f"### {label}: {md_file.stem}\n\n{md_file.read_text()}"
                )
    memories_text = "\n\n---\n\n".join(memories_parts) if memories_parts else "(no memories)"

    # Read conversation log
    conv_path = config.session_dir() / "conversation.md"
    conversation_text = conv_path.read_text() if conv_path.exists() else "(no conversation)"

    # Build agreements text for deliverable compilation
    agreements_text = format_agreements_for_prompt(config, "a")

    artifacts_dir = config.session_dir() / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    for deliverable in config.deliverables:
        display.show_deliverable_compile(deliverable)

        # Find existing artifact files that match this deliverable
        existing_artifacts = find_matching_artifacts(artifacts_dir, deliverable)

        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name=deliverable,
            memories_text=memories_text,
            conversation_text=conversation_text,
            agreements_text=agreements_text,
            existing_artifacts=existing_artifacts or None,
        )

        if config.debug:
            debug_log = config.session_dir() / "debug.log"
            write_debug_request(
                log_path=debug_log,
                turn=f"deliverable:{deliverable}",
                agent_label="Compiler",
                system_prompt=None,
                turn_prompt=prompt,
            )

        with display.thinking_status(f"Compiling: {deliverable}"):
            response = invoke_agent(
                config=config,
                agent="a",
                prompt=prompt,
                session_id=str(uuid4()),
                readonly=True,
            )

        if config.debug:
            debug_log = config.session_dir() / "debug.log"
            write_debug_response(
                log_path=debug_log,
                cmd=response.cmd or [],
                raw_response=response.raw,
                directives={},
            )

        if not response.is_error:
            # Sanitize filename
            safe_name = re.sub(r'[^\w\s-]', '', deliverable).strip()
            safe_name = re.sub(r'[\s]+', '_', safe_name).lower()
            artifact_path = artifacts_dir / f"{safe_name}.md"
            artifact_path.write_text(response.text + "\n")
            display.show_artifact_save(f"{safe_name}.md")
        else:
            display.show_error(f"Failed to compile deliverable: {deliverable}")


def generate_summary(config: SessionConfig, display: DisplayProtocol) -> None:
    """Generate and save a session summary.

    Args:
        config: The session configuration.
        display: The display manager.
    """
    display.show_status("Generating session summary...")
    summary_prompt = build_summary_prompt(config)

    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_request(
            log_path=debug_log,
            turn="summary",
            agent_label="Summarizer",
            system_prompt=None,
            turn_prompt=summary_prompt,
        )

    with display.thinking_status("Generating summary"):
        response = invoke_agent(
            config=config,
            agent="a",
            prompt=summary_prompt,
            session_id=str(uuid4()),
            readonly=True,
        )

    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_response(
            log_path=debug_log,
            cmd=response.cmd or [],
            raw_response=response.raw,
            directives={},
        )

    if not response.is_error:
        summary_path = config.session_dir() / "summary.md"
        summary_path.write_text(response.text + "\n")
        display.show_summary(response.text)
    else:
        display.show_error("Failed to generate session summary")
