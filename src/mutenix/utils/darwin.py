# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import os

from mutenix.utils.linux import ensure_process_run_once


def bring_teams_to_foreground() -> None:  # pragma: no cover
    """
    Bring the Microsoft Teams window to the foreground.

    This function attempts to bring the Microsoft Teams application window to the foreground
    on different operating systems (Windows, macOS, and Linux). It uses platform-specific
    methods to achieve this.

    On macOS, it uses AppleScript commands to activate the application and set it as frontmost.
    """
    os.system("osascript -e 'tell application \"Microsoft Teams\" to activate'")
    os.system(
        'osascript -e \'tell application "System Events" to tell process "Microsoft Teams" to set frontmost to true\'',
    )


__all__ = ["bring_teams_to_foreground", "ensure_process_run_once"]
