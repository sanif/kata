"""Centralized constants for Kata.

All magic numbers, timeout values, and configuration defaults
that are used across multiple modules should be defined here.
"""

# --- Subprocess timeouts (seconds) ---
SUBPROCESS_TIMEOUT = 5
SUBPROCESS_TIMEOUT_SHORT = 2

# --- SQLite database ---
DB_CONNECT_TIMEOUT = 15
DB_BUSY_TIMEOUT_MS = 10000

# --- Session readiness polling ---
SESSION_READY_TIMEOUT = 2.0
SESSION_READY_POLL_INTERVAL = 0.1
SESSION_READY_MAX_RETRIES = int(SESSION_READY_TIMEOUT / SESSION_READY_POLL_INTERVAL)

# --- Unique session name generation ---
SESSION_NAME_MAX_SUFFIX = 100
