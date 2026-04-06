from datetime import datetime

from kata.core.models import WorktreeInfo, WorktreeStatus


def _make_main_status(branch="main", dirty=False, summary=None, active=False):
    info = WorktreeInfo(
        name="main",
        branch=branch,
        path=".",
        created_at=datetime.min,
        context_mode="fresh",
    )
    return WorktreeStatus(
        info=info,
        is_main=True,
        dirty=dirty,
        changed_files=0,
        session_summary=summary,
        session_active=active,
    )


def _make_wt_status(name, branch=None, dirty=False, changed=0, summary=None, active=False):
    info = WorktreeInfo(
        name=name,
        branch=branch or name,
        path=f".worktrees/{name}",
        created_at=datetime.now(),
        context_mode="fresh",
    )
    return WorktreeStatus(
        info=info,
        is_main=False,
        dirty=dirty,
        changed_files=changed,
        session_summary=summary,
        session_active=active,
    )


class TestRenderWorktreePanel:
    def test_contains_worktree_names(self):
        from kata.cli.worktree_strip import render_worktree_panel

        worktrees = [_make_main_status(), _make_wt_status("fix-auth")]
        lines = render_worktree_panel(
            worktrees, selected_index=0, project_name="myproj", term_width=50
        )
        full_text = "".join(line.plain for line in lines)
        assert "main" in full_text
        assert "fix-auth" in full_text

    def test_shows_dirty_indicator(self):
        from kata.cli.worktree_strip import render_worktree_panel

        worktrees = [
            _make_main_status(dirty=True),
            _make_wt_status("fix-auth", dirty=True, changed=3),
        ]
        lines = render_worktree_panel(
            worktrees, selected_index=0, project_name="myproj", term_width=50
        )
        full_text = "".join(line.plain for line in lines)
        assert "3" in full_text

    def test_shows_session_summary(self):
        from kata.cli.worktree_strip import render_worktree_panel

        worktrees = [_make_main_status(summary="Working on auth")]
        lines = render_worktree_panel(
            worktrees, selected_index=0, project_name="myproj", term_width=50
        )
        full_text = "".join(line.plain for line in lines)
        assert "Working on auth" in full_text

    def test_selected_index_highlighted(self):
        from kata.cli.worktree_strip import render_worktree_panel

        worktrees = [_make_main_status(), _make_wt_status("fix-auth")]
        lines = render_worktree_panel(
            worktrees, selected_index=1, project_name="myproj", term_width=50
        )
        all_spans = []
        for line in lines:
            all_spans.extend(line._spans)
        assert any("grey23" in str(s.style) for s in all_spans)

    def test_empty_worktrees(self):
        from kata.cli.worktree_strip import render_worktree_panel

        lines = render_worktree_panel([], selected_index=0, project_name="myproj", term_width=50)
        assert len(lines) > 0


class TestCalcPopupSize:
    def test_min_width(self):
        from kata.cli.worktree_strip import _calc_worktree_popup_size

        worktrees = [_make_main_status()]
        w, h = _calc_worktree_popup_size(worktrees, "x")
        assert w >= 40

    def test_height_scales_with_worktrees(self):
        from kata.cli.worktree_strip import _calc_worktree_popup_size

        wt1 = [_make_main_status()]
        wt3 = [_make_main_status(), _make_wt_status("a"), _make_wt_status("b")]
        _, h1 = _calc_worktree_popup_size(wt1, "x")
        _, h3 = _calc_worktree_popup_size(wt3, "x")
        assert h3 > h1
