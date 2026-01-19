"""Tests for sessions service."""

import os
from unittest.mock import MagicMock, patch

import pytest

from kata.core.models import Project, SessionStatus
from kata.services.sessions import (
    ConfigNotFoundError,
    SessionError,
    SessionNotFoundError,
    attach_session,
    get_all_kata_sessions,
    get_session_status,
    is_inside_tmux,
    kill_session,
    launch_or_attach,
    launch_session,
    session_exists,
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
    """Tests for session_exists function."""

    def test_session_exists_true(self):
        """Test when session exists."""
        mock_server = MagicMock()
        mock_server.has_session.return_value = True

        with patch("kata.services.sessions._get_tmux_server", return_value=mock_server):
            assert session_exists("test-session") is True
            mock_server.has_session.assert_called_once_with("test-session")

    def test_session_exists_false(self):
        """Test when session doesn't exist."""
        mock_server = MagicMock()
        mock_server.has_session.return_value = False

        with patch("kata.services.sessions._get_tmux_server", return_value=mock_server):
            assert session_exists("test-session") is False

    def test_session_exists_no_server(self):
        """Test when tmux server not available."""
        with patch("kata.services.sessions._get_tmux_server", return_value=None):
            assert session_exists("test-session") is False

    def test_session_exists_exception(self):
        """Test when exception occurs."""
        mock_server = MagicMock()
        mock_server.has_session.side_effect = Exception("tmux error")

        with patch("kata.services.sessions._get_tmux_server", return_value=mock_server):
            assert session_exists("test-session") is False


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
                mock_run.assert_called_once()

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
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
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
