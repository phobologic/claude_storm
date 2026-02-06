# Claude Storm

Dual-agent brainstorming system that orchestrates two Claude Code CLI sessions.

## Commands

```
uv run storm init [--topic "..."]     # Create storm.toml in CWD
uv run storm init --update            # Migrate existing storm.toml to latest schema
uv run storm start [TOPIC] [OPTIONS]  # Start a session (reads storm.toml if present)
uv run storm resume <session-id>      # Resume a paused session
uv run storm list                     # List sessions in .storms/
uv run storm show <session-id>        # Show session details
uv run pytest                         # Run all tests
uv run ruff check .                   # Lint
uv run ruff format .                  # Format
```

## Module Dependency Hierarchy

Imports flow downward only. Never add an import that creates a cycle.

```
cli.py            ← Typer commands; imports session, config, project, display
  session.py      ← imports compilation, config, agents, debug, directives, display, memory, prompts, agreements
  compilation.py  ← imports config, agents, debug, directives, display, prompts, agreements
  app.py          ← imports config, messages, widgets; lazy-imports session, display, agents
  prompts.py      ← imports config, project
  display.py      ← imports config; lazy-imports messages, session
  agreements.py   ← imports config
  agents.py       ← imports config
  ─────────────── leaf modules (no local imports) ───────────────
  config.py   project.py   memory.py   debug.py   messages.py   widgets.py   directives.py
```

`app.py` and `display.py` use lazy imports (inside methods) to avoid
circular dependencies. Preserve this pattern when adding cross-module references.

## Code Conventions

**Imports** — Every source module in `claude_storm/` starts with
`from __future__ import annotations` (after the module docstring). Test files
do not require this. Import order: future → stdlib → third-party → local,
blank lines between groups. No wildcard imports.

**Typing** — Modern union syntax: `str | None`, `list[str]`, `dict[str, str]`.
Exception: Typer CLI annotations in `cli.py` use `Optional[str]` because Typer
inspects annotations at runtime before PEP 604 evaluation.

**Naming** — `snake_case` functions/variables, `PascalCase` classes,
`UPPER_SNAKE_CASE` constants. Private helpers prefixed with `_`.

**Docstrings** — Google-style on all public functions and classes. Every module
has a docstring on line 1. Include Args/Returns/Raises when non-trivial.

**Dataclasses** — `field(default_factory=...)` for mutable defaults. Factory
classmethods (e.g., `SessionConfig.create()`) for complex construction.

**Interfaces** — `typing.Protocol` for abstract interfaces (see `DisplayProtocol`
in `display.py`). Concrete implementations: `PlainDisplay`, `TextualDisplay`.

**Error handling** — Specific exceptions from library code (`FileNotFoundError`,
`ValueError`). CLI commands catch and display errors via `console.print` +
`typer.Exit(1)`. No bare `except` clauses. Use `finally` for cleanup.

**Paths** — `pathlib.Path` everywhere. JSON written with `indent=2` and trailing
newline. Session data lives in `.storms/{session_id}/`.

## Architecture Patterns

**Config merge** — Three layers: CLI flags > TOML values > hardcoded defaults.
Resolved in `cli.py`'s `start()` before creating `SessionConfig`.

**Subprocess IPC** — Agents are Claude CLI processes (`claude -p --output-format json`).
First turn: `--session-id` + `--system-prompt`. Subsequent turns: `--resume`.
Thread-safe via `_process_lock` + `_active_process` in `agents.py`.

**Directive parsing** — Regex extraction of `[MEMORY]`, `[ARTIFACT]`, `[PROPOSE]`,
etc. in `parse_directives()` (in `directives.py`). Returns a `ParsedDirectives`
dataclass with typed fields (e.g., `memories`, `artifacts`, `clean_text`).

**TUI threading** — `StormApp` runs `run_session` in a worker thread. Worker → TUI
via `Message` subclasses (`post_message`). TUI → worker via `deque` (nudges) and
`threading.Event` (ASK_USER responses).

**Signal handling** — `SIGINT` registered on main thread only (in `session.py`).
TUI mode uses Textual's own `ctrl+c` binding. `_shutdown_requested` flag polled
in turn loop.

## Testing Conventions

- Run: `uv run pytest`
- Fixtures in `tests/conftest.py`: `tmp_storms`, `sample_config`, `agent_a_dir`, `agent_b_dir`
- Group related tests in classes (`TestSessionConfig`, `TestParseDirectives`)
- Mock subprocess with `unittest.mock.patch` + `MagicMock` — never call Claude CLI
- Filesystem isolation via `tmp_path` / `tmp_storms`
- Capture Rich output with `StringIO` + `Console(file=...)`
- No network calls, no external service dependencies

## Issue Tracking (Beads)

This project uses **bd** (beads) for issue tracking. Issues are stored in
`.beads/` as a SQLite database with JSONL git sync.

**When to use beads** — Use `bd` for all task/issue tracking instead of
markdown files, TodoWrite, or TaskCreate. Create issues before starting work,
claim them with `--status in_progress`, and close them when done.

**Essential commands:**

```
bd ready                                    # Show unblocked work
bd show <id>                                # View issue details
bd create --title="..." --type=task -p 2    # Create issue (priority 0-4)
bd update <id> --status=in_progress         # Claim work
bd close <id>                               # Complete work
bd dep add <child> <parent>                 # child depends on parent
bd sync                                     # Sync with git
```

**Workflow:**

1. `bd ready` — find available work
2. `bd update <id> --status=in_progress` — claim it
3. Do the work
4. `bd close <id>` — mark complete
5. `bd sync` — sync at session end

**Rules:**

- Priority uses integers 0-4 (0=critical, 4=backlog), not words
- Never use `bd edit` — it opens `$EDITOR` which blocks agents
- Run `bd sync` before ending a session
- Use `bd prime` for full workflow context after compaction or new session

## Living Document

This file is the source of truth for project conventions. When writing code:

1. Follow the patterns documented above
2. If you notice a recurring pattern not yet listed (e.g., a new error-handling
   convention, a new module, a naming pattern), point it out to the user
3. On user confirmation, add the pattern to the relevant section
4. Keep entries concise — every line should prevent a future inconsistency
