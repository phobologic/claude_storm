---
id: cs-se82
status: open
deps: []
links: []
created: 2026-02-20T05:06:37Z
type: feature
priority: 2
assignee: Michael Barrett
parent: cs-o05c
---
# Auto-retry with backoff on agent errors

Add exponential backoff retry (2-3 attempts) when invoke_agent() fails due to transient errors (API rate limits, timeouts). Currently any agent error pauses the session and requires manual resume. Implement in the _run_turn() call site in session.py. Should distinguish transient errors (rate limit, timeout) from permanent ones (invalid config). Add a max_retries config option.

