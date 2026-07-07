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

# --- Notification daemon client (seconds) ---
# Never let a hook block on a wedged daemon: connect + each request/response
# is bounded by these so send_notification_sync falls back to SQLite fast.
NOTIFY_CONNECT_TIMEOUT = 1.0
NOTIFY_CLIENT_TIMEOUT = 2.0

# --- Notification daemon store pruning ---
NOTIFYD_PRUNE_INTERVAL_SECONDS = 3600.0

# --- Session readiness polling ---
SESSION_READY_TIMEOUT = 2.0
SESSION_READY_POLL_INTERVAL = 0.1
SESSION_READY_MAX_RETRIES = int(SESSION_READY_TIMEOUT / SESSION_READY_POLL_INTERVAL)

# --- Unique session name generation ---
SESSION_NAME_MAX_SUFFIX = 100

# --- Worktree management ---
WORKTREE_SPINNER_INTERVAL = 0.08
