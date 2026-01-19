"""Kata - Terminal-centric workspace orchestrator for tmux."""

try:
    from kata._version import __version__
except ImportError:
    # Fallback for editable installs without build
    __version__ = "0.0.0.dev0"
