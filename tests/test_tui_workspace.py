"""Tests for the workspace screen: split-row algorithm, mouse + keyboard flows."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import kata.services.registry as registry_module
from kata.core.models import Project
from kata.utils.diff import SplitRow, build_split_rows

# ── build_split_rows (pure) ────────────────────────────────────


def _hunk(header: str, *lines: str) -> str:
    return "\n".join(
        [
            "diff --git a/f.py b/f.py",
            "index 111..222 100644",
            "--- a/f.py",
            "+++ b/f.py",
            header,
            *lines,
        ]
    )


def test_split_rows_modify_pairs_del_with_add():
    rows = build_split_rows(_hunk("@@ -1,3 +1,3 @@", " ctx", "-old", "+new", " tail"))
    assert rows == [
        SplitRow(1, "ctx", "context", 1, "ctx", "context"),
        SplitRow(2, "old", "del", 2, "new", "add"),
        SplitRow(3, "tail", "context", 3, "tail", "context"),
    ]


def test_split_rows_pure_addition_gets_empty_left():
    rows = build_split_rows(_hunk("@@ -1,1 +1,2 @@", " ctx", "+added"))
    assert rows == [
        SplitRow(1, "ctx", "context", 1, "ctx", "context"),
        SplitRow(None, "", "empty", 2, "added", "add"),
    ]


def test_split_rows_pure_deletion_gets_empty_right():
    rows = build_split_rows(_hunk("@@ -1,2 +1,1 @@", " ctx", "-gone"))
    assert rows == [
        SplitRow(1, "ctx", "context", 1, "ctx", "context"),
        SplitRow(2, "gone", "del", None, "", "empty"),
    ]


def test_split_rows_unbalanced_block():
    # 2 deletions vs 1 addition: second del pairs with an empty right cell.
    rows = build_split_rows(_hunk("@@ -1,2 +1,1 @@", "-one", "-two", "+uno"))
    assert rows == [
        SplitRow(1, "one", "del", 1, "uno", "add"),
        SplitRow(2, "two", "del", None, "", "empty"),
    ]


def test_split_rows_skips_no_newline_marker():
    rows = build_split_rows(
        _hunk("@@ -1,1 +1,1 @@", "-old", "\\ No newline at end of file", "+new")
    )
    assert rows == [SplitRow(1, "old", "del", 1, "new", "add")]


def test_split_rows_multiple_hunks_spacer_and_renumber():
    diff = _hunk("@@ -1,1 +1,1 @@", "-a", "+b") + "\n@@ -10,1 +20,1 @@\n c\n+d"
    rows = build_split_rows(diff)
    assert rows[0] == SplitRow(1, "a", "del", 1, "b", "add")
    # Spacer between hunks.
    assert rows[1] == SplitRow(None, "", "empty", None, "", "empty")
    # Second hunk renumbers both sides from the hunk header.
    assert rows[2] == SplitRow(10, "c", "context", 20, "c", "context")
    assert rows[3] == SplitRow(None, "", "empty", 21, "d", "add")


def test_split_rows_headers_produce_no_rows():
    assert build_split_rows("diff --git a/x b/x\nindex 1..2\n--- a/x\n+++ b/x") == []
    assert build_split_rows("") == []


def test_split_rows_multi_file_diff_ends_hunk_at_next_header():
    diff = (
        _hunk("@@ -1,1 +1,1 @@", "-a", "+b")
        + "\ndiff --git a/g.py b/g.py\n--- a/g.py\n+++ b/g.py\n@@ -5,1 +5,1 @@\n-x\n+y"
    )
    rows = build_split_rows(diff)
    assert SplitRow(1, "a", "del", 1, "b", "add") in rows
    assert SplitRow(5, "x", "del", 5, "y", "add") in rows


# ── Fixtures ───────────────────────────────────────────────────


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@test", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def isolated_registry(tmp_path):
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps({"version": "1.0", "projects": []}))
    with patch.object(registry_module, "REGISTRY_FILE", registry_file):
        with patch.object(registry_module, "ensure_config_dirs"):
            registry_module._registry = None
            yield registry_module.get_registry()
            registry_module._registry = None


@pytest.fixture
def git_project(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-q"], root)
    (root / "a.py").write_text("line1\n")
    (root / "README.md").write_text("# Repo\n\nHello.\n")
    _git(["add", "."], root)
    _git(["commit", "-q", "-m", "init"], root)
    (root / "a.py").write_text("line1\nline2\n")  # modified
    return Project(name="repo", path=str(root))


@pytest.fixture
def plain_project(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "notes.txt").write_text("hi\n")
    return Project(name="plain", path=str(root))


@pytest.fixture(autouse=True)
def reset_workspace_prefs():
    from kata.tui.screens.workspace import WorkspaceScreen

    WorkspaceScreen._sidebar_visible_pref = True
    WorkspaceScreen._diff_mode_pref = "unified"
    yield
    WorkspaceScreen._sidebar_visible_pref = True
    WorkspaceScreen._diff_mode_pref = "unified"


async def _open_workspace(app, pilot, project):
    from kata.tui.screens.workspace import WorkspaceScreen

    screen = WorkspaceScreen(project)
    await app.push_screen(screen)
    await pilot.pause()
    await pilot.pause()
    return screen


async def _wait_for(pilot, condition, tries: int = 60):
    """Poll for a condition that depends on a thread worker finishing."""
    for _ in range(tries):
        if condition():
            return True
        await pilot.pause(0.05)
    return condition()


# ── Pilot: layout + sidebar ────────────────────────────────────


async def test_workspace_opens_with_sidebar(isolated_registry, git_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)

        assert screen.query_one("#ws-sidebar").display is True
        # All three sections + content exist.
        for wid in ("#ws-projects", "#ws-changes", "#ws-tree", "#ws-content"):
            assert screen.query_one(wid) is not None
        # Changes loaded the modified file.
        assert [c.rel_path for c in screen._changes] == ["a.py"]


async def test_ctrl_b_hides_sidebar_and_moves_focus(isolated_registry, git_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)

        assert screen.query_one("#ws-sidebar").display is True
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert screen.query_one("#ws-sidebar").display is False
        # Focus moved out of the hidden sidebar into the content area.
        assert app.focused is not None
        assert app.focused.id == "ws-content"

        # Ctrl+B again restores the sidebar and focus returns to the section.
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert screen.query_one("#ws-sidebar").display is True
        assert app.focused.id == "ws-projects"


async def test_header_button_toggles_sidebar(isolated_registry, git_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)

        await pilot.click("#ws-btn-sidebar")
        await pilot.pause()
        assert screen.query_one("#ws-sidebar").display is False
        await pilot.click("#ws-btn-sidebar")
        await pilot.pause()
        assert screen.query_one("#ws-sidebar").display is True


async def test_close_button_pops_screen(isolated_registry, git_project):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.workspace import WorkspaceScreen

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_workspace(app, pilot, git_project)

        assert isinstance(app.screen, WorkspaceScreen)
        await pilot.click("#ws-btn-close")
        await pilot.pause()
        assert not isinstance(app.screen, WorkspaceScreen)


async def test_tab_traversal_reaches_all_sections(isolated_registry, git_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_workspace(app, pilot, git_project)

        seen: set[str] = set()
        for _ in range(6):
            focused = app.focused
            if focused is not None and focused.id:
                seen.add(focused.id)
            await pilot.press("tab")
            await pilot.pause()
        assert {"ws-projects", "ws-changes", "ws-tree", "ws-content"} <= seen


async def test_section_jump_keys(isolated_registry, git_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_workspace(app, pilot, git_project)

        for key, expected in (
            ("2", "ws-changes"),
            ("3", "ws-tree"),
            ("4", "ws-content"),
            ("1", "ws-projects"),
        ):
            await pilot.press(key)
            await pilot.pause()
            assert app.focused is not None and app.focused.id == expected


# ── Pilot: content flows (mouse + keyboard) ────────────────────


async def test_click_changes_row_shows_diff(isolated_registry, git_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)

        await _wait_for(pilot, lambda: len(screen._changes) == 1)
        # Options render inside the OptionList's 1-cell vertical padding.
        await pilot.click("#ws-changes", offset=(3, 1))
        assert await _wait_for(pilot, lambda: screen._diff_text is not None)
        assert "+line2" in screen._diff_text
        assert screen.query_one("#ws-diff-toggle").display is True


async def test_enter_on_changes_row_shows_diff(isolated_registry, git_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)

        await _wait_for(pilot, lambda: len(screen._changes) == 1)
        await pilot.press("2")  # jump to changes
        await pilot.press("enter")
        assert await _wait_for(pilot, lambda: screen._diff_text is not None)
        assert "+line2" in screen._diff_text


async def test_split_toggle_key_and_buttons(isolated_registry, git_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)

        # Open a diff first.
        await _wait_for(pilot, lambda: len(screen._changes) == 1)
        await pilot.press("2", "enter")
        assert await _wait_for(pilot, lambda: screen._diff_text is not None)
        assert screen._diff_mode == "unified"

        await pilot.press("s")
        await pilot.pause()
        assert screen._diff_mode == "split"

        # Header buttons flip modes too.
        await pilot.click("#ws-btn-unified")
        await pilot.pause()
        assert screen._diff_mode == "unified"
        await pilot.click("#ws-btn-split")
        await pilot.pause()
        assert screen._diff_mode == "split"
        # Mode is remembered for the session (class-level pref).
        from kata.tui.screens.workspace import WorkspaceScreen

        assert WorkspaceScreen._diff_mode_pref == "split"


async def test_markdown_file_renders_in_content(isolated_registry, git_project):
    from textual.widgets import Markdown

    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)

        screen._open_file(Path(git_project.path) / "README.md")
        await pilot.pause()
        await pilot.pause()

        assert screen.query_one("#ws-md", Markdown).display is True
        assert screen.query_one("#ws-text").display is False
        assert screen._current_md_path == Path(git_project.path) / "README.md"


async def test_project_switch_by_enter(isolated_registry, git_project, plain_project):
    from kata.tui.app import KataDashboard

    isolated_registry.add(git_project)
    isolated_registry.add(plain_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)
        await pilot.pause()

        assert screen.project.name == "repo"
        await _wait_for(pilot, lambda: len(screen._projects) == 2)
        # Highlight the other project and press Enter.
        from textual.widgets import OptionList

        projects_list = screen.query_one("#ws-projects", OptionList)
        other_index = next(i for i, p in enumerate(screen._projects) if p.name == "plain")
        await pilot.press("1")  # focus projects
        projects_list.highlighted = other_index
        await pilot.press("enter")
        assert await _wait_for(pilot, lambda: screen.project.name == "plain")

        # Non-git project: changes section shows the friendly empty state.
        changes_list = screen.query_one("#ws-changes", OptionList)
        await _wait_for(pilot, lambda: changes_list.option_count == 1)
        assert screen._changes == []
        assert changes_list.option_count == 1  # disabled hint row


async def test_non_git_project_changes_empty_state(isolated_registry, plain_project):
    from textual.widgets import OptionList

    from kata.tui.app import KataDashboard

    isolated_registry.add(plain_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, plain_project)

        changes_list = screen.query_one("#ws-changes", OptionList)
        assert screen._changes == []
        assert changes_list.option_count == 1
        option = changes_list.get_option_at_index(0)
        assert option.disabled is True


async def test_click_tree_file_loads_content(isolated_registry, git_project):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.file_browser import FilteredDirectoryTree

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_workspace(app, pilot, git_project)

        tree = screen.query_one(FilteredDirectoryTree)
        await _wait_for(pilot, lambda: len(tree.root.children) >= 2)
        # Row 0 is the root; the first file row is directly below it.
        await pilot.click(FilteredDirectoryTree, offset=(6, 1))
        assert await _wait_for(pilot, lambda: screen._current_path is not None)
        assert screen._current_path.parent == Path(git_project.path)


async def test_dashboard_w_key_opens_workspace(isolated_registry, git_project):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.workspace import WorkspaceScreen

    isolated_registry.add(git_project)
    app = KataDashboard()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        app._update_empty_state()
        await pilot.press("w")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, WorkspaceScreen)
