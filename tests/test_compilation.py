"""Tests for compilation module."""

from unittest.mock import patch

from claude_storm.agents import AgentResponse
from claude_storm.compilation import compile_deliverables, find_matching_artifacts


class TestFindMatchingArtifacts:
    """Tests for find_matching_artifacts."""

    def test_no_artifacts_dir(self, tmp_path):
        result = find_matching_artifacts(tmp_path / "nonexistent", "Design Doc")
        assert result == {}

    def test_no_match(self, tmp_path):
        tmp_path.joinpath("unrelated_file.md").write_text("content")
        result = find_matching_artifacts(tmp_path, "Design Document")
        assert result == {}

    def test_exact_match(self, tmp_path):
        tmp_path.joinpath("design_document.md").write_text("draft content")
        result = find_matching_artifacts(tmp_path, "Design Document")
        assert "design_document.md" in result
        assert result["design_document.md"] == "draft content"

    def test_partial_word_overlap(self, tmp_path):
        tmp_path.joinpath("api_documentation.md").write_text("api docs")
        result = find_matching_artifacts(tmp_path, "API Documentation Guide")
        assert "api_documentation.md" in result


class TestCompileDeliverables:
    """Tests for compile_deliverables."""

    def test_no_deliverables(self, make_config, capture_display):
        config = make_config(deliverables=[])
        display, _ = capture_display
        compile_deliverables(config, display)
        # Should return early without writing any artifacts
        artifacts_dir = config.session_dir() / "artifacts"
        assert not list(artifacts_dir.glob("*.md")) if artifacts_dir.exists() else True

    def test_preserves_agent_draft_on_compile(self, make_config, capture_display):
        """Compilation should rename existing agent draft to .draft.md."""
        config = make_config(deliverables=["Design Document"])
        display, _ = capture_display

        # Pre-create an agent-written artifact at the same slug
        artifacts_dir = config.session_dir() / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifacts_dir / "design_document.md"
        artifact_path.write_text("original agent draft\n")

        compiled_text = "polished final version"
        mock_response = AgentResponse(text=compiled_text, raw={}, is_error=False)

        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        # Compiled output takes the clean name
        assert artifact_path.read_text() == compiled_text + "\n"

        # Original agent draft preserved as .draft.md
        draft_path = artifacts_dir / "design_document.draft.md"
        assert draft_path.exists()
        assert draft_path.read_text() == "original agent draft\n"

    def test_no_draft_backup_when_no_preexisting(self, make_config, capture_display):
        """No .draft.md created when there's no pre-existing artifact."""
        config = make_config(deliverables=["New Document"])
        display, _ = capture_display

        mock_response = AgentResponse(text="fresh content", raw={}, is_error=False)

        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        artifacts_dir = config.session_dir() / "artifacts"
        assert (artifacts_dir / "new_document.md").read_text() == "fresh content\n"
        assert not (artifacts_dir / "new_document.draft.md").exists()

    def test_draft_backup_not_overwritten_on_second_compile(
        self, make_config, capture_display
    ):
        """If .draft.md already exists, don't overwrite it."""
        config = make_config(deliverables=["Design Document"])
        display, _ = capture_display

        artifacts_dir = config.session_dir() / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Simulate a previous compilation cycle
        (artifacts_dir / "design_document.md").write_text("first compiled\n")
        (artifacts_dir / "design_document.draft.md").write_text(
            "original agent draft\n"
        )

        mock_response = AgentResponse(text="second compiled", raw={}, is_error=False)

        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        # New compiled output written
        assert (artifacts_dir / "design_document.md").read_text() == "second compiled\n"

        # Original draft still preserved (not overwritten)
        assert (
            artifacts_dir / "design_document.draft.md"
        ).read_text() == "original agent draft\n"

    def test_error_response_skips_write(self, make_config, capture_display):
        """Failed compilation should not write or rename anything."""
        config = make_config(deliverables=["Design Document"])
        display, _ = capture_display

        artifacts_dir = config.session_dir() / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "design_document.md").write_text("agent draft\n")

        mock_response = AgentResponse(text="", raw={}, is_error=True)

        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        # Original untouched
        assert (artifacts_dir / "design_document.md").read_text() == "agent draft\n"
        assert not (artifacts_dir / "design_document.draft.md").exists()
