"""Tests for shared notification utilities."""

from datetime import datetime, timedelta

from kata.services.notifications.models import NotificationType
from kata.utils.notifications import TYPE_ICONS, escape_rich, time_ago


class TestTimeAgo:
    def test_now(self):
        assert time_ago(datetime.now()) == "now"

    def test_minutes(self):
        assert time_ago(datetime.now() - timedelta(minutes=5)) == "5m"

    def test_hours(self):
        assert time_ago(datetime.now() - timedelta(hours=3)) == "3h"

    def test_days(self):
        assert time_ago(datetime.now() - timedelta(days=2)) == "2d"

    def test_future_returns_empty(self):
        assert time_ago(datetime.now() + timedelta(hours=1)) == ""


class TestEscapeRich:
    def test_escapes_brackets(self):
        assert escape_rich("[bold]text[/bold]") == r"\[bold]text\[/bold]"

    def test_empty_string(self):
        assert escape_rich("") == ""

    def test_no_brackets(self):
        assert escape_rich("plain text") == "plain text"


class TestTypeIcons:
    def test_all_types_have_icons(self):
        for t in NotificationType:
            assert t in TYPE_ICONS, f"Missing icon for {t}"
