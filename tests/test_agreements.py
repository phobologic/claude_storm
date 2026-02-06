"""Tests for the shared agreements protocol."""

from claude_storm.agreements import (
    accept_proposal,
    create_proposal,
    format_agreements_for_prompt,
    generate_proposal_id,
    reject_proposal,
    write_agreements_file,
)


class TestGenerateProposalId:
    def test_returns_4_hex_chars(self):
        pid = generate_proposal_id()
        assert len(pid) == 4
        int(pid, 16)  # should not raise

    def test_unique_ids(self):
        ids = {generate_proposal_id() for _ in range(100)}
        assert len(ids) > 90  # statistically should all be unique


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
        assert len(config.pending_proposals) == 0
        assert len(config.accepted_agreements) == 1

    def test_writes_agreements_file(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        pid = create_proposal(config, "Use REST", "REST is good", "a", 4)
        accept_proposal(config, pid, 5)
        agreements_path = config.session_dir() / "agreements.md"
        assert agreements_path.exists()
        content = agreements_path.read_text()
        assert pid in content
        assert "Use REST" in content

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


class TestWriteAgreementsFile:
    def test_empty_agreements(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        write_agreements_file(config)
        path = config.session_dir() / "agreements.md"
        assert path.exists()
        assert path.read_text() == ""

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
        write_agreements_file(config)
        content = (config.session_dir() / "agreements.md").read_text()
        assert "b7c1" in content
        assert "e9d4" in content
        assert "revised" in content


class TestFormatAgreementsForPrompt:
    def test_empty_returns_empty_string(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        assert format_agreements_for_prompt(config, "a") == ""

    def test_confirmed_agreements(self, make_config):
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
            }
        ]
        text = format_agreements_for_prompt(config, "b")
        assert "# Shared Agreements" in text
        assert "## Confirmed" in text
        assert "[a3f2]" in text
        assert "Use REST" in text

    def test_pending_proposals_shown_to_other_agent(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [
            {
                "id": "c4e8",
                "title": "Add GraphQL",
                "content": "Add a GraphQL gateway.",
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

    def test_pending_not_shown_to_proposer(self, make_config):
        config = make_config(session_id="agree-test", max_turns=20, current_turn=3)
        config.pending_proposals = [
            {
                "id": "c4e8",
                "title": "Add GraphQL",
                "content": "Add a GraphQL gateway.",
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
        assert "No agreements have been formalized" in text
        assert "[PROPOSE" in text
        assert "Verbal agreement alone" in text

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
                "proposed_by": "a",
                "proposed_turn": 4,
                "accepted_turn": 5,
                "revises": None,
            }
        ]
        text = format_agreements_for_prompt(config, "b", current_turn=7)
        assert "several turns since the last agreement" not in text
