from datetime import datetime, timedelta

from kata.core.models import Project, SessionStatus


def _make_project(name, hours_ago=0):
    return Project(
        name=name,
        path=f"/tmp/{name}",
        created_at=datetime.now(),
        last_opened=datetime.now() - timedelta(hours=hours_ago),
    )


class TestSwitcherRendering:
    def test_render_strip_contains_all_names(self):
        from kata.tui.screens.switcher import render_switcher_strip

        projects = [_make_project("alpha"), _make_project("beta")]
        result = render_switcher_strip(projects, {}, selected_index=0)
        assert "alpha" in result
        assert "beta" in result

    def test_cycling_wraps_around(self):
        from kata.tui.screens.switcher import cycle_index

        assert cycle_index(0, 3) == 1
        assert cycle_index(2, 3) == 0

    def test_status_indicator_active(self):
        from kata.tui.screens.switcher import get_status_indicator

        assert "●" in get_status_indicator(SessionStatus.ACTIVE)

    def test_status_indicator_idle(self):
        from kata.tui.screens.switcher import get_status_indicator

        assert "○" in get_status_indicator(SessionStatus.IDLE)

    def test_selected_item_has_reverse(self):
        from kata.tui.screens.switcher import render_switcher_strip

        projects = [_make_project("a"), _make_project("b")]
        result = render_switcher_strip(projects, {}, selected_index=1)
        assert "reverse" in result

    def test_current_session_dimmed(self):
        from kata.tui.screens.switcher import render_switcher_strip

        projects = [_make_project("a"), _make_project("current")]
        result = render_switcher_strip(projects, {}, selected_index=0, current_session="current")
        assert "[dim]" in result
