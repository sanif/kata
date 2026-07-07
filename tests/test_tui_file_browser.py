"""Pilot tests for the in-TUI file browser and file viewers."""

import json
from unittest.mock import patch

import pytest

import kata.services.registry as registry_module
from kata.core.models import Project


@pytest.fixture
def isolated_registry(tmp_path):
    """Point the registry singleton at a temp file and reset it afterwards."""
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps({"version": "1.0", "projects": []}))
    with patch.object(registry_module, "REGISTRY_FILE", registry_file):
        with patch.object(registry_module, "ensure_config_dirs"):
            registry_module._registry = None
            yield registry_module.get_registry()
            registry_module._registry = None


@pytest.fixture
def sample_project(tmp_path):
    """Create a project directory with a mix of files and noise dirs."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "README.md").write_text("# Title\n\nHello **world**.\n")
    (root / "main.py").write_text("def hello():\n    return 42\n")
    (root / "notes.txt").write_text("plain notes\n")
    (root / "blob.bin").write_bytes(b"\x00\x01\x02\x03binarydata\x00")
    # Noise dirs that should be filtered out of the tree.
    for noise in (".git", "node_modules", "__pycache__", ".venv"):
        (root / noise).mkdir()
        (root / noise / "junk.txt").write_text("junk")
    # A hidden file (should be hidden by default).
    (root / ".secret").write_text("hidden")
    return Project(name="proj", path=str(root))


async def _open_browser(app, project):
    """Register the project, highlight it, and open the browser via `f`."""
    from kata.tui.widgets.tree import ProjectTree

    tree = app.query_one(ProjectTree)
    tree.refresh_projects()
    # Directly invoke the action after ensuring a project is selected.
    inner = tree.query_one("#project-tree")
    for group_node in inner.root.children:
        for pnode in group_node.children:
            if pnode.data and pnode.data.get("type") == "project":
                inner.move_cursor(pnode)
                break
    app.action_browse_files()


async def test_browser_opens_and_filters_noise(isolated_registry, sample_project):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.file_browser import FileBrowserScreen, FilteredDirectoryTree

    isolated_registry.add(sample_project)
    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._update_empty_state()
        await _open_browser(app, sample_project)
        await pilot.pause()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, FileBrowserScreen)

        dtree = screen.query_one(FilteredDirectoryTree)
        # Expand the root so children load, then let the tree populate.
        dtree.root.expand()
        await pilot.pause()
        await pilot.pause()

        # Collect visible child names under the root.
        names = {(node.data.path.name if node.data else "") for node in dtree.root.children}
        # Noise dirs and dotfiles filtered out.
        assert ".git" not in names
        assert "node_modules" not in names
        assert "__pycache__" not in names
        assert ".venv" not in names
        assert ".secret" not in names
        # Real files present.
        assert "README.md" in names
        assert "main.py" in names


async def test_toggle_hidden_reveals_dotfiles(isolated_registry, sample_project):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.file_browser import FilteredDirectoryTree

    isolated_registry.add(sample_project)
    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._update_empty_state()
        await _open_browser(app, sample_project)
        await pilot.pause()

        screen = app.screen
        screen.action_toggle_hidden()
        await pilot.pause()

        dtree = screen.query_one(FilteredDirectoryTree)
        assert dtree.show_hidden is True
        dtree.root.expand()
        await pilot.pause()
        await pilot.pause()
        names = {(node.data.path.name if node.data else "") for node in dtree.root.children}
        assert ".secret" in names
        # Noise dirs stay filtered even with hidden shown.
        assert ".git" not in names


async def test_markdown_file_opens_markdown_viewer(isolated_registry, sample_project):
    from textual.widgets import MarkdownViewer

    from kata.tui.app import KataDashboard
    from kata.tui.screens.file_viewer import MarkdownViewerScreen, open_file

    isolated_registry.add(sample_project)
    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        from pathlib import Path

        md = Path(sample_project.path) / "README.md"
        open_file(app, md, project_root=Path(sample_project.path))
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, MarkdownViewerScreen)
        assert app.screen.query_one(MarkdownViewer) is not None
        # TOC toggle works.
        viewer = app.screen.query_one(MarkdownViewer)
        before = viewer.show_table_of_contents
        app.screen.action_toggle_toc()
        await pilot.pause()
        assert viewer.show_table_of_contents is (not before)


async def test_text_file_shows_syntax_view(isolated_registry, sample_project):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.file_viewer import TextViewerScreen, open_file

    isolated_registry.add(sample_project)
    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        from pathlib import Path

        py = Path(sample_project.path) / "main.py"
        open_file(app, py, project_root=Path(sample_project.path))
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, TextViewerScreen)
        from textual.widgets import Static

        body = app.screen.query_one("#tv-body", Static)
        # Rich Syntax renderable was applied (not the loading placeholder).
        from rich.syntax import Syntax

        content = getattr(body, "_Static__content", None)
        assert isinstance(content, Syntax)


async def test_binary_file_shows_guard_message(isolated_registry, sample_project):
    from kata.tui.app import KataDashboard
    from kata.tui.screens.file_viewer import TextViewerScreen, open_file

    isolated_registry.add(sample_project)
    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        from pathlib import Path

        blob = Path(sample_project.path) / "blob.bin"
        open_file(app, blob, project_root=Path(sample_project.path))
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, TextViewerScreen)
        from textual.widgets import Static

        body = app.screen.query_one("#tv-body", Static)
        text = str(body.render())
        assert "Binary file" in text


def test_read_text_file_guards(tmp_path):
    from kata.tui.screens.file_viewer import MAX_FILE_BYTES, read_text_file

    # Binary
    binary = tmp_path / "b.bin"
    binary.write_bytes(b"abc\x00def")
    assert read_text_file(binary)[0] == "binary"

    # Normal text
    text = tmp_path / "t.txt"
    text.write_text("hello\nworld\n")
    kind, payload = read_text_file(text)
    assert kind == "ok"
    assert "hello" in payload

    # Oversized -> truncated notice
    big = tmp_path / "big.txt"
    big.write_text("x" * (MAX_FILE_BYTES + 5000))
    kind, payload = read_text_file(big)
    assert kind == "ok"
    assert "truncated" in payload


def test_extract_file_references():
    from kata.utils.paths import extract_file_references

    refs = extract_file_references("Fixed /a/b/c.py:42 and see ~/notes/x.md too")
    assert ("/a/b/c.py", 42) in refs
    assert ("~/notes/x.md", None) in refs
    # No false positives on plain prose.
    assert extract_file_references("task complete, no files here") == []


async def test_notification_center_linkifies_existing_paths(isolated_registry, tmp_path):
    """A notification body referencing a real file gains a clickable file node."""
    from kata.tui.app import KataDashboard
    from kata.tui.screens.notification_center import NotificationCenterModal

    real_file = tmp_path / "report.py"
    real_file.write_text("x = 1\n")

    grouped = {
        "mysess": [
            _FakeNotification(
                id="n1",
                body=f"Task done. See {real_file}:1 for details.\nmore context here",
            )
        ]
    }

    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        with patch(
            "kata.tui.screens.notification_center.load_grouped",
            return_value=grouped,
        ):
            modal = NotificationCenterModal()
            await app.push_screen(modal)
            await pilot.pause()
            await pilot.pause()

            # Walk the tree for a file_path node pointing at our real file.
            from textual.widgets import Tree

            tree = modal.query_one("#nc-tree", Tree)

            def _walk(node):
                yield node
                for c in node.children:
                    yield from _walk(c)

            file_nodes = [
                n for n in _walk(tree.root) if n.data and n.data.get("type") == "file_path"
            ]
            assert file_nodes, "expected a clickable file_path node"
            assert file_nodes[0].data["path"] == str(real_file)
            assert file_nodes[0].data["line"] == 1


class _FakeNotification:
    """Minimal stand-in for a Notification (only fields the tree reads)."""

    def __init__(self, *, id: str, body: str) -> None:
        from datetime import datetime

        from kata.services.notifications.models import NotificationStatus, NotificationType

        self.id = id
        self.body = body
        self.title = "Task complete"
        self.type = NotificationType.TASK_COMPLETE
        self.status = NotificationStatus.UNREAD
        self.timestamp = datetime.now()
