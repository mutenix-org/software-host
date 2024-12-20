import asyncio
import logging
import pathlib
from version import __version__

from mutenix.updates import check_for_self_update
from mutenix.macropad import Macropad

# Configure logging to write to a file
log_file_path = pathlib.Path(__file__).parent / "macropad.log"
logging.basicConfig(
    level=logging.INFO,
    filename=log_file_path,
    filemode="a",
    format="%(asctime)s - %(name)-25s [%(levelname)-8s]: %(message)s",
)
_logger = logging.getLogger(__name__)

async def main():
    check_for_self_update(__version__)
    macropad = Macropad(vid=0x2E8A, pid=0x2083)
    await macropad.process()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
