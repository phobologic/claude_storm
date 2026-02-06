"""Tests for the memory system."""

from claude_storm.memory import (
    format_memory_index,
    format_recent_memories,
    format_search_results,
    get_memory_index,
    get_recent_memories,
    save_memory,
    search_memory,
)


class TestSaveMemory:
    def test_saves_file_and_index(self, agent_a_dir):
        filename = save_memory(
            agent_a_dir, "API Design", ["api", "rest"], "Use REST endpoints"
        )
        assert filename == "001-api-design.md"

        mem_path = agent_a_dir / "memory" / filename
        assert mem_path.exists()
        assert "Use REST endpoints" in mem_path.read_text()

        index = get_memory_index(agent_a_dir)
        assert len(index) == 1
        assert index[0]["title"] == "API Design"
        assert index[0]["tags"] == ["api", "rest"]

    def test_auto_numbers(self, agent_a_dir):
        save_memory(agent_a_dir, "First", ["a"], "content 1")
        save_memory(agent_a_dir, "Second", ["b"], "content 2")
        save_memory(agent_a_dir, "Third", ["c"], "content 3")

        index = get_memory_index(agent_a_dir)
        assert len(index) == 3
        assert index[0]["filename"].startswith("001-")
        assert index[1]["filename"].startswith("002-")
        assert index[2]["filename"].startswith("003-")

    def test_creates_memory_dir_if_missing(self, tmp_path):
        agent_dir = tmp_path / "new-agent"
        save_memory(agent_dir, "Note", [], "hello")
        assert (agent_dir / "memory" / "_index.json").exists()


class TestGetRecentMemories:
    def test_returns_most_recent(self, agent_a_dir):
        save_memory(agent_a_dir, "First", [], "AAA")
        save_memory(agent_a_dir, "Second", [], "BBB")
        save_memory(agent_a_dir, "Third", [], "CCC")

        recent = get_recent_memories(agent_a_dir, n=2)
        assert len(recent) == 2
        assert recent[0][0] == "Third"
        assert recent[1][0] == "Second"

    def test_empty_index(self, agent_a_dir):
        assert get_recent_memories(agent_a_dir) == []


class TestSearchMemory:
    def test_matches_title(self, agent_a_dir):
        save_memory(agent_a_dir, "REST API Design", ["api"], "content")
        save_memory(agent_a_dir, "Database Schema", ["db"], "content")

        results = search_memory(agent_a_dir, "REST")
        assert len(results) == 1
        assert results[0][0] == "REST API Design"

    def test_matches_tags(self, agent_a_dir):
        save_memory(agent_a_dir, "Note A", ["security", "auth"], "content")
        save_memory(agent_a_dir, "Note B", ["database"], "content")

        results = search_memory(agent_a_dir, "security")
        assert len(results) == 1
        assert results[0][0] == "Note A"

    def test_no_match(self, agent_a_dir):
        save_memory(agent_a_dir, "Note", ["tag"], "content")
        assert search_memory(agent_a_dir, "nonexistent") == []

    def test_case_insensitive(self, agent_a_dir):
        save_memory(agent_a_dir, "REST API", ["api"], "content")
        results = search_memory(agent_a_dir, "rest api")
        assert len(results) == 1


class TestFormatMemoryIndex:
    def test_empty(self, agent_a_dir):
        result = format_memory_index(agent_a_dir)
        assert "no saved notes" in result

    def test_with_entries(self, agent_a_dir):
        save_memory(agent_a_dir, "API Design", ["api", "rest"], "content")
        save_memory(agent_a_dir, "Auth Notes", ["security"], "content")

        result = format_memory_index(agent_a_dir)
        assert "2 saved note(s)" in result
        assert '"API Design"' in result
        assert '"Auth Notes"' in result
        assert "api, rest" in result


class TestFormatRecentMemories:
    def test_empty(self, agent_a_dir):
        assert format_recent_memories(agent_a_dir) == ""

    def test_with_entries(self, agent_a_dir):
        save_memory(agent_a_dir, "My Note", ["tag"], "Some content here")
        result = format_recent_memories(agent_a_dir)
        assert "## My Note" in result
        assert "Some content here" in result


class TestFormatSearchResults:
    def test_no_results(self, agent_a_dir):
        result = format_search_results(agent_a_dir, "nothing")
        assert "No results found" in result

    def test_with_results(self, agent_a_dir):
        save_memory(agent_a_dir, "REST API", ["api"], "Design notes")
        result = format_search_results(agent_a_dir, "REST")
        assert "## REST API" in result
        assert "Design notes" in result
