"""Tests for the shared agreements protocol."""

import json

from claude_storm.agreements import (
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
        create_proposal(
            config, "Use REST v2", "REST with pagination", "b", 8, revises="a3f2"
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
        rev = create_proposal(
            config, "Use REST", "REST with caching", "b", 8, revises=orig
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
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API with pagination.",
                "summary": "REST API with pagination.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
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
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "summary": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            },
            {
                "id": "b4c3",
                "title": "Use Redis",
                "content": "Redis for caching.",
                "summary": "Redis for caching.",
                "proposed_by": "b",
                "proposed_turn": 6,
                "accepted_turn": 7,
                "revises": None,
            },
        ]
        text = format_agreement_index(config)
        assert "2 confirmed agreement(s)" in text
        assert "[a3f2]" in text
        assert "[b4c3]" in text
        assert "File: agreements/a3f2_use-rest.md" in text
        assert "File: agreements/b4c3_use-redis.md" in text

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
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API with pagination and lots of detail here.",
                "summary": "REST API with pagination and lots of detail here.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
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
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "summary": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        text = format_agreements_for_prompt(config, "b")
        assert "agreements/" in text
        assert "Read tool" in text
        # Index lines include per-file paths
        assert "File: agreements/a3f2_use-rest.md" in text

    def test_pending_proposals_shown_to_other_agent(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [
            {
                "id": "c4e8",
                "title": "Add GraphQL",
                "content": "Add a GraphQL gateway.",
                "summary": "Add a GraphQL gateway.",
                "proposed_by": "a",
                "turn": 9,
                "revises": None,
            }
        ]
        # Agent B should see Agent A's proposal
        text = format_agreements_for_prompt(config, "b")
        assert "Pending Proposals" in text
        assert "[c4e8]" in text
        assert "Add GraphQL" in text
        assert '[ACCEPT id="c4e8"]' in text
        # Full content of pending proposals IS included
        assert "Add a GraphQL gateway." in text

    def test_pending_not_shown_to_proposer(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [
            {
                "id": "c4e8",
                "title": "Add GraphQL",
                "content": "Add a GraphQL gateway.",
                "summary": "Add a GraphQL gateway.",
                "proposed_by": "a",
                "turn": 9,
                "revises": None,
            }
        ]
        # Agent A should NOT see their own pending proposal as awaiting response
        text = format_agreements_for_prompt(config, "a")
        assert "Pending Proposals" not in text

    def test_both_confirmed_and_pending(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "summary": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        config.pending_proposals = [
            {
                "id": "c4e8",
                "title": "Add caching",
                "content": "Use Redis.",
                "summary": "Use Redis.",
                "proposed_by": "a",
                "turn": 9,
                "revises": None,
            }
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
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "summary": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        text = format_agreements_for_prompt(config, "b", current_turn=9)
        assert "## Confirmed" in text
        assert "several turns since the last agreement" in text
        assert "[PROPOSE]" in text

    def test_no_stale_nudge_when_recent(self, make_config):
        """No stale nudge when last agreement was recent."""
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.accepted_agreements = [
            {
                "id": "a3f2",
                "title": "Use REST",
                "content": "REST API.",
                "summary": "REST API.",
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        text = format_agreements_for_prompt(config, "b", current_turn=7)
        assert "several turns since the last agreement" not in text


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
