# Claude Storm

Dual-agent brainstorming system that orchestrates two Claude Code CLI sessions.

## Project Structure

- `claude_storm/` - Main Python package
  - `cli.py` - Typer CLI app (entry point: `storm`)
  - `config.py` - SessionConfig dataclass + JSON persistence
  - `project.py` - Project directory config (storm.toml parsing, scaffolding, pacing, migration)
  - `agents.py` - Claude CLI subprocess wrapper with session management
  - `memory.py` - Per-agent markdown memory filesystem with index
  - `prompts.py` - System prompt and per-turn prompt templates with pacing
  - `display.py` - Rich-based live terminal display
- `tests/` - Pytest test suite
- `.storms/` - Runtime session data (git-ignored), created per-project

## Commands

- `uv run storm init [--topic "..."]` - Create a storm.toml config in CWD
- `uv run storm init --update` - Migrate existing storm.toml to latest schema
- `uv run storm start [TOPIC] [OPTIONS]` - Start a session (reads storm.toml if present)
- `uv run storm resume <session-id>` - Resume a paused session
- `uv run storm list` - List all sessions in .storms/
- `uv run storm show <session-id>` - Show session details

## Running Tests

```
uv run pytest
```

## Key Design Decisions

- Project config lives in `storm.toml` with `[session]` (topic, goal, roles, deliverables) and `[options]` (max_turns, model, etc.)
- Sessions stored in `.storms/{session_id}/` relative to the config file
- CLI flags override TOML values (three-layer merge: CLI > TOML > defaults)
- Each agent gets a persistent Claude CLI session via `--session-id` / `--resume`
- Memory is markdown files with a JSON index per agent
- Agents communicate via structured directives: `[MEMORY]`, `[ARTIFACT]`, `[DONE]`, `[ASK_USER]`
- Conversation pacing: percentage-based nudges at 50%, 75%, and final 2 turns
- Rich panels with color coding (blue=Agent A, green=Agent B)
- Reference directories (`--reference-dir`, repeatable): agents get read-only access to browse background materials
- Agent filesystem access is path-scoped via `--allowedTools` patterns: Read/Glob/Grep for session dir + reference dirs, Write/Edit for session dir only
- Config migration (`storm init --update` or automatic on `storm start`): renames deprecated keys and appends missing defaults
