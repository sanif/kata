"""Tests for sessions service."""

import os
from unittest.mock import MagicMock, patch

import pytest

from kata.core.models import Project, SessionStatus
from kata.services.sessions import (
    ConfigNotFoundError,
    SessionError,
    SessionNotFoundError,
    _parse_command,
    attach_session,
    get_active_kata_sessions,
    get_all_kata_sessions,
    get_all_session_statuses,
    get_session_status,
    is_inside_tmux,
    kill_session,
    launch_adhoc_session,
    launch_or_attach,
    launch_or_attach_adhoc,
    launch_session,
    session_exists,
    session_name_for,
)


class TestIsInsideTmux:
    """Tests for is_inside_tmux function."""

    def test_inside_tmux(self):
        """Test detection when inside tmux."""
        with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
            assert is_inside_tmux() is True

    def test_outside_tmux(self):
        """Test detection when outside tmux."""
        env = os.environ.copy()
        env.pop("TMUX", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_inside_tmux() is False

    def test_empty_tmux_var(self):
        """Test detection with empty TMUX variable."""
        with patch.dict(os.environ, {"TMUX": ""}):
            assert is_inside_tmux() is False


class TestSessionExists:
    """Tests for session_exists function (subprocess-based)."""

    def test_session_exists_true(self):
        """Test when session exists (has-session returns 0)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert session_exists("test-session") is True
            args = mock_run.call_args[0][0]
            assert args[:2] == ["tmux", "has-session"]
            # Exact-match target prefix guards against unrelated sessions.
            assert "=test-session" in args

    def test_session_exists_false(self):
        """Test when session doesn't exist (has-session returns non-zero)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert session_exists("test-session") is False

    def test_session_exists_no_tmux(self):
        """Test when the tmux binary is missing."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert session_exists("test-session") is False

    def test_session_exists_timeout(self):
        """Test when the tmux call times out."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("tmux", 2)):
            assert session_exists("test-session") is False

    def test_session_exists_empty_name(self):
        """Empty names never match and never spawn a subprocess."""
        with patch("subprocess.run") as mock_run:
            assert session_exists("") is False
            mock_run.assert_not_called()


class TestGetSessionStatus:
    """Tests for get_session_status function."""

    def test_status_active(self):
        """Test status when session is active."""
        mock_session = MagicMock()
        mock_session.session_attached = "1"

        mock_server = MagicMock()
        mock_server.sessions.get.return_value = mock_session

        with patch("kata.services.sessions._get_tmux_server", return_value=mock_server):
            status = get_session_status("test-session")
            assert status == SessionStatus.ACTIVE

    def test_status_detached(self):
        """Test status when session is detached."""
        mock_session = MagicMock()
        mock_session.session_attached = "0"

        mock_server = MagicMock()
        mock_server.sessions.get.return_value = mock_session

        with patch("kata.services.sessions._get_tmux_server", return_value=mock_server):
            status = get_session_status("test-session")
            assert status == SessionStatus.DETACHED

    def test_status_idle(self):
        """Test status when session doesn't exist."""
        mock_server = MagicMock()
        mock_server.sessions.get.return_value = None

        with patch("kata.services.sessions._get_tmux_server", return_value=mock_server):
            status = get_session_status("test-session")
            assert status == SessionStatus.IDLE

    def test_status_no_server(self):
        """Test status when tmux server not available."""
        with patch("kata.services.sessions._get_tmux_server", return_value=None):
            status = get_session_status("test-session")
            assert status == SessionStatus.IDLE


class TestLaunchSession:
    """Tests for launch_session function."""

    def test_launch_success(self, tmp_path):
        """Test successful session launch."""
        # Config is now stored as .kata.yaml in the project directory
        config_file = tmp_path / ".kata.yaml"
        config_file.write_text("session_name: test")

        project = Project(
            name="test",
            path=str(tmp_path),
            group="Test",
            config="test.yaml",
        )

        with patch("kata.services.sessions.migrate_project_config"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                launch_session(project)
                # First call should be tmuxp load
                args = mock_run.call_args_list[0][0][0]
                assert "tmuxp" in args
                assert "load" in args

    def test_launch_config_not_found(self, tmp_path):
        """Test launch when config file missing."""
        project = Project(
            name="test",
            path=str(tmp_path),
            group="Test",
            config="nonexistent.yaml",
        )

        with patch("kata.services.sessions.migrate_project_config"):
            with pytest.raises(ConfigNotFoundError):
                launch_session(project)

    def test_launch_tmuxp_error(self, tmp_path):
        """Test launch when tmuxp returns error."""
        # Config is now stored as .kata.yaml in the project directory
        config_file = tmp_path / ".kata.yaml"
        config_file.write_text("session_name: test")

        project = Project(
            name="test",
            path=str(tmp_path),
            group="Test",
            config="test.yaml",
        )

        with patch("kata.services.sessions.migrate_project_config"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="error")
                with pytest.raises(SessionError):
                    launch_session(project)


class TestAttachSession:
    """Tests for attach_session function."""

    def test_attach_outside_tmux(self):
        """Test attach when outside tmux."""
        with patch("kata.services.sessions.session_exists", return_value=True):
            with patch("kata.services.sessions.is_inside_tmux", return_value=False):
                with patch("kata.services.sessions._get_tmux_client", return_value=None):
                    with patch("subprocess.run") as mock_run:
                        attach_session("test-session")
                        mock_run.assert_called_once()
                        args = mock_run.call_args[0][0]
                        assert "attach-session" in args

    def test_attach_inside_tmux(self):
        """Test attach when inside tmux (should switch-client)."""
        with patch("kata.services.sessions.session_exists", return_value=True):
            with patch("kata.services.sessions.is_inside_tmux", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    attach_session("test-session")
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert "switch-client" in args

    def test_attach_inside_tmux_switch_client(self):
        """Test attach inside tmux uses switch-client command."""
        with patch("kata.services.sessions.session_exists", return_value=True):
            with patch("kata.services.sessions.is_inside_tmux", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    attach_session("test-session")
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert "switch-client" in args
                    assert "-t" in args
                    assert "test-session" in args

    def test_attach_session_not_found(self):
        """Test attach when session doesn't exist."""
        with patch("kata.services.sessions.session_exists", return_value=False):
            with pytest.raises(SessionNotFoundError):
                attach_session("test-session")


class TestKillSession:
    """Tests for kill_session function."""

    def test_kill_success(self):
        """Test successful session kill."""
        with patch("kata.services.sessions.session_exists", return_value=True):
            with patch("subprocess.run") as mock_run:
                kill_session("test-session")
                # First call should be tmux kill-session
                args = mock_run.call_args_list[0][0][0]
                assert "kill-session" in args

    def test_kill_session_not_found(self):
        """Test kill when session doesn't exist."""
        with patch("kata.services.sessions.session_exists", return_value=False):
            with pytest.raises(SessionNotFoundError):
                kill_session("test-session")


class TestLaunchOrAttach:
    """Tests for launch_or_attach function."""

    def test_launch_or_attach_existing(self, tmp_path):
        """Test when session exists - should attach."""
        project = Project(
            name="test",
            path=str(tmp_path),
            group="Test",
            config="test.yaml",
        )

        with patch("kata.services.sessions.session_exists", return_value=True):
            with patch("kata.services.sessions.attach_session") as mock_attach:
                launch_or_attach(project)
                mock_attach.assert_called_once_with("test")

    def test_launch_or_attach_new(self, tmp_path):
        """Test when session doesn't exist - should launch then attach."""
        # Config is now stored as .kata.yaml in the project directory
        config_file = tmp_path / ".kata.yaml"
        config_file.write_text("session_name: test")

        project = Project(
            name="test",
            path=str(tmp_path),
            group="Test",
            config="test.yaml",
        )

        with patch("kata.services.sessions.migrate_project_config"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                with patch("kata.services.sessions.attach_session") as mock_attach:
                    mock_attach.return_value = None
                    # After launch, session exists
                    with patch(
                        "kata.services.sessions.session_exists",
                        side_effect=[False, True],
                    ):
                        launch_or_attach(project)


class TestGetAllKataSessions:
    """Tests for get_all_kata_sessions function."""

    def test_get_sessions(self):
        """Test getting all sessions."""
        mock_sessions = [
            MagicMock(name="session1"),
            MagicMock(name="session2"),
        ]
        mock_sessions[0].name = "session1"
        mock_sessions[1].name = "session2"

        mock_server = MagicMock()
        mock_server.sessions = mock_sessions

        with patch("kata.services.sessions._get_tmux_server", return_value=mock_server):
            sessions = get_all_kata_sessions()
            assert len(sessions) == 2
            assert "session1" in sessions
            assert "session2" in sessions

    def test_get_sessions_no_server(self):
        """Test when tmux server not available."""
        with patch("kata.services.sessions._get_tmux_server", return_value=None):
            sessions = get_all_kata_sessions()
            assert sessions == []


class TestSessionNameFor:
    """Tests for session_name_for helper (name sanitization root cause)."""

    def test_dotted_name_falls_back_to_sanitized(self, tmp_path):
        """A dotted project with no config uses the sanitized name."""
        project = Project(name="next.js", path=str(tmp_path), group="Test")
        assert session_name_for(project) == "next_js"

    def test_colon_name_falls_back_to_sanitized(self, tmp_path):
        project = Project(name="scope:pkg", path=str(tmp_path), group="Test")
        assert session_name_for(project) == "scope_pkg"

    def test_edited_session_name_in_config_is_honoured(self, tmp_path):
        """An edited session_name: in .kata.yaml wins over the project name."""
        (tmp_path / ".kata.yaml").write_text("session_name: custom-name\nwindows: []\n")
        project = Project(name="original", path=str(tmp_path), group="Test")
        assert session_name_for(project) == "custom-name"

    def test_malformed_config_falls_back(self, tmp_path):
        (tmp_path / ".kata.yaml").write_text(": : not valid yaml : :\n")
        project = Project(name="proj", path=str(tmp_path), group="Test")
        assert session_name_for(project) == "proj"


class TestAdhocSanitization:
    """Adhoc launch must use the sanitized name tmux actually creates."""

    def test_launch_adhoc_returns_sanitized_name(self, tmp_path):
        dotted = tmp_path / "next.js"
        dotted.mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch("kata.services.sessions._generate_unique_session_name") as mock_uniq:
                mock_uniq.side_effect = lambda base: base
                name = launch_adhoc_session(str(dotted))
        # tmux converts "." to "_"; the returned name must match reality.
        assert name == "next_js"
        mock_uniq.assert_called_once_with("next_js")

    def test_launch_or_attach_adhoc_attaches_to_sanitized_existing(self, tmp_path):
        dotted = tmp_path / "next.js"
        dotted.mkdir()
        with patch("kata.services.sessions.session_exists", return_value=True) as mock_exists:
            with patch("kata.services.sessions.attach_session") as mock_attach:
                launch_or_attach_adhoc(str(dotted))
        mock_exists.assert_called_once_with("next_js")
        mock_attach.assert_called_once_with("next_js")


class TestGetAllSessionStatuses:
    """Parsing must survive session names that contain '|'."""

    def test_pipe_in_session_name_does_not_poison_map(self):
        output = "good|1\nweird|name|0\nbroken-line-no-pipe\nanother|nope\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=output)
            statuses = get_all_session_statuses()
        # "good" attached, "weird|name" detached; the unparseable
        # ("another|nope") line is skipped without dropping the rest.
        assert statuses["good"] == SessionStatus.ACTIVE
        assert statuses["weird|name"] == SessionStatus.DETACHED
        assert "another|nope" not in statuses


class TestGetActiveKataSessions:
    """kill --all must match by sanitized name, never raw name."""

    def test_matches_sanitized_and_ignores_unrelated(self):
        live = {
            "next_js": SessionStatus.DETACHED,
            "personal": SessionStatus.ACTIVE,
        }
        with patch("kata.services.sessions.get_all_session_statuses", return_value=live):
            result = get_active_kata_sessions(["next.js", "missing"])
        assert result == ["next_js"]


class TestParseCommand:
    """_parse_command must not shred paths containing spaces."""

    def test_spaced_path_survives(self):
        # A quoted path with a space must stay one token (naive .split() would
        # break it into "/Some" and "Path/bin/script.py").
        cmd = _parse_command('python "/Some Path/bin/script.py" --flag')
        assert cmd == "python script.py --flag"

    def test_unbalanced_quotes_fall_back(self):
        # A stray quote must not raise; falls back to naive split.
        assert _parse_command('nvim "unterminated') == "nvim"
