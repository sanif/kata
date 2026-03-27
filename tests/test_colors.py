from kata.core.models import Project
from kata.utils.colors import COLOR_PRESETS, hex_to_256, resolve_color


class TestProjectColor:
    def test_default_color_is_none(self):
        p = Project(name="test", path="/tmp/test")
        assert p.color is None

    def test_color_serialization(self):
        p = Project(name="test", path="/tmp/test", color="blue")
        d = p.to_dict()
        assert d["color"] == "blue"

    def test_color_deserialization(self):
        d = {
            "name": "test",
            "path": "/tmp/test",
            "created_at": "2026-01-01T00:00:00",
            "color": "#FF5733",
        }
        p = Project.from_dict(d)
        assert p.color == "#FF5733"

    def test_missing_color_in_dict_defaults_none(self):
        d = {
            "name": "test",
            "path": "/tmp/test",
            "created_at": "2026-01-01T00:00:00",
        }
        p = Project.from_dict(d)
        assert p.color is None


class TestResolveColor:
    def test_none_returns_none(self):
        assert resolve_color(None) is None

    def test_named_preset(self):
        assert resolve_color("blue") == "#5B9BD5"

    def test_named_preset_case_insensitive(self):
        assert resolve_color("Blue") == "#5B9BD5"

    def test_hex_passthrough(self):
        assert resolve_color("#FF5733") == "#FF5733"

    def test_unknown_name_returns_none(self):
        assert resolve_color("unicorn") is None

    def test_all_presets_are_valid_hex(self):
        for name, hex_val in COLOR_PRESETS.items():
            assert hex_val.startswith("#"), f"{name} preset is not hex"
            assert len(hex_val) == 7, f"{name} preset wrong length"


class TestHexTo256:
    def test_pure_red(self):
        result = hex_to_256("#FF0000")
        assert isinstance(result, int)
        assert 0 <= result <= 255

    def test_pure_white(self):
        result = hex_to_256("#FFFFFF")
        assert isinstance(result, int)

    def test_pure_black(self):
        result = hex_to_256("#000000")
        assert isinstance(result, int)

    def test_preset_blue(self):
        result = hex_to_256("#5B9BD5")
        assert isinstance(result, int)
        assert 0 <= result <= 255
