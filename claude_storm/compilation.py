"""Post-session deliverable compilation and summary generation."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from claude_storm.agents import invoke_agent
from claude_storm.agreements import format_agreements_for_compilation
from claude_storm.config import SessionConfig, slugify
from claude_storm.debug import (
    write_debug_phase_banner,
    write_debug_request,
    write_debug_response,
)
from claude_storm.display import DisplayProtocol
from claude_storm.prompts import build_deliverable_prompt, build_summary_prompt

MIN_WORD_OVERLAP_DIVISOR = 2


def find_matching_artifacts(
    artifacts_dir: Path, deliverable_name: str
) -> dict[str, str]:
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

    # Strip file extension before tokenizing to avoid "season_summarymd"
    deliv_base = re.sub(r"\.[a-zA-Z]{1,5}$", "", deliverable_name)
    # Normalize underscores/hyphens to spaces so "season_summary" → {season, summary}
    deliv_words = set(
        re.sub(r"[_\-]", " ", re.sub(r"[^\w\s-]", "", deliv_base)).lower().split()
    )
    if not deliv_words:
        return {}

    matches: dict[str, str] = {}
    for path in sorted(artifacts_dir.glob("draft-*.md")):
        # Only consider draft files (agent-produced) to avoid feeding compiled
        # output back into the compilation prompt on re-runs.
        stem = re.sub(r"^draft-", "", path.stem)
        stem_words = set(re.sub(r"[_\-]", " ", stem).lower().split())
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
    memories_text = (
        "\n\n---\n\n".join(memories_parts) if memories_parts else "(no memories)"
    )

    # Read conversation log
    conv_path = config.session_dir() / "conversation.md"
    conversation_text = (
        conv_path.read_text() if conv_path.exists() else "(no conversation)"
    )

    # Build agreements text for deliverable compilation
    agreements_text = format_agreements_for_compilation(config)

    artifacts_dir = config.session_dir() / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_phase_banner(debug_log, "COMPILATION PHASE")

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

        display.show_agent_stream_start(
            config,
            "a",
            label=f"Compiling: {deliverable}",
        )
        response = invoke_agent(
            config=config,
            agent="a",
            prompt=prompt,
            session_id=str(uuid4()),
            readonly=True,
            timeout=config.agent_timeout,
            on_delta=display.show_agent_stream_delta,
        )
        display.show_agent_stream_end(error=response.is_error, text=response.text)

        if config.debug:
            debug_log = config.session_dir() / "debug.log"
            write_debug_response(
                log_path=debug_log,
                cmd=response.cmd or [],
                raw_response=response.raw,
                directives={},
            )

        if not response.is_error:
            # Strip file extension before sanitizing to avoid "season_summarymd.md"
            base = re.sub(r"\.[a-zA-Z]{1,5}$", "", deliverable)
            safe_name = slugify(base, sep="_", max_len=0)
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

    agreements_text = format_agreements_for_compilation(config)

    conv_path = config.session_dir() / "conversation.md"
    conversation_text = conv_path.read_text() if conv_path.exists() else ""

    summary_prompt = build_summary_prompt(
        config,
        agreements_text=agreements_text,
        conversation_text=conversation_text,
    )

    if config.debug:
        debug_log = config.session_dir() / "debug.log"
        write_debug_phase_banner(debug_log, "SUMMARY PHASE")
        write_debug_request(
            log_path=debug_log,
            turn="summary",
            agent_label="Summarizer",
            system_prompt=None,
            turn_prompt=summary_prompt,
        )

    display.show_agent_stream_start(config, "a", label="Generating summary")
    response = invoke_agent(
        config=config,
        agent="a",
        prompt=summary_prompt,
        session_id=str(uuid4()),
        readonly=True,
        timeout=config.agent_timeout,
        on_delta=display.show_agent_stream_delta,
    )
    display.show_agent_stream_end(error=response.is_error, text=response.text)

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
