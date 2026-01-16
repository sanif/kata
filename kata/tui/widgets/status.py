"""Status indicator widget for session states."""

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from kata.core.models import SessionStatus


class StatusIndicator(Widget):
    """Widget showing session status with colored indicator."""

    DEFAULT_CSS = """
    StatusIndicator {
        width: auto;
        height: 1;
    }

    StatusIndicator .status-active {
        color: $success;
    }

    StatusIndicator .status-detached {
        color: $warning;
    }

    StatusIndicator .status-idle {
        color: $text-muted;
    }
    """

    status: reactive[SessionStatus] = reactive(SessionStatus.IDLE)

    def __init__(
        self,
        status: SessionStatus = SessionStatus.IDLE,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the status indicator.

        Args:
            status: Initial session status
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.status = status

    def compose(self):
        """Compose the widget."""
        yield Static(self._get_indicator(), classes=self._get_class())

    def _get_indicator(self) -> str:
        """Get the indicator character for current status."""
        indicators = {
            SessionStatus.ACTIVE: "◆",
            SessionStatus.DETACHED: "◆",
            SessionStatus.IDLE: "◇",
        }
        return indicators.get(self.status, "◇")

    def _get_class(self) -> str:
        """Get the CSS class for current status."""
        classes = {
            SessionStatus.ACTIVE: "status-active",
            SessionStatus.DETACHED: "status-detached",
            SessionStatus.IDLE: "status-idle",
        }
        return classes.get(self.status, "status-idle")

    def watch_status(self, new_status: SessionStatus) -> None:
        """React to status changes."""
        self.refresh()

    def update_status(self, status: SessionStatus) -> None:
        """Update the status indicator.

        Args:
            status: New status to display
        """
        self.status = status
