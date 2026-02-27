"""Tests for the audio player module."""

from unittest.mock import patch

from kata.services.notifications.dispatch.audio import (
    resolve_sound_path,
    volume_to_afplay,
)


class TestVolumeConversion:
    def test_full_volume(self):
        assert volume_to_afplay(1.0) == 1.0

    def test_zero_volume(self):
        assert volume_to_afplay(0.0) == 0.0

    def test_half_volume(self):
        assert volume_to_afplay(0.5) == 0.5

    def test_clamps_above_one(self):
        assert volume_to_afplay(5.0) == 1.0

    def test_clamps_below_zero(self):
        assert volume_to_afplay(-1.0) == 0.0


class TestResolveSoundPath:
    def test_resolve_bundled_sound(self):
        path = resolve_sound_path("task_complete", {})
        assert path is not None
        assert path.name == "task-complete.mp3"

    def test_resolve_override(self, tmp_path):
        custom = tmp_path / "custom.mp3"
        custom.write_bytes(b"fake mp3")
        overrides = {"task_complete": str(custom)}
        path = resolve_sound_path("task_complete", overrides)
        assert path == custom

    def test_resolve_override_missing_file(self):
        overrides = {"task_complete": "/nonexistent/sound.mp3"}
        path = resolve_sound_path("task_complete", overrides)
        assert path is not None
        assert "task-complete.mp3" in path.name

    def test_resolve_unknown_type(self):
        path = resolve_sound_path("session_launched", {})
        assert path is None


class TestPlaySound:
    @patch("kata.services.notifications.dispatch.audio.subprocess.Popen")
    def test_play_calls_afplay(self, mock_popen, tmp_path):
        from kata.services.notifications.dispatch.audio import play_sound

        sound_file = tmp_path / "test.mp3"
        sound_file.write_bytes(b"fake")
        play_sound(sound_file, volume=0.8)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "afplay"
        assert str(sound_file) in args

    @patch("kata.services.notifications.dispatch.audio.subprocess.Popen")
    def test_play_skips_missing_file(self, mock_popen):
        from pathlib import Path

        from kata.services.notifications.dispatch.audio import play_sound

        play_sound(Path("/nonexistent.mp3"), volume=1.0)
        mock_popen.assert_not_called()
