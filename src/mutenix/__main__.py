import asyncio
import logging
import pathlib
import argparse  # Added import for argparse

from mutenix.version import __version__
from mutenix.updates import check_for_self_update
from mutenix.macropad import Macropad

# Configure logging to write to a file
log_file_path = pathlib.Path.cwd() / "macropad.log"
logging.basicConfig(
    level=logging.INFO,
    filename=log_file_path,
    filemode="a",
    format="%(asctime)s - %(name)-25s [%(levelname)-8s]: %(message)s",
)
_logger = logging.getLogger(__name__)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Mutenix Macropad Controller")
    parser.add_argument('--update-file', type=str, help='Path to the update tar.gz file')
    return parser.parse_args()

async def main(args: argparse.Namespace):
    check_for_self_update(__version__)
    macropad = Macropad(vid=0x2E8A, pid=0x2083)

    if args.update_file:
        _logger.info("Starting manual update with file: %s", args.update_file)
        await macropad.manual_update(args.update_file)
        return

    await macropad.process()

if __name__ == "__main__":
    args = parse_arguments()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(args))
