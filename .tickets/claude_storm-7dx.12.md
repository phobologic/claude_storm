---
id: claude_storm-7dx.12
status: open
deps: []
links: []
created: 2026-02-16T14:51:48.800826-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Nested re.sub calls in find_matching_artifacts reduce readability

**File**: /Users/mike/git/claude_storm/claude_storm/compilation.py
**Line(s)**: 44-46
**Description**: The nested `re.sub` calls on line 46 are hard to read at a glance:

```python
deliv_words = set(
    re.sub(r"[_\-]", " ", re.sub(r"[^\w\s-]", "", deliv_base)).lower().split()
)
```

The inner `re.sub` strips non-word characters (keeping hyphens), then the outer `re.sub` replaces underscores/hyphens with spaces. Nesting two regex substitutions inside a `set()` comprehension with `.lower().split()` chained on is dense.

**Suggested Fix**: Break into intermediate variables with clear names:

```python
# Remove punctuation (keep word chars, whitespace, hyphens)
cleaned = re.sub(r"[^\w\s-]", "", deliv_base)
# Normalize separators to spaces
normalized = re.sub(r"[_\-]", " ", cleaned).lower()
deliv_words = set(normalized.split())
```



