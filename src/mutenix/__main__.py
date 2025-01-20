# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import argparse  # Added import for argparse
import asyncio
import logging
import os
import pathlib
import signal
import tempfile
import threading

from mutenix.macropad import Macropad
from mutenix.tray_icon import run_trayicon
from mutenix.updates import check_for_self_update
from mutenix.version import MAJOR
from mutenix.version import MINOR
from mutenix.version import PATCH

# Configure logging to write to a file
log_file_path = pathlib.Path.cwd() / "mutenix.log"
logging.basicConfig(
    level=logging.INFO,
    filename=log_file_path,
    filemode="a",
    format="%(asctime)s - %(name)-25s [%(levelname)-8s]: %(message)s",
)
_logger = logging.getLogger(__name__)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Mutenix Macropad Controller")
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        help="Path to the configuration file",
    )
    parser.add_argument(
        "--update-file",
        type=str,
        help="Path to the update tar.gz file",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List all connected devices",
    )
    return parser.parse_args()


def register_signal_handler(macropad: Macropad):
    """
    Registers a signal handler to shut down the Macropad gracefully on SIGINT.
    Args:
        macropad (Macropad): The Macropad instance to be shut down on SIGINT.
    """

    def signal_handler(signal, frame):  # pragma: no cover
        print("Shuting down...")
        _logger.info("SIGINT received, shutting down...")
        asyncio.create_task(macropad.stop())

    signal.signal(signal.SIGINT, signal_handler)


def list_devices():
    import hid

    for device in hid.enumerate():
        print(device)


def ensure_only_once(func):
    def wrapper(*args, **kwargs):
        lock_file = pathlib.Path(tempfile.gettempdir()) / "mutenix.lock"
        _logger.info("Using Lock file: %s", lock_file)
        if lock_file.exists():
            _logger.error("Lock file exists. Another instance might be running.")
            try:
                with lock_file.open("r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                _logger.error(
                    "The other instance %s is still runnning, exiting this one",
                    pid,
                )
                exit(1)
            except (OSError, ValueError):
                _logger.info("Stale lock file found. Removing and continuing.")
                lock_file.unlink()
                with lock_file.open("w") as f:
                    f.write(str(os.getpid()))
                lock_file.touch()
                return func(*args, **kwargs)
        else:
            with lock_file.open("w") as f:
                f.write(str(os.getpid()))
            lock_file.touch()
            try:
                return func(*args, **kwargs)
            finally:
                lock_file.unlink()

    return wrapper


@ensure_only_once
def main(args: argparse.Namespace):
    if args.list_devices:
        return list_devices()

    check_for_self_update(MAJOR, MINOR, PATCH)

    macropad = Macropad(args.config)
    register_signal_handler(macropad)

    if args.update_file:
        _logger.info("Starting manual update with file: %s", args.update_file)
        asyncio.run(macropad.manual_update(args.update_file))
        return

    def run_asyncio_loop():  # pragma: no cover
        asyncio.run(macropad.process())

    _logger.info("Running Main Thread")
    loop_thread = threading.Thread(target=run_asyncio_loop)
    loop_thread.start()

    _logger.info("Tray icon start")
    run_trayicon(macropad)
    _logger.info("Tray icon stopped")

    loop_thread.join()
    _logger.info("Trhead joined")


def runmain():  # pragma: no cover
    args = parse_arguments()
    logging.basicConfig(level=logging.INFO)
    main(args)


if __name__ == "__main__":  # pragma: no cover
    runmain()
