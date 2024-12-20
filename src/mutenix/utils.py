import os
import platform
import subprocess
import logging

_logger = logging.getLogger(__name__)

if platform.system().lower() == "windows":
    from pywinauto.findwindows import find_windows # type: ignore
    import win32gui # type: ignore
    import win32con # type: ignore
elif platform.system().lower() == "linux":
    import subprocess

def bring_teams_to_foreground() -> None:
    """Bring the Microsoft Teams window to the foreground."""
    if platform.system().lower() == "windows":
        window_id = find_windows(title_re=".*Teams.*")
        _logger.debug(window_id)
        for w in window_id:
            win32gui.ShowWindow(w, win32con.SW_MINIMIZE)
            win32gui.ShowWindow(w, win32con.SW_RESTORE)
            win32gui.SetActiveWindow(w)

    elif platform.system().lower() == "darwin":
        os.system("osascript -e 'tell application \"Microsoft Teams\" to activate'")
        os.system(
            'osascript -e \'tell application "System Events" to tell process "Microsoft Teams" to set frontmost to true\''
        )
    elif platform.system().lower() == "linux":
        try:
            # Get the window ID of Microsoft Teams
            window_id = (
                subprocess.check_output(
                    "xdotool search --name 'Microsoft Teams'", shell=True
                )
                .strip()
                .decode()
            )
            # Activate the window
            os.system(f"xdotool windowactivate {window_id}")
        except Exception as e:
            _logger.error("Microsoft Teams window not found: %s", e)
    else:
        _logger.error("Platform not supported")
