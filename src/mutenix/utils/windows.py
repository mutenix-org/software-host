# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import logging
import pathlib
import sys
import tempfile

import win32api  # type: ignore
import win32con  # type: ignore
import win32event  # type: ignore
import win32gui  # type: ignore
from pywinauto.findwindows import find_windows  # type: ignore
from winerror import ERROR_ALREADY_EXISTS  # type: ignore

_logger = logging.getLogger(__name__)


def bring_teams_to_foreground() -> None:  # pragma: no cover
    """
    Bring the Microsoft Teams window to the foreground.

    This function attempts to bring the Microsoft Teams application window to the foreground
    on different operating systems (Windows, macOS, and Linux). It uses platform-specific
    methods to achieve this.

    On Windows, it uses the `win32gui` and `win32con` modules to minimize and restore the window.
    Note: This function will not be coverable due to its OS dependencies.
    """
    try:
        _logger.debug("Finding Microsoft Teams window")
        window_id = find_windows(title_re=".*Teams.*")
        _logger.debug("Window ID: %s", window_id)
        for w in window_id:
            _logger.debug("Minimizing and restoring window %s", w)
            win32gui.ShowWindow(w, win32con.SW_MINIMIZE)
            win32gui.ShowWindow(w, win32con.SW_RESTORE)
            win32gui.ShowWindow(w, win32con.SW_SHOWMAXIMIZED)
            win32gui.ShowWindow(w, win32con.SW_SHOWNORMAL)
            win32gui.SetActiveWindow(w)
    except Exception as e:
        _logger.warning(
            "Could not bring Microsoft Teams window to the foreground, %s",
            e,
        )


def ensure_process_run_once(
    lockfile_path: pathlib.Path = pathlib.Path(tempfile.gettempdir()),
):
    def outerwrapper(func):
        def wrapper(*args, **kwargs):
            mutex = win32event.CreateMutex(None, False, "mutenix_instance")
            last_error = win32api.GetLastError()

            if last_error == ERROR_ALREADY_EXISTS:
                print("App instance already running")
                _logger.error("Another instance of the application is already running.")
                sys.exit(1)
            try:
                result = func(*args, **kwargs)
            finally:
                win32event.ReleaseMutex(mutex)
            return result

        return wrapper

    return outerwrapper
