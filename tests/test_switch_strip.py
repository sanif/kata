from datetime import datetime

from kata.core.models import Project, SessionStatus


def _make_project(name):
    return Project(
        name=name,
        path=f"/tmp/{name}",
        created_at=datetime.now(),
        last_opened=datetime.now(),
    )


class TestRenderPanel:
    def test_contains_project_names(self):
        from kata.cli.switch_strip import render_panel

        projects = [_make_project("alpha"), _make_project("beta")]
        lines = render_panel(projects, {}, selected_index=0, term_width=40)
        full_text = "".join(line.plain for line in lines)
        assert "alpha" in full_text
        assert "beta" in full_text

    def test_selected_index_highlighted(self):
        from kata.cli.switch_strip import render_panel

        projects = [_make_project("a"), _make_project("b")]
        lines = render_panel(projects, {}, selected_index=1, term_width=40)
        all_spans = []
        for line in lines:
            all_spans.extend(line._spans)
        assert any("grey23" in str(s.style) for s in all_spans)

    def test_current_session_dimmed(self):
        from kata.cli.switch_strip import render_panel

        projects = [_make_project("a"), _make_project("cur")]
        lines = render_panel(projects, {}, selected_index=0, current_session="cur", term_width=40)
        all_spans = []
        for line in lines:
            all_spans.extend(line._spans)
        assert any("dim" in str(s.style) for s in all_spans)

    def test_empty_projects_panel(self):
        from kata.cli.switch_strip import render_panel

        lines = render_panel([], {}, selected_index=0, term_width=40)
        # Should still render borders without crashing
        assert len(lines) > 0


class TestRenderPanelColors:
    def test_project_with_color_shows_colored_bar(self):
        from kata.cli.switch_strip import render_panel

        p = _make_project("myproj")
        p.color = "blue"
        lines = render_panel([p], {}, selected_index=0, term_width=40)
        full_text = "".join(line.plain for line in lines)
        assert "┃" in full_text
        assert "myproj" in full_text

    def test_project_without_color_selected_gets_cyan_bar(self):
        from kata.cli.switch_strip import render_panel

        p = _make_project("myproj")
        p.color = None
        lines = render_panel([p], {}, selected_index=0, term_width=40)
        full_text = "".join(line.plain for line in lines)
        assert "┃" in full_text  # still has selection bar, just cyan


class TestRenderPanelStatus:
    def test_status_colors(self):
        from kata.cli.switch_strip import render_panel

        projects = [_make_project("active_proj")]
        statuses = {"active_proj": SessionStatus.ACTIVE}
        lines = render_panel(projects, statuses, selected_index=0, term_width=40)
        full_text = "".join(line.plain for line in lines)
        assert "active_proj" in full_text
