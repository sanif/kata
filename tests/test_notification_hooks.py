"""Tests for Claude Code hook handler."""

import json

from kata.services.notifications.hooks.claude_code import (
    classify_event,
    parse_transcript,
)
from kata.services.notifications.models import NotificationType


class TestClassifyEvent:
    """Test event classification from transcript content."""

    def test_question_detection(self):
        messages = [
            {"role": "assistant", "content": "What framework should I use for this?"},
        ]
        assert classify_event(messages, []) == NotificationType.QUESTION

    def test_session_limit_detection(self):
        messages = [
            {"role": "assistant", "content": "Session limit reached. Please start a new session."},
        ]
        assert classify_event(messages, []) == NotificationType.SESSION_LIMIT

    def test_error_detection(self):
        messages = [
            {
                "role": "assistant",
                "content": "I encountered an API error: rate limit exceeded (429).",
            },
        ]
        assert classify_event(messages, []) == NotificationType.ERROR

    def test_plan_ready_detection(self):
        messages = [
            {"role": "assistant", "content": "The plan is ready for your review."},
        ]
        tools = [{"name": "ExitPlanMode"}]
        assert classify_event(messages, tools) == NotificationType.PLAN_READY

    def test_task_complete_with_tools(self):
        messages = [
            {"role": "assistant", "content": "I've implemented the feature. The tests all pass."},
        ]
        tools = [{"name": "Write"}, {"name": "Bash"}]
        assert classify_event(messages, tools) == NotificationType.TASK_COMPLETE

    def test_task_complete_default(self):
        messages = [
            {
                "role": "assistant",
                "content": "Done! I've finished implementing everything you asked for.",
            },
        ]
        assert classify_event(messages, []) == NotificationType.TASK_COMPLETE


class TestParseTranscript:
    """Test JSONL transcript parsing."""

    def test_parse_valid_transcript(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps({"type": "human", "message": {"content": "Fix the bug"}}),
            json.dumps({"type": "assistant", "message": {"content": "I'll fix it."}}),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Edit"},
                            {"type": "text", "text": "Done fixing."},
                        ]
                    },
                }
            ),
        ]
        transcript.write_text("\n".join(lines))
        messages, tools = parse_transcript(str(transcript))
        assert len(messages) >= 1
        assert any(t["name"] == "Edit" for t in tools)

    def test_parse_missing_file(self):
        messages, tools = parse_transcript("/nonexistent/path.jsonl")
        assert messages == []
        assert tools == []
