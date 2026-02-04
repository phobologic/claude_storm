"""Tests for prompt construction."""

from claude_storm.config import SessionConfig
from claude_storm.project import format_pacing_block
from claude_storm.prompts import (
    build_system_prompt,
    build_turn_prompt,
    build_summary_prompt,
    build_deliverable_prompt,
)


def _make_config(**kwargs):
    defaults = dict(
        session_id="test",
        topic="Design an API",
        goal="RESTful todo app",
        role_a="Architect",
        role_b="Critic",
        claude_session_a="a-uuid",
        claude_session_b="b-uuid",
        max_turns=10,
        current_turn=0,
        auto_complete=False,
        interactive=False,
        model="sonnet",
        status="active",
        deliverables=[],
    )
    defaults.update(kwargs)
    return SessionConfig(**defaults)


class TestBuildSystemPrompt:
    def test_includes_role(self):
        config = _make_config()
        prompt = build_system_prompt(config, "a")
        assert "Architect" in prompt

    def test_includes_topic(self):
        config = _make_config()
        prompt = build_system_prompt(config, "a")
        assert "Design an API" in prompt

    def test_includes_goal(self):
        config = _make_config()
        prompt = build_system_prompt(config, "a")
        assert "RESTful todo app" in prompt

    def test_includes_directives(self):
        config = _make_config()
        prompt = build_system_prompt(config, "a")
        assert "[MEMORY" in prompt
        assert "[ARTIFACT" in prompt
        assert "[DONE" in prompt
        assert "[PROPOSE" in prompt
        assert "[ACCEPT" in prompt
        assert "[REJECT" in prompt
        assert "[REVISE" in prompt

    def test_includes_agreement_guidelines(self):
        config = _make_config()
        prompt = build_system_prompt(config, "a")
        assert "shared agreement" in prompt
        assert "pending proposals" in prompt
        assert "Verbal agreement" in prompt
        assert "does NOT create a shared record" in prompt

    def test_ask_user_shown_when_interactive(self):
        config = _make_config(interactive=True)
        prompt = build_system_prompt(config, "a")
        assert "[ASK_USER]" in prompt
        assert "human operator is available" in prompt

    def test_ask_user_hidden_when_not_interactive(self):
        config = _make_config(interactive=False)
        prompt = build_system_prompt(config, "a")
        assert "[ASK_USER]" not in prompt

    def test_interactive_guideline_shown(self):
        config = _make_config(interactive=True)
        prompt = build_system_prompt(config, "a")
        assert "uncertain about a direction" in prompt

    def test_interactive_guideline_hidden(self):
        config = _make_config(interactive=False)
        prompt = build_system_prompt(config, "a")
        assert "uncertain about a direction" not in prompt

    def test_nudge_guidance_shown_when_interactive(self):
        config = _make_config(interactive=True)
        prompt = build_system_prompt(config, "a")
        assert "nudge" in prompt.lower()
        assert "steering guidance" in prompt

    def test_nudge_guidance_hidden_when_not_interactive(self):
        config = _make_config(interactive=False)
        prompt = build_system_prompt(config, "a")
        assert "steering guidance" not in prompt

    def test_no_role_uses_default(self):
        config = _make_config(role_a=None)
        prompt = build_system_prompt(config, "a")
        assert "brainstorming partner" in prompt

    def test_mentions_other_agent(self):
        config = _make_config()
        prompt = build_system_prompt(config, "a")
        assert "Critic" in prompt  # The other agent's role

    def test_system_prompt_includes_deliverables(self):
        config = _make_config(deliverables=["Doc A", "Doc B"])
        prompt = build_system_prompt(config, "a")
        assert "Expected Deliverables" in prompt
        assert "Doc A" in prompt
        assert "Doc B" in prompt

    def test_system_prompt_no_deliverables(self):
        config = _make_config(goal="", deliverables=[])
        prompt = build_system_prompt(config, "a")
        assert "Expected Deliverables" not in prompt
        assert "Session Structure" not in prompt

    def test_system_prompt_includes_pacing_overview(self):
        config = _make_config(deliverables=["Doc A"])
        prompt = build_system_prompt(config, "a")
        assert "budget of 10 turns" in prompt
        assert "Pace yourself" in prompt
        assert "incrementally" in prompt
        assert "[ARTIFACT]" in prompt

    def test_system_prompt_includes_reference_dirs(self):
        config = _make_config(reference_dirs=["/tmp/notes"])
        prompt = build_system_prompt(config, "a")
        assert "Reference Materials" in prompt
        assert "/tmp/notes" in prompt
        assert "read-only" in prompt

    def test_system_prompt_multiple_reference_dirs(self):
        config = _make_config(reference_dirs=["/tmp/notes", "/tmp/docs"])
        prompt = build_system_prompt(config, "a")
        assert "Reference Materials" in prompt
        assert "/tmp/notes" in prompt
        assert "/tmp/docs" in prompt

    def test_system_prompt_no_reference_dirs(self):
        config = _make_config()
        prompt = build_system_prompt(config, "a")
        assert "Reference Materials" not in prompt


class TestBuildTurnPrompt:
    def test_first_turn_agent_a(self):
        config = _make_config(current_turn=0)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "start of the conversation" in prompt
        assert "Turn 1 of 10" in prompt

    def test_includes_other_response(self):
        config = _make_config(current_turn=2)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="I think we should use pagination",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "I think we should use pagination" in prompt

    def test_includes_memory_index(self):
        config = _make_config(current_turn=3)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index='You have 2 saved note(s):\n- "Note 1" [tag1]',
            recent_memories="",
        )
        assert "Memory Index" in prompt
        assert '"Note 1"' in prompt

    def test_includes_search_results(self):
        config = _make_config(current_turn=3)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
            search_results='Results for "auth": ## Auth Notes\ncontent',
        )
        assert "Search Results" in prompt
        assert "Auth Notes" in prompt

    def test_includes_user_input(self):
        config = _make_config(current_turn=3)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
            user_input="Use JWT tokens",
        )
        assert "User Input" in prompt
        assert "Use JWT tokens" in prompt

    def test_auto_complete_message(self):
        config = _make_config(auto_complete=True)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "[DONE]" in prompt

    def test_turn_prompt_shows_percentage(self):
        config = _make_config(current_turn=2, max_turns=20)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "15%" in prompt
        assert "Turn 3 of 20" in prompt

    def test_turn_prompt_halfway_nudge(self):
        config = _make_config(current_turn=9, max_turns=20)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "halfway" in prompt

    def test_turn_prompt_final_nudge(self):
        config = _make_config(current_turn=18, max_turns=20)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "final turns" in prompt

    def test_turn_prompt_deliverables_reminder(self):
        config = _make_config(
            current_turn=3,
            deliverables=["Architecture doc", "Data model"],
        )
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "Expected deliverables" in prompt
        assert "Architecture doc" in prompt
        assert "Data model" in prompt


    def test_completion_check_shown_when_other_done(self):
        config = _make_config(
            auto_complete=True,
            done_signals={"a": "All topics covered"},
        )
        prompt = build_turn_prompt(
            config=config,
            agent="b",
            other_response="I think we're done.",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "Completion Check" in prompt
        assert "All topics covered" in prompt
        assert "If you agree, signal [DONE]" in prompt
        # Should NOT show the generic DONE hint
        assert "Signal [DONE] when you believe" not in prompt

    def test_no_completion_check_when_no_pending_done(self):
        config = _make_config(auto_complete=True)
        prompt = build_turn_prompt(
            config=config,
            agent="b",
            other_response="Let's keep going.",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "Completion Check" not in prompt
        assert "Signal [DONE] when you believe" in prompt

    def test_includes_agreements_text(self):
        config = _make_config(current_turn=5)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
            agreements_text="# Shared Agreements\n\n## Confirmed\n- [a3f2] **Use REST**",
        )
        assert "Shared Agreements" in prompt
        assert "[a3f2]" in prompt
        assert "Use REST" in prompt

    def test_no_agreements_text_when_empty(self):
        config = _make_config(current_turn=5)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
            agreements_text="",
        )
        assert "Shared Agreements" not in prompt

    def test_interactive_reminder_shown(self):
        config = _make_config(interactive=True, current_turn=3)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "interactive mode" in prompt
        assert "[ASK_USER]" in prompt

    def test_interactive_reminder_hidden(self):
        config = _make_config(interactive=False, current_turn=3)
        prompt = build_turn_prompt(
            config=config,
            agent="a",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "interactive mode" not in prompt

    def test_completion_check_not_shown_without_auto_complete(self):
        config = _make_config(
            auto_complete=False,
            done_signals={"a": "Done"},
        )
        prompt = build_turn_prompt(
            config=config,
            agent="b",
            other_response="response",
            memory_index="You have no saved notes.",
            recent_memories="",
        )
        assert "Completion Check" not in prompt


class TestBuildSummaryPrompt:
    def test_includes_topic_and_turns(self):
        config = _make_config(current_turn=8)
        prompt = build_summary_prompt(config)
        assert "Design an API" in prompt
        assert "8 turns" in prompt
        assert "summary" in prompt.lower()

    def test_summary_prompt_deliverables(self):
        config = _make_config(
            current_turn=8,
            deliverables=["Doc A", "Doc B"],
        )
        prompt = build_summary_prompt(config)
        assert "deliverables were expected" in prompt
        assert "Doc A" in prompt
        assert "Doc B" in prompt
        assert "completeness" in prompt


class TestBuildDeliverablePrompt:
    def test_includes_deliverable_name(self):
        config = _make_config()
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Chapter Summaries",
            memories_text="memory content",
            conversation_text="conversation content",
        )
        assert "Chapter Summaries" in prompt

    def test_includes_topic(self):
        config = _make_config()
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text="conversation",
        )
        assert "Design an API" in prompt

    def test_includes_memories_and_conversation(self):
        config = _make_config()
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="key insight about caching",
            conversation_text="turn 1: discussed caching",
        )
        assert "key insight about caching" in prompt
        assert "turn 1: discussed caching" in prompt

    def test_includes_agreements_text(self):
        config = _make_config()
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text="conversation",
            agreements_text="[a3f2] Use REST API",
        )
        assert "Shared Agreements" in prompt
        assert "[a3f2] Use REST API" in prompt

    def test_includes_no_write_instruction(self):
        config = _make_config()
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text="conversation",
        )
        assert "Output the full deliverable content directly" in prompt
        assert "Do NOT use Write or Edit tools" in prompt

    def test_no_agreements_section_when_empty(self):
        config = _make_config()
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text="conversation",
            agreements_text="",
        )
        assert "Shared Agreements" not in prompt

    def test_includes_existing_artifacts(self):
        config = _make_config()
        artifacts = {
            "chapter_1.md": "# Chapter 1\nContent here",
            "chapter_2.md": "# Chapter 2\nMore content",
        }
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Chapters",
            memories_text="memories",
            conversation_text="conversation",
            existing_artifacts=artifacts,
        )
        assert "Draft Content" in prompt
        assert "chapter_1.md" in prompt
        assert "# Chapter 1" in prompt
        assert "chapter_2.md" in prompt
        assert "refine" in prompt.lower()

    def test_no_draft_section_without_artifacts(self):
        config = _make_config()
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text="conversation",
        )
        assert "Draft Content" not in prompt

    def test_truncation_when_conversation_exceeds_threshold(self):
        config = _make_config(truncate_conversation=True)
        long_conversation = "x" * 60_000
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text=long_conversation,
        )
        assert "[...earlier conversation truncated...]" in prompt
        # Memories and agreements should be fully included regardless
        assert "memories" in prompt

    def test_no_truncation_when_under_threshold(self):
        config = _make_config(truncate_conversation=True)
        short_conversation = "x" * 1000
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text=short_conversation,
        )
        assert "truncated" not in prompt

    def test_no_truncation_when_disabled(self):
        config = _make_config(truncate_conversation=False)
        long_conversation = "x" * 60_000
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text=long_conversation,
        )
        assert "truncated" not in prompt
        assert len(prompt) > 60_000


class TestEarlyPhasePacing:
    def test_early_phase_nudge_interactive(self):
        """At <=20% with interactive=True, should mention ASK_USER."""
        result = format_pacing_block(turn=2, max_turns=20, interactive=True)
        assert "[ASK_USER]" in result
        assert "Early exploration phase" in result

    def test_early_phase_no_nudge_non_interactive(self):
        """At <=20% with interactive=False, should NOT mention ASK_USER."""
        result = format_pacing_block(turn=2, max_turns=20, interactive=False)
        assert "[ASK_USER]" not in result
        assert "Continue the brainstorm" in result

    def test_past_early_phase_interactive(self):
        """At >20% with interactive=True, should show generic message."""
        result = format_pacing_block(turn=8, max_turns=20, interactive=True)
        assert "[ASK_USER]" not in result
        assert "Continue the brainstorm" in result

    def test_boundary_20_percent(self):
        """At exactly 20%, should still show early-phase nudge if interactive."""
        result = format_pacing_block(turn=4, max_turns=20, interactive=True)
        assert "Early exploration phase" in result

    def test_system_prompt_interactive_pacing(self):
        """Interactive system prompt should mention early-turn clarification."""
        config = _make_config(interactive=True, deliverables=["Doc A"])
        prompt = build_system_prompt(config, "a")
        assert "clarify goals and constraints" in prompt
        assert "[ASK_USER]" in prompt

    def test_system_prompt_non_interactive_pacing(self):
        """Non-interactive system prompt should NOT mention early clarification."""
        config = _make_config(interactive=False, deliverables=["Doc A"])
        prompt = build_system_prompt(config, "a")
        assert "clarify goals and constraints" not in prompt


class TestGoalThreading:
    def test_summary_prompt_includes_goal(self):
        config = _make_config(goal="Favor battle-tested tech", current_turn=8)
        prompt = build_summary_prompt(config)
        assert "Favor battle-tested tech" in prompt
        assert "Goal assessment" in prompt

    def test_summary_prompt_no_goal(self):
        config = _make_config(goal="", current_turn=8)
        prompt = build_summary_prompt(config)
        assert "Goal assessment" not in prompt

    def test_deliverable_prompt_includes_goal(self):
        config = _make_config(goal="Production-ready designs")
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Architecture doc",
            memories_text="memories",
            conversation_text="conversation",
        )
        assert "Production-ready designs" in prompt

    def test_deliverable_prompt_no_goal(self):
        config = _make_config(goal="")
        prompt = build_deliverable_prompt(
            config=config,
            deliverable_name="Doc",
            memories_text="memories",
            conversation_text="conversation",
        )
        assert "Session goal" not in prompt

    def test_pacing_block_includes_goal_at_50_pct(self):
        result = format_pacing_block(
            turn=10, max_turns=20, goal="Favor simplicity"
        )
        assert "Favor simplicity" in result
        assert "Keep the session goal in mind" in result

    def test_pacing_block_includes_goal_at_75_pct(self):
        result = format_pacing_block(
            turn=15, max_turns=20, goal="Favor simplicity"
        )
        assert "Favor simplicity" in result
        assert "Ensure output addresses the session goal" in result

    def test_pacing_block_includes_goal_at_final_turns(self):
        result = format_pacing_block(
            turn=19, max_turns=20, goal="Favor simplicity"
        )
        assert "Favor simplicity" in result
        assert "ensure final output addresses this" in result

    def test_pacing_block_goal_bottom_reminder_no_deliverables(self):
        result = format_pacing_block(
            turn=5, max_turns=20, goal="Favor simplicity"
        )
        assert "**Session goal:** Favor simplicity" in result

    def test_pacing_block_no_goal_bottom_reminder_with_deliverables(self):
        result = format_pacing_block(
            turn=5, max_turns=20, deliverables=["Doc A"], goal="Favor simplicity"
        )
        assert "**Expected deliverables:**" in result
        assert "**Session goal:**" not in result

    def test_system_prompt_session_structure_shows_goal(self):
        config = _make_config(goal="Favor simplicity", deliverables=["Doc A"])
        prompt = build_system_prompt(config, "a")
        assert "Session Structure" in prompt
        assert "**Session goal:** Favor simplicity" in prompt
