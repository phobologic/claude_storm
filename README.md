# Claude Storm

A dual-agent brainstorming system that orchestrates two Claude Code CLI instances in strict alternating turns. Each agent maintains a persistent Claude session.

**Try it now** (no install needed):

```bash
uvx --from claude-storm storm start "Design a REST API for a todo app"
```

## Prerequisites

- **Claude Code CLI** — must be installed and authenticated (`claude` command available on your `$PATH`). See the [Claude Code docs](https://docs.anthropic.com/en/docs/claude-code/overview) for setup instructions.
- **Python 3.11+**

**API usage:** Claude Storm spawns Claude Code subprocesses — each agent turn is an API call billed through your Claude Code authentication (Anthropic API key or Claude Pro/Max subscription). Agents often finish early via consensus, so a session with `--max-turns 20` typically uses fewer than 40 calls, plus a few more for deliverable compilation at the end.

## Installation

```bash
# Run without installing (recommended for trying it out)
uvx --from claude-storm storm start "your topic"

# Install globally
pip install claude-storm

# Or with pipx
pipx install claude-storm
```

Once installed, the `storm` command is available:

```bash
storm start "your topic"
```

<details>
<summary>Development install (from source)</summary>

```bash
git clone https://github.com/phobologic/claude_storm.git
cd claude_storm
uv sync
uv run storm start "your topic"
```

</details>

## Quick Start

```bash
# One-off brainstorming session
storm start "Design a REST API for a todo app" --max-turns 4

# Project-based workflow (recommended)
storm init --topic "Design a distributed task queue"
# Edit storm.toml to add roles, goal, deliverables...
storm start
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
Favor battle-tested technologies; produce production-ready designs
with clear trade-off analysis for each decision.
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
# reference_dirs = ["./research/notes"]

[options]
max_turns = 20
model = "sonnet"
auto_complete = true
interactive = false
# max_minutes = 30
# agent_timeout = 600
# truncate_conversation = true
# web_search = false
```

Sessions are stored in `.storms/` alongside `storm.toml` (add to `.gitignore`).

### Configuration Reference

**\[session\]**

| Key | Default | Description |
|-----|---------|-------------|
| `topic` | *(required)* | The subject or question under discussion. Multi-line strings supported. |
| `goal` | — | Desired outcome or success criterion. Reinforced in pacing, summary, and deliverable compilation. Describes direction/quality, not a specific document. |
| `role_a` / `role_b` | — | Agent personas. Become the agent's system prompt, replacing Claude Code's default instructions. First line is used as the TUI display label — keep it short (a title); additional lines provide detailed persona guidance. |
| `deliverables` | `[]` | Documents to produce as `[ARTIFACT]` files. Drives pacing and post-session compilation. Also settable via `--deliverable` CLI flag. Draft artifacts with matching filenames are used as foundations. |
| `reference_dirs` | `[]` | Read-only directories agents can browse via Read/Glob/Grep. |

**\[options\]**

| Key | Default | Description |
|-----|---------|-------------|
| `max_turns` | `20` | Turn budget. Shapes percentage-based pacing. Set to a higher value or omit when using `max_minutes` alone. |
| `max_minutes` | — | Wall-clock time limit in minutes. Acts independently of `max_turns`; whichever limit is hit first stops the session. |
| `model` | `"sonnet"` | Claude model to use (`"sonnet"`, `"opus"`, or a full model ID). |
| `auto_complete` | `true` | Allow agents to signal `[DONE]`. Requires both agents to agree. |
| `interactive` | `false` | Enable user nudges and `[ASK_USER]` questions. |
| `agent_timeout` | `600` | Per-turn timeout in seconds. Increase for complex topics where agents take longer to respond. |
| `truncate_conversation` | `true` | Truncate conversation to last ~50k chars during deliverable compilation. |
| `web_search` | `false` | Allow agents to use WebSearch and WebFetch tools. Off by default due to prompt injection risk from untrusted web content. |

## Usage

```bash
# Initialize a project config
storm init [--topic "quick topic"]
storm init --force             # overwrite existing storm.toml

# Migrate existing config to latest schema
storm init --update

# Start a session (reads storm.toml if present, or pass a topic)
storm start [TOPIC] [OPTIONS]
storm start --config path/to/storm.toml
storm start "Quick topic" --max-turns 4

# With custom roles and a goal (one-off mode)
storm start "Microservices vs monolith" --roles "Advocate" "Skeptic" --auto-complete
storm start "API design" --goal "Prefer REST; produce an OpenAPI spec"

# Produce specific deliverables (repeatable)
storm start --deliverable "Architecture doc" --deliverable "Data model"

# CLI flags override TOML values
storm start --max-turns 6 --model opus
storm start --max-minutes 30           # stop after 30 minutes regardless of turns
storm start --agent-timeout 120        # shorten per-turn timeout to 2 minutes

# Give agents read-only access to reference materials (repeatable)
storm start --reference-dir ./research/notes --reference-dir ./design/specs

# Interactive mode — type nudges at any time to steer the conversation;
# agents can ask you questions via [ASK_USER]
storm start --interactive

# Enable web search (agents can use WebSearch + WebFetch)
storm start --web-search

# Enable verbose debug logging (agent prompts + raw responses written to debug.log)
storm --debug start "your topic"

# Resume a paused session (Ctrl+C to pause)
storm resume <session-id>
storm resume <session-id> --force  # recover after a hard kill

# List and inspect sessions
storm list
storm list --config path/to/storm.toml  # locate .storms/ from a specific config
storm show <session-id>                 # includes why the session stopped
storm show <session-id> --config path/to/storm.toml
```

## Agent Protocol

Agents communicate via structured directives embedded in their responses.

### Shared Output

| Directive | Syntax | Description |
|-----------|--------|-------------|
| `[PROPOSE]` | `[PROPOSE title="..."]content[/PROPOSE]` | Propose a shared agreement for the other agent to confirm. |
| `[ACCEPT]` | `[ACCEPT id="..."]` | Accept a pending proposal by ID. |
| `[REJECT]` | `[REJECT id="..." reason="..."]` | Reject a pending proposal with explanation. |
| `[REVISE]` | `[REVISE id="..."]new content[/REVISE]` | Propose a revision to an existing confirmed agreement. Creates a new pending proposal. |
| `[ARTIFACT]` | `[ARTIFACT filename="..."]content[/ARTIFACT]` | Produce a shared output file (code, document, etc.). Optional `action="append"` adds content to an existing file across turns instead of replacing it. Only `filename` and `action` are recognized attributes. |
| `[DONE]` | `[DONE reason="..."]` | Signal that brainstorming is complete. The other agent must confirm; if they disagree, conversation continues. |
| `[ASK_USER]` | `[ASK_USER]question[/ASK_USER]` | Pause to ask the human user a question (interactive mode only). |

## Conversation Pacing

When deliverables or a goal are defined, agents receive pacing guidance based on turn progress:

| Progress | Guidance |
|----------|----------|
| ≤20% (interactive) | Use `[ASK_USER]` to clarify intent before narrowing |
| Default | Continue brainstorming |
| 50% | Start narrowing; produce draft `[ARTIFACT]` files |
| 75% | Finalize artifacts, resolve open questions |
| Final 2 turns | Complete all artifacts; produce any missing deliverables |

**Agreement nudges:** After turn 3 with no agreements, agents are nudged to use `[PROPOSE]`. If 4+ turns pass since the last accepted agreement, agents get a reminder.

**Deliverable compilation:** After the session ends, each deliverable is compiled by a separate Claude instance from the conversation log, agreements, and matching draft artifacts.

## Interactive Mode

- **User nudges**: Type at any time in the TUI to steer the conversation; queued and merged into the next turn prompt.
- **Agent questions**: `[ASK_USER]` pauses the agent to ask the user. The TUI defers the question if the user is mid-typing.
- **Early clarification pacing**: In interactive sessions, agents are encouraged to use `[ASK_USER]` in the first 20% of turns.
- **Non-interactive**: No user input during the session; `[ASK_USER]` is not available to agents.

## TUI Navigation

The TUI auto-scrolls to follow new output. Scrolling up pauses auto-follow and
shows a scroll indicator; scrolling back to the bottom (or pressing `End`) resumes it.

| Key | Action |
|-----|--------|
| `PageUp` / `Shift+Up` | Scroll up one page |
| `PageDown` / `Shift+Down` | Scroll down one page |
| `End` | Jump to bottom and resume auto-follow |

## How It Works

1. Two Claude Code CLI instances are launched with persistent sessions
2. Agents take strict alternating turns responding to each other
3. Agents can produce shared artifacts (code, documents)
4. Agents formalize shared decisions using an agreement protocol (`[PROPOSE]`/`[ACCEPT]`/`[REJECT]`/`[REVISE]`); confirmed agreements persist to `agreements.md` and feed into deliverable compilation. Verbal agreement alone ("I agree", "good point") does **not** create a shared record — only `[PROPOSE]` + `[ACCEPT]` does. Pacing nudges encourage `[PROPOSE]` usage when no agreements have been recorded recently.
5. Pacing nudges guide agents through exploration, convergence, and deliverable production
6. In `--auto-complete` mode, agents signal `[DONE]` when the topic is well-explored
7. Sessions can be paused with Ctrl+C and resumed later; each session records why it stopped (visible via `storm show`)
8. When running in a terminal, a full-screen TUI provides live-streamed agent output, an animated thinking timer, and a persistent input bar for nudges (Shift+Enter for newlines); the header shows the session ID. Piped/non-TTY output falls back to plain Rich console

## Security

Agent filesystem access is restricted via path-scoped `--allowedTools` patterns:

- **Read/Glob/Grep**: session directory + reference directories (if configured)
- **Write/Edit**: session directory only
- **Bash/other tools**: not available to agents

## License

MIT
