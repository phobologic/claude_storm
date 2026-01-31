"""Tests for prompt construction."""

from claude_storm.config import SessionConfig
from claude_storm.prompts import (
    build_system_prompt,
    build_turn_prompt,
    build_summary_prompt,
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
        assert "[ASK_USER]" in prompt

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
        assert "Expected deliverables" in prompt
        assert "Doc A" in prompt
        assert "Doc B" in prompt

    def test_system_prompt_no_deliverables(self):
        config = _make_config(goal="", deliverables=[])
        prompt = build_system_prompt(config, "a")
        assert "Expected deliverables" not in prompt
        assert "Session Structure" not in prompt

    def test_system_prompt_includes_pacing_overview(self):
        config = _make_config(deliverables=["Doc A"])
        prompt = build_system_prompt(config, "a")
        assert "budget of 10 turns" in prompt
        assert "Pace yourself" in prompt


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
        assert "TURN 1 of 10" in prompt

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
        assert "MEMORY INDEX" in prompt
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
        assert "SEARCH RESULTS" in prompt
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
        assert "USER INPUT" in prompt
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
        assert "TURN 3 of 20" in prompt

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
