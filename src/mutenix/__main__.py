# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import argparse  # Added import for argparse
import asyncio
import logging
import pathlib
import signal
import threading

import daiquiri
from mutenix.config import load_config
from mutenix.config import LoggingConfig
from mutenix.macropad import Macropad
from mutenix.tray_icon import run_trayicon
from mutenix.updates import check_for_self_update
from mutenix.utils import ensure_process_run_once
from mutenix.version import MAJOR
from mutenix.version import MINOR
from mutenix.version import PATCH

# Configure logging to write to a file
logging.basicConfig(level=logging.ERROR)
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

    for device in sorted(hid.enumerate(), key=lambda x: x["vendor_id"]):
        if "mutenix" in device["product_string"].lower():
            print("********** ")
        print(device)


def setup_logging(logging_config: LoggingConfig):
    log_file_path = logging_config.file_path or pathlib.Path.cwd() / "mutenix.log"
    log_level = logging_config.level.to_logging_level()
    outputs = []
    if logging_config.file_enabled:
        file_log_level = (
            logging_config.file_level.to_logging_level()
            if logging_config.file_level
            else log_level
        )
        outputs.append(
            daiquiri.output.RotatingFile(
                log_file_path,
                level=file_log_level,
                max_size_bytes=logging_config.file_max_size,
                backup_count=logging_config.file_backup_count,
            ),
        )
    if logging_config.console_enabled:
        console_log_level = (
            logging_config.console_level.to_logging_level()
            if logging_config.console_level
            else log_level
        )
        outputs.append(
            daiquiri.output.Stream(
                level=console_log_level,
                formatter=daiquiri.formatter.ColorExtrasFormatter(
                    fmt="%(asctime)s - %(name)-25s [%(levelname)-8s]: %(message)s",
                ),
            ),
        )
    daiquiri.setup(
        level=log_level,
        outputs=outputs,
    )
    daiquiri.parse_and_set_default_log_levels(logging_config.submomdules)
    global _logger


@ensure_process_run_once()
def main(args: argparse.Namespace):
    config = load_config(args.config)
    print(config.logging)

    setup_logging(config.logging)

    if args.list_devices:
        return list_devices()

    check_for_self_update(MAJOR, MINOR, PATCH)
    macropad = Macropad(config)
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
