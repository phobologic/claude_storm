"""Tests for the shared agreements protocol."""

import json
from unittest.mock import MagicMock

from claude_storm.agreements import (
    RevisionContext,
    _agreement_filename,
    _extract_summary,
    _slugify,
    accept_proposal,
    create_proposal,
    format_agreement_index,
    format_agreements_for_compilation,
    format_agreements_for_prompt,
    generate_proposal_id,
    reject_proposal,
    write_agreement_files,
)
from claude_storm.config import SessionConfig
from claude_storm.session import _resolve_revision_context
from tests.conftest import _make_agreement, _make_proposal


class TestGenerateProposalId:
    def test_returns_4_hex_chars(self):
        pid = generate_proposal_id()
        assert len(pid) == 4
        int(pid, 16)  # should not raise

    def test_unique_ids(self):
        ids = {generate_proposal_id() for _ in range(100)}
        assert len(ids) > 90  # statistically should all be unique


class TestExtractSummary:
    def test_plain_text(self):
        result = _extract_summary("REST API with pagination.")
        assert result == "REST API with pagination."

    def test_strips_heading_prefix(self):
        assert _extract_summary("## Overview of the system") == "Overview of the system"

    def test_uses_first_line_only(self):
        content = "First line summary\nSecond line detail\nThird line"
        assert _extract_summary(content) == "First line summary"

    def test_truncates_to_120_chars(self):
        long_line = "A" * 200
        assert len(_extract_summary(long_line)) == 120

    def test_handles_empty_string(self):
        assert _extract_summary("") == ""

    def test_strips_whitespace(self):
        assert _extract_summary("  \n  Some content  ") == "Some content"


class TestCreateProposal:
    def test_creates_pending_proposal(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        pid = create_proposal(config, "Use REST", "REST is better", "a", 4)
        assert len(pid) == 4
        assert len(config.pending_proposals) == 1
        assert config.pending_proposals[0]["id"] == pid
        assert config.pending_proposals[0]["title"] == "Use REST"
        assert config.pending_proposals[0]["content"] == "REST is better"
        assert config.pending_proposals[0]["proposed_by"] == "a"
        assert config.pending_proposals[0]["turn"] == 4
        assert config.pending_proposals[0]["revises"] is None
        assert config.pending_proposals[0]["summary"] == "REST is better"

    def test_creates_revision_proposal(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        revision = RevisionContext(
            revises="a3f2",
            title="Use REST v2",
            original_content=None,
            original_turn=None,
            original_agent=None,
        )
        create_proposal(
            config,
            "Use REST v2",
            "REST with pagination",
            "b",
            8,
            revision=revision,
        )
        assert config.pending_proposals[0]["revises"] == "a3f2"

    def test_multiple_proposals(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        id1 = create_proposal(config, "A", "content A", "a", 1)
        id2 = create_proposal(config, "B", "content B", "b", 2)
        assert len(config.pending_proposals) == 2
        assert id1 != id2

    def test_summary_from_multiline_content(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        create_proposal(
            config, "Architecture", "## Use microservices\nWith gRPC", "a", 1
        )
        assert config.pending_proposals[0]["summary"] == "Use microservices"

    def test_proposal_id_no_collision(self, make_config, monkeypatch):
        """Collision is retried until a unique ID is found."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals.append(
            {
                "id": "aaaa",
                "title": "Existing",
                "content": "x",
                "proposed_by": "a",
                "turn": 1,
            }
        )
        calls = iter(["aaaa", "bbbb"])
        monkeypatch.setattr(
            "claude_storm.agreements.generate_proposal_id", lambda: next(calls)
        )
        pid = create_proposal(config, "Title", "Content", "a", 2)
        assert pid == "bbbb"
        assert config.pending_proposals[-1]["id"] == "bbbb"


class TestAcceptProposal:
    def test_moves_to_accepted(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        pid = create_proposal(config, "Use REST", "REST is good", "a", 4)
        accepted = accept_proposal(config, pid, 5)
        assert accepted is not None
        assert accepted["id"] == pid
        assert accepted["title"] == "Use REST"
        assert accepted["proposed_turn"] == 4
        assert accepted["accepted_turn"] == 5
        assert accepted["summary"] == "REST is good"
        assert len(config.pending_proposals) == 0
        assert len(config.accepted_agreements) == 1

    def test_writes_agreement_files(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        pid = create_proposal(config, "Use REST", "REST is good", "a", 4)
        accept_proposal(config, pid, 5)
        # Combined file still written
        agreements_path = config.session_dir() / "agreements.md"
        assert agreements_path.exists()
        content = agreements_path.read_text()
        assert pid in content
        assert "Use REST" in content
        # Per-file also written
        per_file = config.session_dir() / "agreements" / f"{pid}_use-rest.md"
        assert per_file.exists()
        assert "REST is good" in per_file.read_text()

    def test_returns_none_for_missing_id(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        assert accept_proposal(config, "xxxx", 5) is None

    def test_accept_revision(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        orig = create_proposal(config, "Use REST", "REST is good", "a", 4)
        accept_proposal(config, orig, 5)
        revision = RevisionContext(
            revises=orig,
            title="Use REST",
            original_content="REST is good",
            original_turn=4,
            original_agent="a",
        )
        rev = create_proposal(
            config,
            "Use REST",
            "REST with caching",
            "b",
            8,
            revision=revision,
        )
        accepted = accept_proposal(config, rev, 9)
        assert accepted["revises"] == orig
        assert len(config.accepted_agreements) == 2

    def test_summary_fallback_for_legacy_proposal(self, make_config):
        """Accept a proposal without a summary field (legacy migration)."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals.append(
            {
                "id": "ab12",
                "title": "Legacy",
                "content": "## Old content\nDetails here",
                "proposed_by": "a",
                "turn": 3,
            }
        )
        accepted = accept_proposal(config, "ab12", 4)
        assert accepted["summary"] == "Old content"


class TestRejectProposal:
    def test_removes_from_pending(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        pid = create_proposal(config, "Use SOAP", "SOAP is enterprise", "a", 4)
        rejected = reject_proposal(config, pid)
        assert rejected is not None
        assert rejected["id"] == pid
        assert len(config.pending_proposals) == 0
        assert len(config.accepted_agreements) == 0

    def test_returns_none_for_missing_id(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        assert reject_proposal(config, "xxxx") is None

    def test_stores_rejection_with_reason(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        pid = create_proposal(config, "Use SOAP", "SOAP is enterprise", "a", 4)
        reject_proposal(config, pid, reason="Too verbose", turn=5)
        assert len(config.rejected_proposals) == 1
        r = config.rejected_proposals[0]
        assert r["id"] == pid
        assert r["title"] == "Use SOAP"
        assert r["proposed_by"] == "a"
        assert r["proposed_turn"] == 4
        assert r["rejected_turn"] == 5
        assert r["reason"] == "Too verbose"

    def test_stores_rejection_without_reason(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        pid = create_proposal(config, "Use SOAP", "SOAP is enterprise", "a", 4)
        reject_proposal(config, pid)
        assert len(config.rejected_proposals) == 1
        assert config.rejected_proposals[0]["reason"] == ""

    def test_persists_rejection_to_disk(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        pid = create_proposal(config, "Use SOAP", "SOAP is enterprise", "a", 4)
        reject_proposal(config, pid, reason="We decided REST", turn=5)
        loaded = SessionConfig.load(
            "agree-test", storms_dir=str(config.session_dir().parent)
        )
        assert len(loaded.rejected_proposals) == 1
        assert loaded.rejected_proposals[0]["reason"] == "We decided REST"


class TestSlugify:
    def test_basic_title(self):
        assert _slugify("Use REST") == "use-rest"

    def test_special_characters(self):
        assert _slugify("Use PostgreSQL!") == "use-postgresql"

    def test_truncates_to_60(self):
        assert len(_slugify("A" * 100)) == 60

    def test_strips_leading_trailing_hyphens(self):
        assert _slugify("--hello--") == "hello"


class TestAgreementFilename:
    def test_basic(self):
        agreement = {"id": "a3f2", "title": "Use REST"}
        assert _agreement_filename(agreement) == "a3f2_use-rest.md"

    def test_with_special_chars(self):
        agreement = {"id": "e9d4", "title": "Use PostgreSQL!"}
        assert _agreement_filename(agreement) == "e9d4_use-postgresql.md"


class TestWriteAgreementFiles:
    def test_empty_agreements(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        write_agreement_files(config)
        path = config.session_dir() / "agreements.md"
        assert path.exists()
        assert path.read_text() == ""
        # agreements/ dir should exist but be empty
        agreements_dir = config.session_dir() / "agreements"
        assert agreements_dir.is_dir()
        assert list(agreements_dir.glob("*.md")) == []

    def test_writes_individual_files(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API with pagination.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            },
            {
                "id": "e9d4",
                "title": "Use PostgreSQL",
                "content": "PostgreSQL with Redis.",
                "proposed_by": "b",
                "proposed_turn": 6,
                "accepted_turn": 7,
                "revises": None,
            },
        ]
        write_agreement_files(config)
        agreements_dir = config.session_dir() / "agreements"
        assert (agreements_dir / "a3f2_use-rest.md").exists()
        assert (agreements_dir / "e9d4_use-postgresql.md").exists()
        # Each file contains the agreement content
        rest_content = (agreements_dir / "a3f2_use-rest.md").read_text()
        assert "REST API with pagination." in rest_content
        assert "[a3f2]" in rest_content
        pg_content = (agreements_dir / "e9d4_use-postgresql.md").read_text()
        assert "PostgreSQL with Redis." in pg_content

    def test_writes_combined_agreements_md(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            },
            {
                "id": "e9d4",
                "title": "Use PostgreSQL",
                "content": "PostgreSQL.",
                "proposed_by": "b",
                "proposed_turn": 6,
                "accepted_turn": 7,
                "revises": None,
            },
        ]
        write_agreement_files(config)
        combined = (config.session_dir() / "agreements.md").read_text()
        assert "REST API." in combined
        assert "PostgreSQL." in combined
        assert "---" in combined

    def test_formats_revision(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "e9d4",
                "title": "Use PostgreSQL",
                "content": "Use PostgreSQL with Redis for caching and sessions.",
                "proposed_by": "a",
                "proposed_turn": 12,
                "accepted_turn": 13,
                "revises": "b7c1",
            }
        ]
        write_agreement_files(config)
        content = (config.session_dir() / "agreements.md").read_text()
        assert "b7c1" in content
        assert "e9d4" in content
        assert "revised" in content
        # Per-file should also exist
        per_file = config.session_dir() / "agreements" / "e9d4_use-postgresql.md"
        assert per_file.exists()
        assert "revised" in per_file.read_text()

    def test_removes_stale_files(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        agreements_dir = config.session_dir() / "agreements"
        agreements_dir.mkdir(parents=True, exist_ok=True)
        # Simulate a pre-existing file from a now-removed agreement
        (agreements_dir / "old1_stale-agreement.md").write_text("stale\n")
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        write_agreement_files(config)
        # Stale file should be removed
        assert not (agreements_dir / "old1_stale-agreement.md").exists()
        # Current file should exist
        assert (agreements_dir / "a3f2_use-rest.md").exists()


class TestFormatAgreementIndex:
    def test_empty_returns_empty(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        assert format_agreement_index(config) == ""

    def test_single_agreement(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            _make_agreement(content="REST API with pagination.")
        ]
        text = format_agreement_index(config)
        assert "1 confirmed agreement(s)" in text
        assert "[a3f2]" in text
        assert "**Use REST**" in text
        assert "Turn 4\u21925" in text
        assert "REST API with pagination." in text
        assert "File: agreements/a3f2_use-rest.md" in text

    def test_multiple_agreements(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            _make_agreement(),
            _make_agreement(
                id="b4c3",
                title="Use Redis",
                content="Redis for caching.",
                proposed_by="b",
                proposed_turn=6,
                accepted_turn=7,
            ),
        ]
        text = format_agreement_index(config)
        assert "2 confirmed agreement(s)" in text
        assert "[a3f2]" in text
        assert "[b4c3]" in text
        assert "File: agreements/a3f2_use-rest.md" in text
        assert "File: agreements/b4c3_use-redis.md" in text

    def test_superseded_agreement_marked(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=5)
        # Original + revision: a3f2 is superseded by b4c3
        config.accepted_agreements = [
            _make_agreement(id="a3f2", title="Use REST"),
            _make_agreement(
                id="b4c3",
                title="Use REST (revised)",
                proposed_turn=6,
                accepted_turn=7,
                revises="a3f2",
            ),
        ]
        text = format_agreement_index(config)
        # Count: 1 active, 2 total
        assert "1 active agreement(s)" in text
        assert "2 total" in text
        # Superseded entry marked with strikethrough
        assert "~~[a3f2]~~" in text
        assert "superseded by [b4c3]" in text
        # Revision entry uses arrow notation
        assert "[a3f2 \u2192 b4c3]" in text
        # File path present for active agreement
        assert "File: agreements/b4c3" in text

    def test_fallback_summary_extraction(self, make_config):
        """Index falls back to _extract_summary when summary key is missing."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "## REST endpoint design\nWith pagination.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        text = format_agreement_index(config)
        assert "REST endpoint design" in text


class TestFormatAgreementsForCompilation:
    def test_empty_returns_empty(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        assert format_agreements_for_compilation(config) == ""

    def test_includes_full_content(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API with pagination and rate limiting.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        text = format_agreements_for_compilation(config)
        assert "[a3f2]" in text
        assert "Use REST" in text
        assert "REST API with pagination and rate limiting." in text
        assert "Agent A" in text
        assert "Turn 4" in text

    def test_formats_revision(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "e9d4",
                "title": "Use PostgreSQL",
                "content": "PostgreSQL with Redis.",
                "proposed_by": "a",
                "proposed_turn": 12,
                "accepted_turn": 13,
                "revises": "b7c1",
            }
        ]
        text = format_agreements_for_compilation(config)
        assert "b7c1" in text
        assert "e9d4" in text
        assert "revised" in text
        assert "PostgreSQL with Redis." in text

    def test_multiple_separated_by_dividers(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            },
            {
                "id": "b4c3",
                "title": "Use Redis",
                "content": "Redis for caching.",
                "proposed_by": "b",
                "proposed_turn": 6,
                "accepted_turn": 7,
                "revises": None,
            },
        ]
        text = format_agreements_for_compilation(config)
        assert "---" in text
        assert "REST API." in text
        assert "Redis for caching." in text


class TestFormatAgreementsForPrompt:
    def test_empty_returns_empty_string(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        assert format_agreements_for_prompt(config, "a") == ""

    def test_confirmed_uses_compact_index(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            _make_agreement(content="REST API with pagination and lots of detail here.")
        ]
        text = format_agreements_for_prompt(config, "b")
        assert "# Shared Agreements" in text
        assert "## Confirmed" in text
        assert "[a3f2]" in text
        assert "Use REST" in text
        # Index line contains summary
        assert "1 confirmed agreement(s)" in text
        # Full content should NOT be in the prompt as a separate indented block
        assert "  REST API with pagination" not in text

    def test_confirmed_no_full_content_in_prompt(self, make_config):
        """Verify the prompt does not embed full agreement content."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        long_content = "Detailed agreement content. " * 50
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": long_content,
                "summary": "Detailed agreement content.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        text = format_agreements_for_prompt(config, "b")
        # The full long content should not appear
        assert long_content not in text
        # But the summary should appear in the index line
        assert "Detailed agreement content." in text

    def test_file_reference_included(self, make_config):
        """File reference tells agents to Read per-agreement files."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [_make_agreement()]
        text = format_agreements_for_prompt(config, "b")
        assert "agreements/" in text
        assert "Read tool" in text
        # Index lines include per-file paths
        assert "File: agreements/a3f2_use-rest.md" in text

    def test_pending_proposals_shown_to_other_agent(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [_make_proposal(content="Add a GraphQL gateway.")]
        # Agent B should see Agent A's proposal
        text = format_agreements_for_prompt(config, "b")
        assert "Pending Proposals" in text
        assert "[c4e8]" in text
        assert "Add GraphQL" in text
        assert '[ACCEPT id="c4e8"]' in text
        # Full content of pending proposals IS included
        assert "Add a GraphQL gateway." in text

    def test_pending_proposals_show_revise_option(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [_make_proposal(content="Add a GraphQL gateway.")]
        text = format_agreements_for_prompt(config, "b")
        assert '[REVISE id="c4e8"]' in text
        assert "[/REVISE]" in text

    def test_pending_not_shown_to_proposer_as_action_item(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [_make_proposal(content="Add a GraphQL gateway.")]
        # Agent A should NOT see their own proposal as something requiring their action
        text = format_agreements_for_prompt(config, "a")
        assert "awaiting your response" not in text
        # But they SHOULD see it as a reminder that the other agent hasn't responded yet
        assert "Your Pending Proposals" in text
        assert "Add GraphQL" in text

    def test_both_confirmed_and_pending(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [_make_agreement()]
        config.pending_proposals = [
            _make_proposal(title="Add caching", content="Use Redis.")
        ]
        text = format_agreements_for_prompt(config, "b")
        assert "## Confirmed" in text
        assert "## Pending Proposals" in text

    def test_nudge_after_warmup(self, make_config):
        """After turn 3 with no agreements, agents see a nudge."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        text = format_agreements_for_prompt(config, "a", current_turn=3)
        assert "No agreements yet" in text
        assert "[PROPOSE]" in text
        assert "verbal agreement alone" in text

    def test_no_nudge_during_warmup(self, make_config):
        """During turns 1-2, no nudge is shown."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        text = format_agreements_for_prompt(config, "a", current_turn=2)
        assert text == ""

    def test_no_nudge_without_current_turn(self, make_config):
        """Backward compat: no current_turn returns empty string."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        text = format_agreements_for_prompt(config, "a")
        assert text == ""

    def test_stale_agreement_nudge(self, make_config):
        """When last agreement was 4+ turns ago, show a reminder."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [_make_agreement()]
        text = format_agreements_for_prompt(config, "b", current_turn=9)
        assert "## Confirmed" in text
        assert "several turns since the last agreement" in text
        assert "[PROPOSE]" in text

    def test_no_stale_nudge_when_recent(self, make_config):
        """No stale nudge when last agreement was recent."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [_make_agreement()]
        text = format_agreements_for_prompt(config, "b", current_turn=7)
        assert "several turns since the last agreement" not in text

    def test_seen_pending_proposal_shows_revise_hint(self, make_config):
        """Already-seen pending proposals include REVISE reminder."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [_make_proposal(content="Add a GraphQL gateway.")]
        watermark = {"agreement_count": 0, "seen_proposal_ids": ["c4e8"]}
        text = format_agreements_for_prompt(config, "b", watermark=watermark)
        assert "(still pending" in text
        assert "REVISE" in text
        # Full content should NOT be shown for already-seen proposals
        assert "Add a GraphQL gateway." not in text

    def test_new_pending_proposal_revise_placeholder_style(self, make_config):
        """New pending proposals use '...revised content...' placeholder."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [_make_proposal(content="Add a GraphQL gateway.")]
        text = format_agreements_for_prompt(config, "b")
        assert "...revised content..." in text
        assert "improved content" not in text

    def test_own_pending_shown_to_proposer(self, make_config):
        """Proposer sees their own pending proposals as a reminder."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [_make_proposal(proposed_by="a", turn=3)]
        text = format_agreements_for_prompt(config, "a")
        assert "Your Pending Proposals" in text
        assert "awaiting Agent B" in text
        assert "[c4e8]" in text
        assert "Add GraphQL" in text

    def test_own_pending_not_shown_to_other_agent(self, make_config):
        """Other agent does not see the 'Your Pending Proposals' section."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [_make_proposal(proposed_by="a", turn=3)]
        text = format_agreements_for_prompt(config, "b")
        assert "Your Pending Proposals" not in text
        # The other agent DOES see it as an action item
        assert "awaiting your response" in text

    def test_rejected_proposals_shown_in_prompt(self, make_config):
        """Rejected proposals appear in the prompt for both agents."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=5)
        config.accepted_agreements = [_make_agreement()]
        config.rejected_proposals = [
            {
                "id": "d1e2",
                "title": "Use SOAP",
                "proposed_by": "a",
                "proposed_turn": 3,
                "rejected_turn": 4,
                "reason": "Too verbose",
            }
        ]
        # Proposer sees it as "your proposal"
        text_a = format_agreements_for_prompt(config, "a")
        assert "Recent Rejections" in text_a
        assert "[d1e2]" in text_a
        assert "your proposal" in text_a
        assert "Too verbose" in text_a

        # Other agent sees it attributed correctly
        text_b = format_agreements_for_prompt(config, "b")
        assert "Recent Rejections" in text_b
        assert "Agent A's proposal" in text_b

    def test_rejected_proposals_differential_via_watermark(self, make_config):
        """Watermark suppresses already-seen rejections."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=5)
        config.accepted_agreements = [_make_agreement()]
        config.rejected_proposals = [
            {
                "id": "d1e2",
                "title": "Use SOAP",
                "proposed_by": "a",
                "proposed_turn": 3,
                "rejected_turn": 4,
                "reason": "Too verbose",
            },
            {
                "id": "f3a4",
                "title": "Use XML",
                "proposed_by": "b",
                "proposed_turn": 5,
                "rejected_turn": 6,
                "reason": "Outdated",
            },
        ]
        # Watermark has seen 1 rejection — only the new one should appear
        watermark = {"agreement_count": 1, "seen_proposal_ids": [], "rejected_count": 1}
        text = format_agreements_for_prompt(config, "a", watermark=watermark)
        assert "Use XML" in text
        assert "Use SOAP" not in text

    def test_rejected_proposals_capped_at_five(self, make_config):
        """At most 5 rejections are shown at once."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=10)
        config.accepted_agreements = [_make_agreement()]
        for i in range(8):
            config.rejected_proposals.append(
                {
                    "id": f"r{i:03d}",
                    "title": f"Rejected Idea {i}",
                    "proposed_by": "a",
                    "proposed_turn": i,
                    "rejected_turn": i + 1,
                    "reason": f"reason {i}",
                }
            )
        text = format_agreements_for_prompt(config, "a")
        # The 5 most recent (indices 3-7) should appear; earlier ones should not
        assert "Rejected Idea 7" in text
        assert "Rejected Idea 3" in text
        assert "Rejected Idea 2" not in text

    def test_no_rejected_section_when_empty(self, make_config):
        """No 'Recent Rejections' heading when rejected_proposals is empty."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=5)
        config.accepted_agreements = [_make_agreement()]
        text = format_agreements_for_prompt(config, "a")
        assert "Recent Rejections" not in text


class TestConfigLoadSummaryBackfill:
    def test_backfills_agreement_summary(self, tmp_storms):
        """Legacy agreements without summary get backfilled on load."""
        session_id = "legacy-test"
        session_dir = tmp_storms / session_id
        session_dir.mkdir()
        data = {
            "session_id": session_id,
            "topic": "Test",
            "storms_dir": str(tmp_storms),
            "accepted_agreements": [
                {
                    "id": "a3f2",
                    "title": "Use REST",
                    "content": "## REST Design\nWith pagination.",
                    "proposed_by": "a",
                    "proposed_turn": 4,
                    "accepted_turn": 5,
                    "revises": None,
                }
            ],
            "pending_proposals": [
                {
                    "id": "b4c3",
                    "title": "Add Cache",
                    "content": "Use Redis for caching",
                    "proposed_by": "b",
                    "turn": 6,
                }
            ],
        }
        (session_dir / "session.json").write_text(json.dumps(data, indent=2) + "\n")
        config = SessionConfig.load(session_id, storms_dir=str(tmp_storms))
        assert config.accepted_agreements[0]["summary"] == "REST Design"
        assert config.pending_proposals[0]["summary"] == "Use Redis for caching"

    def test_backfills_original_content_fields_gracefully(self, tmp_storms):
        """Legacy revisions without original_content load without error."""
        session_id = "legacy-revision"
        session_dir = tmp_storms / session_id
        session_dir.mkdir()
        data = {
            "session_id": session_id,
            "topic": "Test",
            "storms_dir": str(tmp_storms),
            "accepted_agreements": [
                {
                    "id": "e9d4",
                    "title": "Use PostgreSQL",
                    "content": "PostgreSQL with Redis.",
                    "proposed_by": "a",
                    "proposed_turn": 12,
                    "accepted_turn": 13,
                    "revises": "b7c1",
                }
            ],
            "pending_proposals": [],
        }
        (session_dir / "session.json").write_text(json.dumps(data, indent=2) + "\n")
        config = SessionConfig.load(session_id, storms_dir=str(tmp_storms))
        # Should load without error; original_content not present
        assert config.accepted_agreements[0].get("original_content") is None

    def test_legacy_session_defaults_rejected_proposals(self, tmp_storms):
        """Legacy session JSON without rejected_proposals loads with empty list."""
        session_id = "legacy-no-rejections"
        session_dir = tmp_storms / session_id
        session_dir.mkdir()
        data = {
            "session_id": session_id,
            "topic": "Test",
            "storms_dir": str(tmp_storms),
            "accepted_agreements": [],
            "pending_proposals": [],
            # No rejected_proposals key — simulating pre-feature session
        }
        (session_dir / "session.json").write_text(json.dumps(data, indent=2) + "\n")
        config = SessionConfig.load(session_id, storms_dir=str(tmp_storms))
        assert config.rejected_proposals == []

    def test_preserves_existing_summary(self, tmp_storms):
        """Agreements with existing summary are not overwritten."""
        session_id = "existing-summary"
        session_dir = tmp_storms / session_id
        session_dir.mkdir()
        data = {
            "session_id": session_id,
            "topic": "Test",
            "storms_dir": str(tmp_storms),
            "accepted_agreements": [
                {
                    "id": "a3f2",
                    "title": "Use REST",
                    "content": "## REST Design\nWith pagination.",
                    "summary": "Custom summary",
                    "proposed_by": "a",
                    "proposed_turn": 4,
                    "accepted_turn": 5,
                    "revises": None,
                }
            ],
            "pending_proposals": [],
        }
        (session_dir / "session.json").write_text(json.dumps(data, indent=2) + "\n")
        config = SessionConfig.load(session_id, storms_dir=str(tmp_storms))
        assert config.accepted_agreements[0]["summary"] == "Custom summary"


class TestRevisionOriginalContent:
    """Tests for preserving original content through the revision pipeline."""

    def _assert_revision_ctx(self, ctx, title, content, turn, agent):
        """Assert a RevisionContext matches expected original values."""
        assert ctx is not None
        assert ctx.title == title
        assert ctx.original_content == content
        assert ctx.original_turn == turn
        assert ctx.original_agent == agent

    def test_create_proposal_stores_original_content(self, make_config):
        config = make_config(session_id="rev-test", max_turns=20, current_turn=5)
        revision = RevisionContext(
            revises="a3f2",
            title="Use REST v2",
            original_content="REST API with pagination.",
            original_turn=4,
            original_agent="a",
        )
        create_proposal(
            config,
            "Use REST v2",
            "REST with caching",
            "b",
            6,
            revision=revision,
        )
        proposal = config.pending_proposals[0]
        assert proposal["original_content"] == "REST API with pagination."
        assert proposal["original_turn"] == 4
        assert proposal["original_agent"] == "a"
        assert proposal["revises"] == "a3f2"

    def test_create_proposal_without_original_content(self, make_config):
        """When original_content is not provided, keys are absent (not None)."""
        config = make_config(session_id="rev-test", max_turns=20, current_turn=5)
        create_proposal(config, "Use REST", "REST is good", "a", 4)
        proposal = config.pending_proposals[0]
        assert "original_content" not in proposal
        assert "original_turn" not in proposal

    def test_accept_revision_carries_original_content(self, make_config):
        config = make_config(session_id="rev-test", max_turns=20, current_turn=5)
        revision = RevisionContext(
            revises="a3f2",
            title="Use REST v2",
            original_content="REST API with pagination.",
            original_turn=4,
            original_agent="a",
        )
        pid = create_proposal(
            config,
            "Use REST v2",
            "REST with caching",
            "b",
            6,
            revision=revision,
        )
        accepted = accept_proposal(config, pid, 7)
        assert accepted["original_content"] == "REST API with pagination."
        assert accepted["original_turn"] == 4
        assert accepted["original_agent"] == "a"

    def test_revision_agreement_file_contains_both_sections(self, make_config):
        """Accepted revision renders original + revision in agreement file."""
        config = make_config(session_id="rev-test", max_turns=20, current_turn=5)
        revision = RevisionContext(
            revises="9235",
            title="Chapter Outline",
            original_content=(
                "# Act 1\n\nCh 0: Prologue\nCh 1: Introduction\nCh 3: Original"
            ),
            original_turn=5,
            original_agent="a",
        )
        pid = create_proposal(
            config,
            "Chapter Outline",
            "All chapters remain with revisions to Ch 3 and Ch 7.",
            "b",
            6,
            revision=revision,
        )
        accept_proposal(config, pid, 7)

        per_file = config.session_dir() / "agreements" / f"{pid}_chapter-outline.md"
        content = per_file.read_text()
        # Header shows revision chain
        assert "9235" in content
        assert pid in content
        assert "revised" in content
        # Both sections present
        assert "### Original proposal" in content
        assert "Ch 0: Prologue" in content
        assert "### Revisions" in content
        assert "All chapters remain" in content
        # Metadata uses original_turn, not the revises ID
        assert "Turn 5 by Agent A" in content

    def test_revision_without_original_content_renders_normally(self, make_config):
        """Legacy revision (no original_content) still renders without error."""
        config = make_config(session_id="rev-test", max_turns=20, current_turn=5)
        config.accepted_agreements = [
            {
                "id": "e9d4",
                "title": "Use PostgreSQL",
                "content": "PostgreSQL with Redis.",
                "proposed_by": "a",
                "proposed_turn": 12,
                "accepted_turn": 13,
                "revises": "b7c1",
            }
        ]
        write_agreement_files(config)
        content = (config.session_dir() / "agreements.md").read_text()
        assert "revised" in content
        assert "PostgreSQL with Redis." in content
        # No "Original proposal" section when original_content is absent
        assert "### Original proposal" not in content
        # original_turn fallback to '?'
        assert "Turn ?" in content

    def test_revision_of_accepted_agreement_preserves_content(self, make_config):
        """Revising an already-accepted agreement captures its content."""
        config = make_config(session_id="rev-test", max_turns=20, current_turn=5)
        orig_id = create_proposal(
            config, "API Design", "Use REST with JSON responses.", "a", 4
        )
        accept_proposal(config, orig_id, 5)

        display = MagicMock()
        ctx = _resolve_revision_context(config, orig_id, "b", display)
        self._assert_revision_ctx(
            ctx,
            "API Design",
            "Use REST with JSON responses.",
            4,
            "a",
        )

    def test_revision_of_pending_proposal_preserves_content(self, make_config):
        """Revising a pending proposal captures the original proposal's content."""
        config = make_config(session_id="rev-test", max_turns=20, current_turn=5)
        orig_id = create_proposal(
            config, "API Design", "Use REST with JSON responses.", "a", 4
        )

        display = MagicMock()
        ctx = _resolve_revision_context(config, orig_id, "b", display)
        self._assert_revision_ctx(
            ctx,
            "API Design",
            "Use REST with JSON responses.",
            4,
            "a",
        )
        assert len(config.pending_proposals) == 0

    def test_chained_revision_preserves_root_original(self, make_config):
        """Revising a revision (A->B->C) preserves the root original content."""
        config = make_config(session_id="rev-test", max_turns=20, current_turn=5)
        orig_id = create_proposal(config, "API Design", "v1: Use REST.", "a", 4)
        accept_proposal(config, orig_id, 5)
        revision = RevisionContext(
            revises=orig_id,
            title="API Design",
            original_content="v1: Use REST.",
            original_turn=4,
            original_agent="a",
        )
        rev1_id = create_proposal(
            config,
            "API Design",
            "v2: REST with caching.",
            "b",
            6,
            revision=revision,
        )
        accept_proposal(config, rev1_id, 7)

        display = MagicMock()
        ctx = _resolve_revision_context(config, rev1_id, "a", display)
        self._assert_revision_ctx(ctx, "API Design", "v1: Use REST.", 4, "a")
