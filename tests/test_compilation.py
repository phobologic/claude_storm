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
        tmp_path.joinpath("draft-design_document.md").write_text("draft content")
        result = find_matching_artifacts(tmp_path, "Design Document")
        assert "draft-design_document.md" in result
        assert result["draft-design_document.md"] == "draft content"

    def test_partial_word_overlap(self, tmp_path):
        tmp_path.joinpath("draft-api_documentation.md").write_text("api docs")
        result = find_matching_artifacts(tmp_path, "API Documentation Guide")
        assert "draft-api_documentation.md" in result

    def test_draft_prefix_stripped_for_matching(self, tmp_path):
        """draft-season_summary.md should match deliverable 'season_summary.md'."""
        tmp_path.joinpath("draft-season_summary.md").write_text("draft content")
        result = find_matching_artifacts(tmp_path, "season_summary.md")
        assert "draft-season_summary.md" in result
        assert result["draft-season_summary.md"] == "draft content"

    def test_extension_stripped_from_deliverable_name(self, tmp_path):
        """Deliverable 'season_summary.md' tokenizes as {season, summary}."""
        tmp_path.joinpath("draft-season_summary.md").write_text("content")
        result = find_matching_artifacts(tmp_path, "season_summary.md")
        assert "draft-season_summary.md" in result

    def test_underscore_suffix_not_stripped_as_extension(self, tmp_path):
        """'v2.0_plan' should not have '.0_pl' stripped by extension regex."""
        tmp_path.joinpath("draft-v2_0_plan.md").write_text("plan content")
        result = find_matching_artifacts(tmp_path, "v2.0_plan")
        assert "draft-v2_0_plan.md" in result

    def test_compiled_output_not_matched(self, tmp_path):
        """Compiled files (no draft- prefix) should not be matched."""
        tmp_path.joinpath("design_document.md").write_text("compiled content")
        result = find_matching_artifacts(tmp_path, "Design Document")
        assert result == {}

    def test_compiled_ignored_when_draft_exists(self, tmp_path):
        """Only draft files matched even when compiled output also exists."""
        tmp_path.joinpath("draft-design_document.md").write_text("draft")
        tmp_path.joinpath("design_document.md").write_text("compiled")
        result = find_matching_artifacts(tmp_path, "Design Document")
        assert "draft-design_document.md" in result
        assert "design_document.md" not in result


class TestCompileDeliverables:
    """Tests for compile_deliverables."""

    def test_no_deliverables(self, make_config, capture_display):
        config = make_config(deliverables=[])
        display, _ = capture_display
        compile_deliverables(config, display)
        # Should return early without writing any artifacts
        artifacts_dir = config.session_dir() / "artifacts"
        assert not list(artifacts_dir.glob("*.md")) if artifacts_dir.exists() else True

    def test_compiled_output_overwrites_without_backup(
        self, make_config, capture_display
    ):
        """Compilation writes to the clean name; no .draft.md backup needed."""
        config = make_config(deliverables=["Design Document"])
        display, _ = capture_display

        # Pre-create a draft-prefixed agent artifact
        artifacts_dir = config.session_dir() / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "draft-design_document.md").write_text("agent draft\n")

        compiled_text = "polished final version"
        mock_response = AgentResponse(text=compiled_text, raw={}, is_error=False)

        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        # Compiled output takes the clean name
        assert (
            artifacts_dir / "design_document.md"
        ).read_text() == compiled_text + "\n"

        # Draft file still exists (untouched)
        assert (
            artifacts_dir / "draft-design_document.md"
        ).read_text() == "agent draft\n"

    def test_no_draft_backup_when_no_preexisting(self, make_config, capture_display):
        """No .draft.md created when there's no pre-existing artifact."""
        config = make_config(deliverables=["New Document"])
        display, _ = capture_display

        mock_response = AgentResponse(text="fresh content", raw={}, is_error=False)

        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        artifacts_dir = config.session_dir() / "artifacts"
        assert (artifacts_dir / "new_document.md").read_text() == "fresh content\n"

    def test_extension_deliverable_produces_clean_filename(
        self, make_config, capture_display
    ):
        """Extension in deliverable name doesn't corrupt the filename."""
        config = make_config(deliverables=["season_summary.md"])
        display, _ = capture_display

        mock_response = AgentResponse(text="summary content", raw={}, is_error=False)

        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        artifacts_dir = config.session_dir() / "artifacts"
        assert (artifacts_dir / "season_summary.md").exists()
        assert not (artifacts_dir / "season_summarymd.md").exists()

    def test_error_response_skips_write(self, make_config, capture_display):
        """Failed compilation should not write anything."""
        config = make_config(deliverables=["Design Document"])
        display, _ = capture_display

        artifacts_dir = config.session_dir() / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "draft-design_document.md").write_text("agent draft\n")

        mock_response = AgentResponse(text="", raw={}, is_error=True)

        with patch("claude_storm.compilation.invoke_agent", return_value=mock_response):
            compile_deliverables(config, display)

        # Draft untouched, no compiled file created
        assert (
            artifacts_dir / "draft-design_document.md"
        ).read_text() == "agent draft\n"
        assert not (artifacts_dir / "design_document.md").exists()
