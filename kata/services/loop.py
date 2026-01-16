"""Return loop service for re-launching dashboard after detach."""

from kata.core.settings import get_settings, update_settings


def is_loop_enabled() -> bool:
    """Check if the return loop is enabled.

    Returns:
        True if loop is enabled
    """
    return get_settings().loop_enabled


def set_loop_enabled(enabled: bool) -> None:
    """Set whether the return loop is enabled.

    Args:
        enabled: Whether to enable the loop
    """
    update_settings(loop_enabled=enabled)


def run_with_loop() -> None:
    """Run the TUI dashboard in a loop.

    After the user detaches from a session or exits the TUI,
    the dashboard is immediately re-launched.

    Press 'q' or Ctrl+C to fully exit.
    """
    from kata.tui.app import KataDashboard
    from kata.services.sessions import launch_or_attach, launch_or_attach_adhoc

    print("\n[Kata Return Loop] Dashboard will re-launch after detach.")
    print("[Kata Return Loop] Press 'q' or Ctrl+C to exit completely.\n")

    while True:
        try:
            app = KataDashboard()
            app.run()

            # Check if user explicitly quit (pressed 'q')
            if app._explicit_quit:
                print("\n[Kata Return Loop] Exiting...")
                break

            # After the app exits, check if we need to launch a project or zoxide entry
            project = app._project_to_launch
            zoxide_entry = app._zoxide_to_launch

            if project:
                try:
                    launch_or_attach(project)
                except Exception as e:
                    print(f"\n[Kata] Error: {e}")
                    print("[Kata] Press Enter to continue...")
                    input()
            elif zoxide_entry:
                try:
                    launch_or_attach_adhoc(zoxide_entry.path)
                except Exception as e:
                    print(f"\n[Kata] Error: {e}")
                    print("[Kata] Press Enter to continue...")
                    input()

            # Small delay before re-launching
            import time

            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n[Kata Return Loop] Exiting...")
            break
        except Exception as e:
            print(f"[Kata Return Loop] Error: {e}")
            break


def run_dashboard_with_wrapper() -> None:
    """Run the dashboard with a shell wrapper for detach detection.

    This creates a wrapper that monitors tmux sessions and
    re-launches the dashboard when a session is detached.
    """
    import os
    import shutil

    # Check if we're inside tmux already
    if os.environ.get("TMUX"):
        # We're inside tmux - run directly
        from kata.tui.app import run_dashboard

        run_dashboard()
        return

    # Check if tmux is available
    if not shutil.which("tmux"):
        # No tmux - run directly
        from kata.tui.app import run_dashboard

        run_dashboard()
        return

    # Run with loop if enabled
    if is_loop_enabled():
        run_with_loop()
    else:
        from kata.tui.app import run_dashboard

        run_dashboard()
