# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import logging
import os
import pathlib
import subprocess
import sys
import tempfile

import psutil

_logger = logging.getLogger(__name__)


def bring_teams_to_foreground() -> None:  # pragma: no cover
    try:
        # Get the window ID of Microsoft Teams
        window_id = (
            subprocess.check_output(
                "xdotool search --name 'Microsoft Teams'",
                shell=True,
            )
            .strip()
            .decode()
        )
        # Activate the window
        os.system(f"xdotool windowactivate {window_id}")
    except Exception as e:
        _logger.error("Microsoft Teams window not found: %s", e)


def ensure_process_run_once(
    lockfile_path: pathlib.Path = pathlib.Path(tempfile.gettempdir()),
):
    def outerwrapper(func):
        def wrapper(*args, **kwargs):
            lock_file = lockfile_path / "mutenix.lock"
            _logger.info("Using Lock file: %s", lock_file)
            if lock_file.exists():
                _logger.debug("Lock file exists. Another instance might be running.")
                try:
                    with lock_file.open("r") as f:
                        pid = int(f.read().strip())
                    _logger.info("Found PID %s in lock file", pid)
                    if psutil.pid_exists(pid):
                        _logger.error(
                            "The other instance %s is still running, exiting this one",
                            pid,
                        )
                        sys.exit(1)
                except (OSError, ValueError):
                    _logger.info("Stale lock file found. Removing and continuing.")
                _logger.info("Removing lockfile")
                lock_file.unlink()
            with lock_file.open("w") as f:
                f.write(str(os.getpid()))
            try:
                result = func(*args, **kwargs)
            finally:
                lock_file.unlink()
            return result

        return wrapper

    return outerwrapper
