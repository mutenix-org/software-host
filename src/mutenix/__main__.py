# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import argparse  # Added import for argparse
import asyncio
import logging
import pathlib
import signal
import threading

from mutenix.macropad import Macropad
from mutenix.tray_icon import run_trayicon
from mutenix.updates import check_for_self_update
from mutenix.utils import ensure_process_run_once
from mutenix.version import MAJOR
from mutenix.version import MINOR
from mutenix.version import PATCH

# Configure logging to write to a file
log_file_path = pathlib.Path.cwd() / "mutenix.log"
logging.basicConfig(
    level=logging.DEBUG,
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
        asyncio.run(macropad.stop())

    signal.signal(signal.SIGINT, signal_handler)


def list_devices():
    import hid

    for device in hid.enumerate():
        print(device)


@ensure_process_run_once()
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
