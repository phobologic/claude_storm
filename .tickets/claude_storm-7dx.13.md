---
id: claude_storm-7dx.13
status: open
deps: []
links: []
created: 2026-02-16T14:52:01.751056-08:00
type: task
priority: 3
parent: claude_storm-7dx
---
# Summary prompt guardrail lacks explanatory comment

**File**: /Users/mike/git/claude_storm/claude_storm/prompts.py
**Line(s)**: 401-406
**Description**: The added instruction block in `build_summary_prompt` uses strong imperative language ("IMPORTANT", "Do NOT") to prevent the Claude agent from using tools instead of outputting the summary inline. While this is a pragmatic workaround, the comment lacks context about *why* this guardrail exists. A brief inline comment explaining the failure mode (e.g., "agents sometimes attempt to write the summary to a file instead of returning it") would help future maintainers understand the intent.

**Suggested Fix**: Add a brief comment above the instruction:

```python
# Guard against agents using Write/Edit tools instead of returning
# the summary text directly in their response.
parts.append(
    "Be concise but thorough. Format as markdown.\n\n"
    "IMPORTANT: Output the full summary directly in your response.\n"
    "Do NOT use Write or Edit tools. Do NOT ask for permission — "
    "write the actual summary content here."
)
```



