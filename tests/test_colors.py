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


class TestColorCommand:
    def test_list_presets(self):
        from typer.testing import CliRunner

        from kata.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["color", "--list"])
        assert result.exit_code == 0
        assert "blue" in result.output
        assert "red" in result.output


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


class TestColorIntegration:
    def test_set_color_then_resolve_in_strip(self):
        """Verify a project with color set renders correctly in switch strip."""
        from kata.cli.switch_strip import render_panel

        p = Project(name="colored-proj", path="/tmp/colored-proj", color="teal")
        assert resolve_color(p.color) == "#56B6C2"

        lines = render_panel([p], {}, selected_index=0, term_width=40)
        full_text = "".join(line.plain for line in lines)
        assert "colored-proj" in full_text

    def test_color_roundtrip_serialization(self):
        """Verify color survives serialization/deserialization."""
        p = Project(name="test", path="/tmp/test", color="purple")
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert p2.color == "purple"

    def test_hex_color_roundtrip(self):
        """Verify hex color survives serialization."""
        p = Project(name="test", path="/tmp/test", color="#FF5733")
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert p2.color == "#FF5733"

    def test_no_color_backward_compat(self):
        """Verify projects without color work in switch strip."""
        from kata.cli.switch_strip import render_panel

        p = Project(name="no-color", path="/tmp/no-color")
        assert p.color is None
        lines = render_panel([p], {}, selected_index=0, term_width=40)
        full_text = "".join(line.plain for line in lines)
        assert "no-color" in full_text
