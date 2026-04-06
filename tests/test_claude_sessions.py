import json

from kata.utils.claude_sessions import (
    _encode_cwd,
    _find_latest_session,
    get_session_summary,
)


class TestEncodeCwd:
    def test_encode_path(self):
        result = _encode_cwd("/Users/foo/projects/bar")
        assert result == "-Users-foo-projects-bar"

    def test_encode_root(self):
        result = _encode_cwd("/")
        assert result == "-"


class TestFindLatestSession:
    def test_finds_most_recent_jsonl(self, tmp_path):
        (tmp_path / "aaa.jsonl").write_text("{}\n")
        (tmp_path / "bbb.jsonl").write_text("{}\n")
        import time

        time.sleep(0.01)
        (tmp_path / "bbb.jsonl").write_text("{}\n")

        result = _find_latest_session(tmp_path)
        assert result is not None
        assert result.name == "bbb.jsonl"

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = _find_latest_session(tmp_path)
        assert result is None


class TestGetSessionSummary:
    def test_extracts_last_assistant_message(self, tmp_path):
        session_dir = tmp_path / ".claude" / "projects" / "-tmp-myproject"
        session_dir.mkdir(parents=True)
        session_file = session_dir / "test-session.jsonl"
        lines = [
            json.dumps({"type": "human", "message": {"content": "hello"}}),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "I'm working on fixing the auth bug in login.py",
                            }
                        ]
                    },
                }
            ),
        ]
        session_file.write_text("\n".join(lines) + "\n")

        result = get_session_summary("/tmp/myproject", claude_dir=tmp_path / ".claude")
        assert result is not None
        assert "auth bug" in result.lower() or "login" in result.lower()

    def test_returns_none_when_no_sessions(self, tmp_path):
        result = get_session_summary("/tmp/nonexistent", claude_dir=tmp_path / ".claude")
        assert result is None

    def test_truncates_long_summaries(self, tmp_path):
        session_dir = tmp_path / ".claude" / "projects" / "-tmp-myproject"
        session_dir.mkdir(parents=True)
        session_file = session_dir / "test-session.jsonl"
        long_text = "A" * 500
        lines = [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": long_text}]},
                }
            ),
        ]
        session_file.write_text("\n".join(lines) + "\n")

        result = get_session_summary("/tmp/myproject", claude_dir=tmp_path / ".claude")
        assert result is not None
        assert len(result) <= 80
