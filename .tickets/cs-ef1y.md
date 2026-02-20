---
id: cs-ef1y
status: closed
deps: [cs-f9vd]
links: []
created: 2026-02-20T05:34:24Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kmv6
---
# Adopt shared helpers in test_agreements.py

test_agreements.py constructs agreement and proposal dicts with 7-8 keys dozens of times inline. After cs-f9vd adds _make_agreement and _make_proposal helpers to conftest.py, this file should adopt them.

SCOPE: Replace all inline dict constructions of agreement/proposal dicts with calls to the helpers. Look for dicts with keys like {id, title, content, summary, proposed_by, proposed_turn, accepted_turn, revises} and {id, title, content, summary, proposed_by, turn, revises}.

Specific locations (approximate — verify against current file):
- Lines 231-249, 264-283, 292-302, 344-362, 366-388, 397-410, 420-430
- Lines 459-479, 517-530, 559-567, 580-590, 615-627, 627-636
- Lines 665-675, 686-696, 703-712, 744-765

Only use the helpers where the default values match or can be overridden. Don't force-fit if a test intentionally uses unusual values that the helper doesn't support.

Files touched: test_agreements.py only

