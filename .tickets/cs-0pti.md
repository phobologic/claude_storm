---
id: cs-0pti
status: closed
deps: []
links: []
created: 2026-02-20T05:06:46Z
type: chore
priority: 2
assignee: Michael Barrett
parent: cs-st02
---
# Proposal ID collision guard

generate_proposal_id() in agreements.py uses uuid4().hex[:4] — only 65K unique values with no collision check. Simple fix: check generated ID against existing pending_proposals and accepted_agreements in a retry loop, or bump to 6 chars. Low probability of collision in practice but easy to guard against.

