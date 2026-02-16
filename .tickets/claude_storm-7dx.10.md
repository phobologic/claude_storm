---
id: claude_storm-7dx.10
status: closed
deps: []
links: []
created: 2026-02-16T14:51:43.201189-08:00
type: task
priority: 2
parent: claude_storm-7dx
---
# Inline filename sanitization duplicates existing _slugify helpers

**File**: /Users/mike/git/claude_storm/claude_storm/compilation.py
**Line(s)**: 155-157
**Description**: `compilation.py` inlines its own filename sanitization logic (`re.sub(r"[^\w\s-]", "", base).strip()` then `re.sub(r"[\s]+", "_", safe_name).lower()`) rather than reusing the `_slugify` helpers that already exist in both `agreements.py` and `memory.py`. The three implementations differ slightly (hyphens vs underscores as separators, truncation), but the core pattern is the same. This is a missed reusability opportunity that could drift over time.

**Suggested Fix**: Consider extracting a shared `slugify` utility (e.g., in a `utils.py` or in `config.py`) that accepts a separator parameter, then use it in all three locations:

```python
def slugify(title: str, sep: str = "-", max_len: int = 60) -> str:
    """Convert a title to a filename-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", sep, slug).strip(sep)
    return slug[:max_len] if slug else "note"
```

Then `compilation.py` calls `slugify(base, sep="_", max_len=0)` (or similar), and `agreements.py`/`memory.py` use `slugify(title)`.



