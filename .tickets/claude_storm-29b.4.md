---
id: claude_storm-29b.4
status: closed
deps: []
links: []
created: 2026-02-14T21:29:11.540999-08:00
type: task
priority: 1
parent: claude_storm-29b
---
# write_debug_summary uses object type with 8 type: ignore comments

**File**: debug.py (lines 162-209)
**Description**: write_debug_summary declares config as object and uses type: ignore[attr-defined] on every attribute access (current_turn, max_turns, status, stop_reason, get_watermark, agent_label). This defeats static type checking entirely, makes the function contract opaque, and suppresses tooling that could catch bugs.
**Suggested Fix**: Use a TYPE_CHECKING guard to properly type the parameter without creating a runtime circular import:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_storm.config import SessionConfig

def write_debug_summary(log_path: Path, config: SessionConfig, duration_s: int | None) -> None:
```

This eliminates all type: ignore comments and provides proper IDE support. debug.py is a leaf module so config.py import would not create a cycle, or use TYPE_CHECKING to be safe.
**Found by**: All 3 reviewers (logic: Medium, perf: Medium, readability: High)


