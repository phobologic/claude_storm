# Claude Storm

A dual-agent brainstorming system that orchestrates two Claude Code CLI instances in strict alternating turns. Each agent maintains a persistent Claude session and has access to a markdown-based memory filesystem for long-term notes.

## Installation

```bash
uv sync
```

## Quick Start

```bash
# One-off brainstorming session
uv run storm start "Design a REST API for a todo app" --max-turns 4

# Project-based workflow (recommended)
uv run storm init --topic "Design a distributed task queue"
# Edit storm.toml to add roles, goal, deliverables...
uv run storm start
```

## Project Configuration

Run `storm init` to create a `storm.toml` in your project directory:

```toml
[session]
topic = """
Design a distributed task queue system that handles
job prioritization, retry logic, and horizontal scaling.
"""

goal = """
Produce a detailed architecture document covering core
data model, queue topology, and failure handling.
"""

role_a = """
Systems Architect - Deep experience with distributed systems.
Favors pragmatic, battle-tested approaches.
"""

role_b = """
Reliability Engineer - Focuses on failure modes, observability,
and operational concerns.
"""

deliverables = [
    "Architecture overview document",
    "Data model specification",
    "Failure handling policy",
]

# Optional: directories of notes/docs agents can read for context
# reference_dirs = ["/path/to/research/notes"]

[options]
max_turns = 20
model = "sonnet"
auto_complete = true
interactive = false
# truncate_conversation = true
```

Sessions are stored in `.storms/` alongside `storm.toml` (add to `.gitignore`).

## Usage

```bash
# Initialize a project config
uv run storm init [--topic "quick topic"]
uv run storm init --force             # overwrite existing storm.toml

# Migrate existing config to latest schema
uv run storm init --update

# Start a session (reads storm.toml if present, or pass a topic)
uv run storm start [TOPIC] [OPTIONS]
uv run storm start --config path/to/storm.toml
uv run storm start "Quick topic" --max-turns 4

# With custom roles (one-off mode)
uv run storm start "Microservices vs monolith" --roles "Advocate" "Skeptic" --auto-complete

# CLI flags override TOML values
uv run storm start --max-turns 6 --model opus

# Give agents read-only access to reference materials (repeatable)
uv run storm start --reference-dir ./research/notes --reference-dir ./design/specs

# Interactive mode — type nudges at any time to steer the conversation;
# agents can ask you questions via [ASK_USER]
uv run storm start --interactive

# Resume a paused session (Ctrl+C to pause)
uv run storm resume <session-id>
uv run storm resume <session-id> --force  # recover after a hard kill

# List and inspect sessions
uv run storm list
uv run storm show <session-id>            # includes why the session stopped
```

## Conversation Pacing

When deliverables or a goal are defined, agents receive pacing guidance:

- **System prompt** includes the turn budget, expected deliverables, and a pacing overview
- **Turn prompts** show percentage progress with escalating nudges:
  - Early turns: standard "continue the brainstorm"
  - 50%: "Start narrowing down and committing to approaches"
  - 75%: "Focus on producing deliverables and resolving open questions"
  - Final 2 turns: "Prioritize completing artifacts and capturing remaining decisions"
- **Summary prompt** asks the summarizing agent to assess which deliverables were produced

## How It Works

1. Two Claude Code CLI instances are launched with persistent sessions
2. Agents take strict alternating turns responding to each other
3. Each agent can save notes to its memory filesystem for long-term retention
4. Agents can produce shared artifacts (code, documents)
5. Agents can formalize shared decisions using an agreement protocol (`[PROPOSE]`/`[ACCEPT]`/`[REJECT]`/`[REVISE]`); confirmed agreements persist to `agreements.md` and feed into deliverable compilation
6. Pacing nudges guide agents through exploration, convergence, and deliverable production
7. In `--auto-complete` mode, agents signal `[DONE]` when the topic is well-explored
8. Sessions can be paused with Ctrl+C and resumed later; each session records why it stopped (visible via `storm show`)
9. When running in a terminal, a full-screen TUI provides scrollable output, an animated thinking timer, and a persistent input bar for nudges; piped/non-TTY output falls back to plain Rich console

## Security

Agent filesystem access is restricted via path-scoped `--allowedTools` patterns:

- **Read/Glob/Grep**: session directory + reference directories (if configured)
- **Write/Edit**: session directory only
- **Bash/other tools**: not available to agents

## License

MIT
