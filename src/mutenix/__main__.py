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


def main(args: argparse.Namespace):
    check_for_self_update(MAJOR, MINOR, PATCH)

    def signal_handler(signal, frame):
        print("Shuting down...")
        _logger.info("SIGINT received, shutting down...")
        asyncio.create_task(macropad.stop())

    if args.list_devices:
        import hid

        for device in hid.enumerate():
            print(device)
        return

    signal.signal(signal.SIGINT, signal_handler)
    macropad = Macropad(args.config)

    if args.update_file:
        _logger.info("Starting manual update with file: %s", args.update_file)
        asyncio.run(macropad.manual_update(args.update_file))
        return

    def run_asyncio_loop():
        asyncio.run(macropad.process())

    loop_thread = threading.Thread(target=run_asyncio_loop)
    loop_thread.start()

    run_trayicon(macropad)

    loop_thread.join()


def runmain():
    args = parse_arguments()
    logging.basicConfig(level=logging.INFO)
    main(args)


if __name__ == "__main__":
    runmain()
