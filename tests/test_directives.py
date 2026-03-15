"""Tests for directive parsing (directives.py)."""

from __future__ import annotations

from claude_storm.directives import (
    ArtifactDirective,
    _parse_attrs,
    _remove_spans,
    parse_directives,
)


class TestParseDirectives:
    def test_parse_artifact(self):
        text = '[ARTIFACT filename="api.yaml"]openapi: 3.0\npaths: {}[/ARTIFACT]'
        result = parse_directives(text)
        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "api.yaml"
        assert "openapi: 3.0" in result.artifacts[0].content

    def test_parse_done_with_reason(self):
        text = 'I think we covered everything\n[DONE reason="Topic well explored"]'
        result = parse_directives(text)
        assert result.done == "Topic well explored"

    def test_parse_done_without_reason(self):
        text = "I think we're done here\n[DONE]"
        result = parse_directives(text)
        assert result.done == "complete"
        assert "[DONE]" not in result.clean_text

    def test_parse_done_bare_cleans_text(self):
        text = "Final thoughts.\n[DONE]\nThat's all."
        result = parse_directives(text)
        assert result.done == "complete"
        assert "Final thoughts." in result.clean_text
        assert "That's all." in result.clean_text
        assert "[DONE]" not in result.clean_text

    def test_parse_done_with_leading_whitespace(self):
        text = "Some preamble\n  [DONE]\nMore text"
        result = parse_directives(text)
        assert result.done == "complete"

    def test_parse_done_mid_sentence_no_trigger(self):
        text = "Should we follow this plan or aim for [DONE] sooner?"
        result = parse_directives(text)
        assert result.done is None

    def test_parse_done_quoted_context_no_trigger(self):
        text = 'The agent can signal [DONE reason="..."] when finished.'
        result = parse_directives(text)
        assert result.done is None

    def test_parse_ask_user(self):
        text = "What do you think? [ASK_USER]Should we use JWT or OAuth?[/ASK_USER]"
        result = parse_directives(text)
        assert result.ask_user == "Should we use JWT or OAuth?"

    def test_no_directives(self):
        text = "Just a regular response with no special directives."
        result = parse_directives(text)
        assert result.artifacts == []
        assert result.done is None
        assert result.ask_user is None
        assert result.clean_text == text

    def test_parse_propose(self):
        text = (
            'Let me propose [PROPOSE title="Use REST"]'
            "We should use REST for the API[/PROPOSE] done"
        )
        result = parse_directives(text)
        assert len(result.proposals) == 1
        assert result.proposals[0] == ("Use REST", "We should use REST for the API")
        assert "[PROPOSE" not in result.clean_text
        assert "Let me propose" in result.clean_text

    def test_parse_accept(self):
        text = 'I agree with that. [ACCEPT id="a3f2"]'
        result = parse_directives(text)
        assert result.accepts == ["a3f2"]
        assert "[ACCEPT" not in result.clean_text

    def test_parse_reject(self):
        text = 'I disagree. [REJECT id="a3f2" reason="Too complex"]'
        result = parse_directives(text)
        assert result.rejects == [("a3f2", "Too complex")]
        assert "[REJECT" not in result.clean_text

    def test_parse_revise(self):
        text = '[REVISE id="a3f2"]Updated: use REST with caching[/REVISE]'
        result = parse_directives(text)
        assert len(result.revisions) == 1
        assert result.revisions[0] == ("a3f2", "Updated: use REST with caching")
        assert "[REVISE" not in result.clean_text

    def test_parse_revise_empty_body_ignored(self):
        result = parse_directives('[REVISE id="abc"][/REVISE]')
        assert result.revisions == []

    def test_parse_multiple_accepts(self):
        text = '[ACCEPT id="a3f2"] [ACCEPT id="b7c1"]'
        result = parse_directives(text)
        assert result.accepts == ["a3f2", "b7c1"]

    def test_no_agreement_directives(self):
        text = "Just a regular response."
        result = parse_directives(text)
        assert result.proposals == []
        assert result.accepts == []
        assert result.rejects == []
        assert result.revisions == []

    def test_artifact_with_extra_title_attr(self):
        """The motivating bug: extra title= attribute should not break parsing."""
        text = '[ARTIFACT title="Act 1" filename="act1.md"]Scene 1 content[/ARTIFACT]'
        result = parse_directives(text)
        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "act1.md"
        assert result.artifacts[0].content == "Scene 1 content"
        assert "[ARTIFACT" not in result.clean_text

    def test_artifact_attrs_reversed_order(self):
        """Attribute order should not matter."""
        text = '[ARTIFACT filename="ch1.md" title="Chapter 1"]Chapter text[/ARTIFACT]'
        result = parse_directives(text)
        assert len(result.artifacts) == 1
        assert result.artifacts[0].filename == "ch1.md"
        assert result.artifacts[0].content == "Chapter text"

    def test_reject_with_extra_attrs(self):
        """Extra attributes on self-closing directives should be ignored."""
        text = '[REJECT id="x1" reason="Too slow" priority="high"]'
        result = parse_directives(text)
        assert result.rejects == [("x1", "Too slow")]
        assert "[REJECT" not in result.clean_text

    def test_reject_attrs_reversed_order(self):
        """Attribute order should not matter for self-closing directives."""
        text = '[REJECT reason="Overengineered" id="p5"]'
        result = parse_directives(text)
        assert result.rejects == [("p5", "Overengineered")]

    def test_mixed_block_and_self_closing(self):
        """Block and self-closing directives coexist in one response."""
        text = (
            "Here is my analysis.\n"
            '[ACCEPT id="prop1"]\n'
            '[ARTIFACT filename="out.md"]# Output[/ARTIFACT]'
        )
        result = parse_directives(text)
        assert result.accepts == ["prop1"]
        assert len(result.artifacts) == 1
        assert "Here is my analysis." in result.clean_text
        assert "[ACCEPT" not in result.clean_text
        assert "[ARTIFACT" not in result.clean_text


class TestArtifactAction:
    def test_default_action_is_overwrite(self):
        text = '[ARTIFACT filename="out.md"]content[/ARTIFACT]'
        result = parse_directives(text)
        assert result.artifacts[0].action == "overwrite"

    def test_action_append_parsed(self):
        text = '[ARTIFACT filename="story.md" action="append"]next section[/ARTIFACT]'
        result = parse_directives(text)
        assert result.artifacts[0].filename == "story.md"
        assert result.artifacts[0].content == "next section"
        assert result.artifacts[0].action == "append"

    def test_unknown_action_stored_as_is(self):
        """Parser stores unknown action values; write layer is responsible for handling them."""
        text = '[ARTIFACT filename="x.md" action="replace"]body[/ARTIFACT]'
        result = parse_directives(text)
        assert result.artifacts[0].action == "replace"

    def test_artifact_directive_is_named_tuple(self):
        text = '[ARTIFACT filename="f.md"]body[/ARTIFACT]'
        result = parse_directives(text)
        artifact = result.artifacts[0]
        assert isinstance(artifact, ArtifactDirective)
        assert artifact.filename == "f.md"
        assert artifact.content == "body"
        assert artifact.action == "overwrite"


class TestParseAttrs:
    def test_single_attr(self):
        assert _parse_attrs(' filename="api.yaml"') == {"filename": "api.yaml"}

    def test_multiple_attrs(self):
        result = _parse_attrs(' title="Act 1" filename="act1.md"')
        assert result == {"title": "Act 1", "filename": "act1.md"}

    def test_empty_string(self):
        assert _parse_attrs("") == {}

    def test_empty_value(self):
        assert _parse_attrs(' tags=""') == {"tags": ""}

    def test_attr_with_spaces_in_value(self):
        result = _parse_attrs(' reason="Too complex for MVP"')
        assert result == {"reason": "Too complex for MVP"}


class TestRemoveSpans:
    def test_no_spans(self):
        assert _remove_spans("hello world", []) == "hello world"

    def test_single_span(self):
        assert _remove_spans("hello [TAG] world", [(6, 11)]) == "hello  world"

    def test_multiple_non_overlapping(self):
        text = "AA[X]BB[Y]CC"
        result = _remove_spans(text, [(2, 5), (7, 10)])
        assert result == "AABBCC"

    def test_overlapping_spans_merged(self):
        text = "0123456789"
        # Spans (2,5) and (4,7) overlap — should remove indices 2..7
        result = _remove_spans(text, [(2, 5), (4, 7)])
        assert result == "01789"

    def test_adjacent_spans(self):
        text = "AABBCC"
        result = _remove_spans(text, [(2, 4), (4, 6)])
        assert result == "AA"
