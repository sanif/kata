"""Tests for the tool-based transcript analyzer."""

import json

from kata.services.notifications.dispatch.analyzer import (
    classify_from_tools_and_text,
    parse_transcript_window,
)
from kata.services.notifications.models import NotificationType


class TestClassifyFromToolsAndText:
    def test_session_limit(self):
        result = classify_from_tools_and_text(
            tools=set(),
            last_messages=["Session limit reached. Please start a new session."],
            has_error=False,
        )
        assert result == NotificationType.SESSION_LIMIT

    def test_error_from_flag(self):
        result = classify_from_tools_and_text(
            tools=set(),
            last_messages=["Something happened"],
            has_error=True,
        )
        assert result == NotificationType.ERROR

    def test_plan_ready(self):
        result = classify_from_tools_and_text(
            tools={"ExitPlanMode"},
            last_messages=["Plan ready"],
            has_error=False,
        )
        assert result == NotificationType.PLAN_READY

    def test_review_done_passive_only(self):
        result = classify_from_tools_and_text(
            tools={"Read", "Grep"},
            last_messages=["x" * 201],
            has_error=False,
        )
        assert result == NotificationType.REVIEW_DONE

    def test_task_complete_active_tools(self):
        result = classify_from_tools_and_text(
            tools={"Write", "Bash"},
            last_messages=["Done"],
            has_error=False,
        )
        assert result == NotificationType.TASK_COMPLETE

    def test_task_complete_mixed_tools(self):
        result = classify_from_tools_and_text(
            tools={"Read", "Edit", "Grep"},
            last_messages=["Fixed it"],
            has_error=False,
        )
        assert result == NotificationType.TASK_COMPLETE

    def test_task_complete_default(self):
        result = classify_from_tools_and_text(
            tools=set(),
            last_messages=["All done"],
            has_error=False,
        )
        assert result == NotificationType.TASK_COMPLETE

    def test_review_short_text_not_review(self):
        result = classify_from_tools_and_text(
            tools={"Read"},
            last_messages=["ok"],
            has_error=False,
        )
        assert result == NotificationType.TASK_COMPLETE


class TestParseTranscriptWindow:
    def _make_transcript(self, tmp_path, entries):
        path = tmp_path / "transcript.jsonl"
        lines = [json.dumps(e) for e in entries]
        path.write_text("\n".join(lines))
        return str(path)

    def test_extracts_tools_after_last_user(self, tmp_path):
        path = self._make_transcript(
            tmp_path,
            [
                {"type": "human", "message": {"content": "Fix it"}},
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Edit"},
                            {"type": "text", "text": "Done."},
                        ]
                    },
                },
            ],
        )
        tools, messages = parse_transcript_window(path)
        assert "Edit" in tools
        assert "Done." in messages

    def test_only_after_last_user_message(self, tmp_path):
        path = self._make_transcript(
            tmp_path,
            [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Write"},
                        ]
                    },
                },
                {"type": "human", "message": {"content": "Now read it"}},
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Read"},
                            {"type": "text", "text": "Here's what I found"},
                        ]
                    },
                },
            ],
        )
        tools, messages = parse_transcript_window(path)
        assert "Write" not in tools
        assert "Read" in tools

    def test_caps_at_15_messages(self, tmp_path):
        entries = [{"type": "human", "message": {"content": "go"}}]
        for i in range(20):
            entries.append({"type": "assistant", "message": {"content": f"msg {i}"}})
        path = self._make_transcript(tmp_path, entries)
        _, messages = parse_transcript_window(path)
        assert len(messages) <= 15

    def test_missing_file(self):
        tools, messages = parse_transcript_window("/nonexistent")
        assert tools == set()
        assert messages == []
