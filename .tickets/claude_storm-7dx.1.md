---
id: claude_storm-7dx.1
status: closed
deps: []
links: []
created: 2026-02-16T14:51:09.369104-08:00
type: task
priority: 2
parent: claude_storm-7dx
---
# Extension-stripping regex is too broad — matches non-extension suffixes

**File**: `/Users/mike/git/claude_storm/claude_storm/compilation.py`
**Line(s)**: 43
**Description**: The regex `r"\.\w{1,5}$"` used to strip file extensions will also match legitimate trailing substrings that happen to be 1-5 word characters after a dot. For example, a deliverable named `"v2.0_plan"` would have `.0_pl` matched and stripped (since `\w` includes underscores). Similarly, `"chapter_3.final"` would lose `.final`.

The same regex is used on line 155 in `compile_deliverables` for sanitizing the output filename.

**Suggested Fix**: Use a more targeted extension-stripping regex that only matches common file extensions, or anchor the match to known extensions:

```python
# Option A: only strip known document extensions
deliv_base = re.sub(r"\.(md|txt|html|pdf|rst|docx?)$", "", deliverable_name, flags=re.IGNORECASE)

# Option B: require the extension to not contain underscores/hyphens (narrower than \w)
deliv_base = re.sub(r"\.[a-zA-Z]{1,5}$", "", deliverable_name)
```

Option B is the minimal fix — it prevents `\w` from greedily matching underscores in token-like suffixes while still handling typical file extensions.



