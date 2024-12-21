import requests
import semver
import tarfile
import io
import tempfile
import pathlib
import time
import os
import hid
from abc import abstractmethod
from tqdm import tqdm
from mutenix.hid_commands import VersionInfo
import logging
from mutenix.version import __version__

_logger = logging.getLogger(__name__)

# region: Update Firmware
def check_for_device_update(device: hid.device, device_version: VersionInfo):
    try:
        result = requests.get(
            f"https://mutenix.de/api/v1/releases/macropad-{device_version.type.name}"
        )
        if result.status_code != 200:
            _logger.error(
                "Failed to download the release info, status code: %s",
                result.status_code,
            )
            return

        releases = result.json()
        latest_version = releases.get("latest", "0.0.0")
        _logger.debug("Latest version: %s", latest_version)
        if semver.compare(device_version.version, latest_version) >= 0:
            _logger.info("Device is up to date")
            return

        print("Device update available, starting update, please be patient")
        update_url = releases.get(latest_version).get("url")
        result = requests.get(update_url)
        result.raise_for_status()
        with tempfile.TemporaryDirectory() as tmpdirname:
            with tarfile.open(fileobj=io.BytesIO(result.content), mode="r:gz") as tar:
                tar.extractall(path=tmpdirname)
            files = list(filter(lambda x: x.endswith(".py"), os.listdir(tmpdirname)))
            perform_hid_upgrade(device, files)
            _logger.info("Successfully updated device firmware")
    except requests.RequestException as e:
        _logger.error("Failed to check for device update availability", e)


HEADER_SIZE = 8
MAX_CHUNK_SIZE = 60 - HEADER_SIZE
DATA_TRANSFER_SLEEP_TIME = 0.02
STATE_CHANGE_SLEEP_TIME = 0.5


class RequestChunk:
    def __init__(self, data: bytes):
        self.id = 0
        self.segment = 0
        self.parse(data)

    def parse(self, data: bytes):
        self.identifier = data[:2].decode("utf-8")
        if self.identifier != "RQ":
            return
        self.id = int.from_bytes(data[2:4], "little")
        self.segment = int.from_bytes(data[4:6], "little")
        _logger.info("Chunk request: %s", self)

    def is_valid(self):
        return self.identifier == "RQ"

    def __str__(self):
        if self.is_valid():
            return f"File: {self.id}, Package: {self.segment}"
        return "Invalid Request"


class Chunk:
    @abstractmethod
    def packet(self):
        pass


class FileChunk(Chunk):
    def __init__(self, id: int, package: int, total_packages: int, content: bytes):
        self.id = id
        self.package = package
        self.total_packages = total_packages
        self.content = content

    def packet(self):
        return (
            int(2).to_bytes(2, "little")
            + self.id.to_bytes(2, "little")
            + self.total_packages.to_bytes(2, "little")
            + self.package.to_bytes(2, "little")
            + self.content
            + b"\0" * (MAX_CHUNK_SIZE - len(self.content))
        )


class FileStart(Chunk):
    def __init__(
        self, id: int, package: int, total_packages: int, filename: str, filesize: int
    ):
        self.id = id
        self.package = package
        self.total_packages = total_packages
        self.content = (
            bytes((len(filename),))
            + filename.encode("utf-8")
            + bytes((2,))
            + filesize.to_bytes(2, "little")
        )

    def packet(self):
        return (
            int(1).to_bytes(2, "little")
            + self.id.to_bytes(2, "little")
            + self.total_packages.to_bytes(2, "little")
            + self.package.to_bytes(2, "little")
            + self.content
            + b"\0" * (MAX_CHUNK_SIZE - len(self.content))
        )


class FileEnd(Chunk):
    def __init__(self, id: int):
        self.id = id

    def packet(self):
        return (
            int(3).to_bytes(2, "little")
            + self.id.to_bytes(2, "little")
            + b"\0" * (MAX_CHUNK_SIZE + 4)
        )


class TransferFile:
    def __init__(self, id, filename: str):
        self.id = id
        file = pathlib.Path(filename)
        self.filename = file.name
        with open(file, "rb") as f:
            self.content = f.read()
        self.size = len(self.content)
        self.packages_sent: list[int] = []
        self._chunks: list[Chunk] = []
        self.make_chunks()
        _logger.debug("File %s has %s chunks", self.filename, len(self._chunks))

    def make_chunks(self):
        total_packages = self.size // MAX_CHUNK_SIZE
        self._chunks.append(
            FileStart(self.id, 0, total_packages, self.filename, self.size)
        )
        for i in range(0, self.size, MAX_CHUNK_SIZE):
            self._chunks.append(
                FileChunk(
                    self.id,
                    i // MAX_CHUNK_SIZE,
                    total_packages,
                    self.content[i : i + MAX_CHUNK_SIZE],
                )
            )
        self._chunks.append(FileEnd(self.id))

    def get_next_chunk(self) -> Chunk:
        next = max(self.packages_sent) + 1 if len(self.packages_sent) > 0 else 0
        self.packages_sent.append(next)
        return self._chunks[next]

    @property
    def chunks(self):
        return len(self._chunks)

    def get_chunk(self, request: RequestChunk) -> Chunk:
        if request.id != self.id:
            raise FileNotFoundError("File not found")
        if request.segment < 0 or request.segment >= len(self._chunks):
            raise ValueError("Invalid request")
        return self._chunks[request.segment + 1]

    def is_complete(self):
        return len(self.packages_sent) == len(self._chunks)


def perform_hid_upgrade(device, files: list[str]):
    _logger.debug("Opening device for update")
    _logger.debug("Sending prepare update")
    device.write([1, 0xE0] + [0] * 7)
    time.sleep(STATE_CHANGE_SLEEP_TIME)

    transfer_files = [TransferFile(i, file) for i, file in enumerate(files)]

    chunk_requests = []
    finished = False
    finished_at = None

    _logger.debug("Preparing to send %s files", len(transfer_files))
    file_progress_bars = {
        file.id: tqdm(
            total=file.chunks, desc=f"{file.id}/{len(transfer_files)} {file.filename}"
        )
        for file in transfer_files
    }

    while True:
        received = device.read(24, 100)
        if len(received) > 0:
            rc = RequestChunk(bytes(received))
            if rc.is_valid():
                chunk_requests.append(rc)

        if len(chunk_requests) > 0:
            _logger.debug("Sending requested chunk")
            cr = chunk_requests.pop(0)
            file = next((f for f in transfer_files if f.id == cr.id), None)
            if not file:
                print("File not found")
                _logger.warning("File not found")
                raise FileNotFoundError("File not found")
            file_chunk = file.get_chunk(cr)
            device.write(bytearray((2,)) + file_chunk.packet())
            time.sleep(DATA_TRANSFER_SLEEP_TIME)

        try:
            file = next(filter(lambda x: not x.is_complete(), transfer_files))
            chunk = file.get_next_chunk()
            if chunk:
                _logger.debug("Sending chunk of file %s", file.filename)
                cnk = bytes((2,)) + chunk.packet()
                device.write(cnk)
                file_progress_bars[file.id].update(1)
                time.sleep(DATA_TRANSFER_SLEEP_TIME)
            else:
                print(f"File {file.filename} transfered")
        except StopIteration:
            if (finished_at and time.monotonic() - finished_at > 5) or (
                not finished_at
            ):
                break
            if not finished:
                print("All files transfered")
                finished = True
                finished_at = time.monotonic()
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    device.write([2, 4] + [0] * 59)
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    print("Resetting")
    device.write([1, 0xE1] + [0] * 7)


# endregion


# region: Update Application
def check_for_self_update():
    try:
        result = requests.get("https://mutenix.de/api/v1/releases/software-python")
        if result.status_code != 200:
            _logger.error(
                "Failed to download the release info, status code: %s",
                result.status_code,
            )
            return

        versions = result.json()
        _logger.debug("Versions: %s", versions)
        latest_version = versions.get("latest", "0.0.0")
        _logger.debug("Latest version: %s", latest_version)
        if semver.compare(__version__, latest_version) >= 0:
            _logger.info("Application is up to date")
            return

        print("Application update available, starting update, please be patient")
        update_url = versions.get(latest_version).get("url")
        result = requests.get(update_url)
        result.raise_for_status()
        if result.status_code == 200:
            with tarfile.open(fileobj=io.BytesIO(result.content), mode="r:gz") as tar:
                tar.extract("macropad.py", path=pathlib.Path(__file__).parent)
                _logger.info("Successfully updated macropad.py")
        else:
            _logger.error(
                "Failed to download the update, status code: %s", result.status_code
            )

    except requests.RequestException as e:
        _logger.error("Failed to check for application update availability", e)


# endregion