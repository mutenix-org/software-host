import os
import platform
import subprocess
import logging
import asyncio
import time
import functools

_logger = logging.getLogger(__name__)

if platform.system().lower() == "windows": # pragma: no cover
    from pywinauto.findwindows import find_windows # type: ignore
    import win32gui # type: ignore
    import win32con # type: ignore
elif platform.system().lower() == "linux": # pragma: no cover
    import subprocess

def bring_teams_to_foreground() -> None: # pragma: no cover
    """
    Bring the Microsoft Teams window to the foreground.

    This function attempts to bring the Microsoft Teams application window to the foreground
    on different operating systems (Windows, macOS, and Linux). It uses platform-specific
    methods to achieve this.

    - On Windows, it uses the `win32gui` and `win32con` modules to minimize and restore the window.
    - On macOS, it uses AppleScript commands to activate the application and set it as frontmost.
    - On Linux, it uses the `xdotool` command to search for and activate the window.

    If the platform is not supported, it logs an error message.

    Note: This function will not be coverable due to its OS dependencies.
    """
    if platform.system().lower() == "windows":
        _logger.debug("Finding Microsoft Teams window")
        window_id = find_windows(title_re=".*Teams.*")
        _logger.debug("Window ID: %s", window_id)
        for w in window_id:
            _logger.debug("Minimizing and restoring window %s", w)
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


def check_run(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._run:
            return func(self, *args, **kwargs)
        else:
            _logger.debug("Not running, skip %s", func.__name__)
    return wrapper

def run_loop(func):
    if asyncio.iscoroutinefunction(func):
        async def wrapper(self, *args, **kwargs):
            while self._run:
                await func(self, *args, **kwargs)
                await asyncio.sleep(0)

    else:
        raise Exception("only for async functions") # pragma: no cover
    return wrapper


def block_parallel(func):
    func._already_running = False
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        _logger.debug("block_parallel %s %s", func.__name__, func._already_running)
        if func._already_running:
            while func._already_running:
                await asyncio.sleep(0.1)
            return
        func._already_running = True
        await func(self, *args, **kwargs)
        func._already_running = False
    return wrapper

def run_till_some_loop(sleep_time: float = 0):
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def wrapper(self, *args, **kwargs):
                while self._run:
                    some = await func(self, *args, **kwargs)
                    if some:
                        return some
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
        else:
            def wrapper(self, *args, **kwargs):
                while self._run:
                    some = func(self, *args, **kwargs)
                    if some:
                        return some
                    if sleep_time > 0:
                        time.sleep(sleep_time)
        return wrapper
    return decorator
