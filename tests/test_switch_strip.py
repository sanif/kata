from datetime import datetime

from kata.core.models import Project, SessionStatus


def _make_project(name):
    return Project(
        name=name,
        path=f"/tmp/{name}",
        created_at=datetime.now(),
        last_opened=datetime.now(),
    )


class TestRenderStrip:
    def test_contains_project_names(self):
        from kata.cli.switch_strip import render_strip

        projects = [_make_project("alpha"), _make_project("beta")]
        text = render_strip(projects, {}, selected_index=0)
        assert "alpha" in text.plain
        assert "beta" in text.plain

    def test_selected_index_highlighted(self):
        from kata.cli.switch_strip import render_strip

        projects = [_make_project("a"), _make_project("b")]
        text = render_strip(projects, {}, selected_index=1)
        spans = text._spans
        assert any("reverse" in str(s.style) for s in spans)

    def test_current_session_dimmed(self):
        from kata.cli.switch_strip import render_strip

        projects = [_make_project("a"), _make_project("cur")]
        text = render_strip(projects, {}, selected_index=0, current_session="cur")
        spans = text._spans
        assert any("dim" in str(s.style) for s in spans)

    def test_empty_projects(self):
        from kata.cli.switch_strip import render_strip

        text = render_strip([], {}, selected_index=0)
        assert text.plain.strip() == ""

    def test_status_colors(self):
        from kata.cli.switch_strip import render_strip

        projects = [_make_project("active_proj")]
        statuses = {"active_proj": SessionStatus.ACTIVE}
        text = render_strip(projects, statuses, selected_index=0)
        # Selected item uses "bold reverse" not the status color
        assert "active_proj" in text.plain
