---
id: claude_storm-7dx.8
status: open
deps: []
links: []
created: 2026-02-16T14:51:36.366181-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Magic string 'draft-' prefix used across modules without a shared constant

**File**: /Users/mike/git/claude_storm/claude_storm/session.py (line 308), /Users/mike/git/claude_storm/claude_storm/compilation.py (line 54)
**Line(s)**: session.py:308, compilation.py:54
**Description**: The string literal `"draft-"` is used as a magic prefix in two modules (`session.py` adds it, `compilation.py` strips it for matching). If this prefix ever changes, both files must be updated. A shared constant would make the coupling explicit and discoverable.

**Suggested Fix**: Define `DRAFT_PREFIX = "draft-"` in `config.py` (or `compilation.py` since that's where `MIN_WORD_OVERLAP_DIVISOR` already lives) and import it in both modules:

```python
# config.py or compilation.py
DRAFT_PREFIX = "draft-"

# session.py
from claude_storm.compilation import DRAFT_PREFIX

draft_filename = (
    f"{DRAFT_PREFIX}{filename}" if not filename.startswith(DRAFT_PREFIX) else filename
)

# compilation.py
stem = re.sub(rf"^{re.escape(DRAFT_PREFIX)}", "", path.stem)
```



