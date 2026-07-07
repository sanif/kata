"""Tests for the diff viewer: git change collection, Claude-edit awareness, UI."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from kata.core.models import Project


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@test", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def git_repo(tmp_path):
    """A git repo with staged, unstaged, untracked, and deleted changes."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-q"], root)
    (root / "a.py").write_text("line1\n")
    (root / "b.txt").write_text("keep\n")
    (root / "gone.txt").write_text("bye\n")
    _git(["add", "."], root)
    _git(["commit", "-q", "-m", "init"], root)

    (root / "a.py").write_text("line1\nline2\nline3\n")  # modified, unstaged
    (root / "new.txt").write_text("hello\nworld\n")  # untracked
    (root / "blob.bin").write_bytes(b"\x00\x01\x02")  # untracked binary
    (root / "staged.py").write_text("x = 1\n")
    _git(["add", "staged.py"], root)  # staged add
    _git(["rm", "-q", "gone.txt"], root)  # staged delete
    return root


def test_collect_uncommitted_changes(git_repo):
    from kata.utils.git import collect_uncommitted_changes

    changes = collect_uncommitted_changes(git_repo)
    assert changes is not None
    by_rel = {c.rel_path: c for c in changes}

    assert by_rel["a.py"].status == "M"
    assert by_rel["a.py"].added == 2
    assert by_rel["a.py"].removed == 0

    assert by_rel["new.txt"].status == "U"
    assert by_rel["new.txt"].added == 2

    assert by_rel["blob.bin"].status == "U"
    assert by_rel["blob.bin"].added is None  # binary

    assert by_rel["staged.py"].status == "A"
    assert by_rel["staged.py"].added == 1

    assert by_rel["gone.txt"].status == "D"
    assert by_rel["gone.txt"].removed == 1
    assert by_rel["gone.txt"].mtime == 0.0

    # Sorted newest-first; the deleted file (mtime 0) is last.
    assert changes[-1].rel_path == "gone.txt"


def test_collect_returns_none_for_non_git(tmp_path):
    from kata.utils.git import collect_uncommitted_changes

    plain = tmp_path / "plain"
    plain.mkdir()
    assert collect_uncommitted_changes(plain) is None


def test_get_uncommitted_diff(git_repo):
    from kata.utils.git import get_uncommitted_diff

    diff = get_uncommitted_diff(git_repo, "a.py")
    assert diff is not None
    assert "+line2" in diff
    assert "+line3" in diff

    # Staged-only change is included too (diff vs HEAD).
    staged = get_uncommitted_diff(git_repo, "staged.py")
    assert staged is not None
    assert "+x = 1" in staged


def test_build_untracked_diff():
    from kata.tui.screens.diff_viewer import build_untracked_diff

    text = build_untracked_diff("new.txt", "hello\nworld\n")
    assert "+++ b/new.txt" in text
    assert "+hello" in text
    assert "+world" in text
    # No phantom empty added line from the trailing newline.
    assert not text.endswith("+\n") and not text.endswith("+")


# ── Claude session parsing ─────────────────────────────────────


def _write_session(claude_dir: Path, project_path: str, lines: list[str]) -> Path:
    from kata.utils.claude_sessions import _encode_cwd

    session_dir = claude_dir / "projects" / _encode_cwd(project_path)
    session_dir.mkdir(parents=True)
    session_file = session_dir / "abc123.jsonl"
    session_file.write_text("\n".join(lines) + "\n")
    return session_file


def test_get_session_edited_files(tmp_path):
    from kata.utils.claude_sessions import get_session_edited_files

    project = tmp_path / "proj"
    project.mkdir()
    claude_dir = tmp_path / ".claude"

    def tool_use(name: str, key: str, value: str) -> str:
        return json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": name, "input": {key: value}},
                        {"type": "text", "text": "done"},
                    ]
                },
            }
        )

    lines = [
        "not json at all {{{",
        json.dumps({"type": "user", "message": {"content": "hi"}}),
        tool_use("Edit", "file_path", str(project / "edited.py")),
        tool_use("Write", "file_path", str(project / "written.md")),
        tool_use("NotebookEdit", "notebook_path", str(project / "nb.ipynb")),
        tool_use("Read", "file_path", str(project / "only_read.py")),  # not an edit
        json.dumps({"type": "assistant", "message": {"content": "plain string"}}),
        json.dumps([1, 2, 3]),  # non-dict entry
    ]
    _write_session(claude_dir, str(project), lines)

    edited = get_session_edited_files(str(project), claude_dir=claude_dir)
    names = {p.name for p in edited}
    assert names == {"edited.py", "written.md", "nb.ipynb"}


def test_get_session_edited_files_no_session(tmp_path):
    from kata.utils.claude_sessions import get_session_edited_files

    assert get_session_edited_files(str(tmp_path / "nope"), claude_dir=tmp_path) == set()


# ── Screen tests (pilot) ───────────────────────────────────────


import kata.services.registry as registry_module  # noqa: E402


@pytest.fixture
def isolated_registry(tmp_path):
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps({"version": "1.0", "projects": []}))
    with patch.object(registry_module, "REGISTRY_FILE", registry_file):
        with patch.object(registry_module, "ensure_config_dirs"):
            registry_module._registry = None
            yield registry_module.get_registry()
            registry_module._registry = None


async def test_diff_screen_lists_changes(isolated_registry, git_repo):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.diff_viewer import DiffViewerScreen

    isolated_registry.add(Project(name="repo", path=str(git_repo)))
    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        with patch(
            "kata.tui.screens.diff_viewer.get_session_edited_files",
            return_value=set(),
        ):
            screen = DiffViewerScreen(git_repo, title="repo")
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()

            assert len(screen._files) == 5
            rels = [f.rel_path for f in screen._files]
            assert "a.py" in rels and "new.txt" in rels and "gone.txt" in rels
            # List pane visible, empty message hidden.
            assert screen.query_one("#dv-body").display is True
            assert screen.query_one("#dv-empty").display is False


async def test_diff_screen_non_git_shows_message(isolated_registry, tmp_path):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.diff_viewer import DiffViewerScreen

    plain = tmp_path / "plain"
    plain.mkdir()
    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = DiffViewerScreen(plain, title="plain")
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.pause()

        assert screen.query_one("#dv-empty").display is True
        from textual.widgets import Static

        assert "Not a git repository" in str(
            getattr(screen.query_one("#dv-empty", Static), "_Static__content", "")
        )


async def test_diff_screen_clean_tree_shows_message(isolated_registry, tmp_path):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.diff_viewer import DiffViewerScreen

    root = tmp_path / "clean"
    root.mkdir()
    _git(["init", "-q"], root)
    (root / "a.txt").write_text("x\n")
    _git(["add", "."], root)
    _git(["commit", "-q", "-m", "init"], root)

    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        with patch(
            "kata.tui.screens.diff_viewer.get_session_edited_files",
            return_value=set(),
        ):
            screen = DiffViewerScreen(root, title="clean")
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()

            assert screen.query_one("#dv-empty").display is True
            from textual.widgets import Static

            assert "clean" in str(
                getattr(screen.query_one("#dv-empty", Static), "_Static__content", "")
            )


async def test_claude_filter(isolated_registry, git_repo):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.diff_viewer import DiffViewerScreen

    claude_edited = {(git_repo / "a.py").resolve()}
    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        with patch(
            "kata.tui.screens.diff_viewer.get_session_edited_files",
            return_value=claude_edited,
        ):
            screen = DiffViewerScreen(git_repo, title="repo")
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()

            assert len(screen._visible) == 5
            await pilot.press("c")
            await pilot.pause()
            assert [f.rel_path for f in screen._visible] == ["a.py"]
            # Toggle back off restores the full list.
            await pilot.press("c")
            await pilot.pause()
            assert len(screen._visible) == 5


async def test_claude_filter_without_session_shows_hint(isolated_registry, git_repo):
    from textual.widgets import OptionList

    from kata.tui.app import KataDashboard
    from kata.tui.screens.diff_viewer import DiffViewerScreen

    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        with patch(
            "kata.tui.screens.diff_viewer.get_session_edited_files",
            return_value=set(),
        ):
            screen = DiffViewerScreen(git_repo, title="repo")
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()

            await pilot.press("c")
            await pilot.pause()
            assert screen._visible == []
            option_list = screen.query_one("#dv-files", OptionList)
            assert option_list.option_count == 1  # the hint line


async def test_untracked_file_diff_renders_additions(isolated_registry, git_repo):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.diff_viewer import DiffViewerScreen

    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        with patch(
            "kata.tui.screens.diff_viewer.get_session_edited_files",
            return_value=set(),
        ):
            screen = DiffViewerScreen(git_repo, title="repo")
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()

            # Highlight the untracked new.txt.
            index = next(i for i, f in enumerate(screen._visible) if f.rel_path == "new.txt")
            from textual.widgets import OptionList

            screen.query_one("#dv-files", OptionList).highlighted = index
            await pilot.pause()
            await pilot.pause()

            from rich.syntax import Syntax
            from textual.widgets import Static

            body = screen.query_one("#dv-diff", Static)
            content = getattr(body, "_Static__content", None)
            assert isinstance(content, Syntax)
            assert "+hello" in content.code
