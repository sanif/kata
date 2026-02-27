"""Tests for notification summary generator."""

from kata.services.notifications.dispatch.summary import generate_summary


class TestGenerateSummary:
    def test_plain_text(self):
        assert generate_summary("Hello world") == "Hello world"

    def test_strips_markdown_headers(self):
        assert generate_summary("## Header\nContent") == "Content"

    def test_strips_bullet_points(self):
        result = generate_summary("- Item one\n- Item two")
        assert not result.startswith("-")
        assert "Item one" in result

    def test_strips_backticks(self):
        assert generate_summary("Use `foo()` here") == "Use foo() here"

    def test_strips_code_blocks(self):
        text = "Before\n```python\ncode()\n```\nAfter"
        result = generate_summary(text)
        assert "```" not in result
        assert "After" in result

    def test_truncates_to_max_length(self):
        long_text = "A" * 300
        result = generate_summary(long_text, max_length=200)
        assert len(result) <= 200
        assert result.endswith("…")

    def test_normalizes_whitespace(self):
        assert generate_summary("hello   \n  world") == "hello world"

    def test_empty_string(self):
        assert generate_summary("") == ""

    def test_first_line_only_for_multiline(self):
        result = generate_summary("First line\nSecond line\nThird", max_length=200)
        assert "First line" in result

    def test_strips_bold_italic(self):
        assert generate_summary("**bold** and *italic*") == "bold and italic"
