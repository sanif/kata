"""Tests for centralized constants."""

from kata.core.constants import (
    DB_BUSY_TIMEOUT_MS,
    DB_CONNECT_TIMEOUT,
    SESSION_READY_POLL_INTERVAL,
    SESSION_READY_TIMEOUT,
    SUBPROCESS_TIMEOUT,
    SUBPROCESS_TIMEOUT_SHORT,
)


class TestConstants:
    """Verify constants are defined and have valid values."""

    def test_subprocess_timeout_is_positive(self):
        assert SUBPROCESS_TIMEOUT > 0

    def test_subprocess_timeout_short_is_less_than_default(self):
        assert SUBPROCESS_TIMEOUT_SHORT < SUBPROCESS_TIMEOUT

    def test_db_connect_timeout_is_positive(self):
        assert DB_CONNECT_TIMEOUT > 0

    def test_db_busy_timeout_is_positive_ms(self):
        assert DB_BUSY_TIMEOUT_MS > 0

    def test_session_ready_timeout_is_positive(self):
        assert SESSION_READY_TIMEOUT > 0

    def test_session_ready_poll_interval_is_fraction(self):
        assert 0 < SESSION_READY_POLL_INTERVAL < 1
