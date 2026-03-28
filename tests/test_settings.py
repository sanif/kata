"""Tests for settings module."""

from dataclasses import fields as dataclass_fields

from kata.core.settings import Settings


class TestSettings:
    """Test Settings dataclass."""

    def test_from_dict_empty_returns_defaults(self):
        """from_dict({}) should return same defaults as Settings()."""
        default = Settings()
        from_empty = Settings.from_dict({})
        for f in dataclass_fields(Settings):
            assert getattr(default, f.name) == getattr(
                from_empty, f.name
            ), f"Mismatch on field '{f.name}'"

    def test_from_dict_with_values(self):
        """from_dict with values should override defaults."""
        s = Settings.from_dict({"theme": "kata-ocean", "refresh_interval": 10})
        assert s.theme == "kata-ocean"
        assert s.refresh_interval == 10

    def test_from_dict_ignores_unknown_keys(self):
        """from_dict should ignore keys not in the dataclass."""
        s = Settings.from_dict({"unknown_key": "value", "theme": "kata-dark"})
        assert s.theme == "kata-dark"
        assert not hasattr(s, "unknown_key")

    def test_validation_clamps_refresh_interval(self):
        """Refresh interval should be clamped to 1-60."""
        s = Settings(refresh_interval=0)
        assert s.refresh_interval == 1
        s = Settings(refresh_interval=100)
        assert s.refresh_interval == 60

    def test_validation_resets_invalid_theme(self):
        """Invalid theme should reset to kata-dark."""
        s = Settings(theme="nonexistent")
        assert s.theme == "kata-dark"

    def test_validation_clamps_volume(self):
        """Volume should be clamped to 0.0-1.0."""
        s = Settings(notifications_volume=2.0)
        assert s.notifications_volume == 1.0
        s = Settings(notifications_volume=-0.5)
        assert s.notifications_volume == 0.0
