from __future__ import annotations

import io
import logging
import os
import pathlib
import tarfile
import tempfile
import time
import webbrowser
from abc import abstractmethod
from collections.abc import Sequence
from typing import BinaryIO

import hid
import requests
import semver
from mutenix.hid_commands import VersionInfo
from tqdm import tqdm

_logger = logging.getLogger(__name__)


def check_for_device_update(device: hid.device, device_version: VersionInfo):
    try:
        result = requests.get(
            "https://api.github.com/repos/mutenix-org/firmware-macroboard/releases/latest",
        )
        if result.status_code != 200:
            _logger.error(
                "Failed to fetch latest release info, status code: %s",
                result.status_code,
            )
            return

        releases = result.json()
        latest_version = releases.get("tag_name", "v0.0.0")[1:]
        _logger.debug("Latest version: %s", latest_version)
        if semver.compare(device_version.version, latest_version) >= 0:
            _logger.info("Device is up to date")
            return

        print("Device update available, starting update, please be patient")
        assets = releases.get("assets", [])
        for asset in assets:
            if asset.get("name") == f"v{latest_version}.tar.gz":
                update_url = asset.get("browser_download_url")
                result = requests.get(update_url)
                result.raise_for_status()
                perform_upgrade_with_file(device, io.BytesIO(result.content))
                return
    except requests.RequestException as e:
        _logger.error("Failed to check for device update availability %s", e)


HEADER_SIZE = 8
MAX_CHUNK_SIZE = 60 - HEADER_SIZE
DATA_TRANSFER_SLEEP_TIME = 0.02
STATE_CHANGE_SLEEP_TIME = 0.5
WAIT_FOR_REQUESTS_SLEEP_TIME = STATE_CHANGE_SLEEP_TIME


def perform_upgrade_with_file(device: hid.device, file_stream: BinaryIO):
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = pathlib.Path(tmpdirname)
        with tarfile.open(fileobj=file_stream, mode="r:gz") as tar:
            tar.extractall(path=tmpdirname)
        files = list(
            map(
                lambda x: tmpdir / x,
                filter(
                    lambda x: x.endswith(".py") and not x.startswith("."),
                    os.listdir(tmpdirname),
                ),
            ),
        )
        _logger.debug("Updateing device with files: %s", files)
        perform_hid_upgrade(device, files)
        _logger.info("Successfully updated device firmware")


class DeviceFileChunk:
    def __init__(self, data: bytes):
        self.id = 0
        self.segment = 0
        self.parse(data)

    def parse(self, data: bytes):
        self.identifier = data[:2].decode("utf-8")
        if not self.is_valid():
            return
        self.id = int.from_bytes(data[2:4], "little")
        self.segment = int.from_bytes(data[4:6], "little")
        _logger.info("Chunk request: %s", self)

    def is_valid(self):
        return self.identifier in ["RQ", "AK"]

    @property
    def is_request(self):
        return self.identifier == "RQ"

    @property
    def is_ack(self):
        return self.identifier == "AK"

    def __str__(self):
        if self.is_valid():
            return f"File: {self.id}, Package: {self.segment}"
        return "Invalid Request"


class Chunk:
    @abstractmethod
    def packet(self):  # pragma: no cover
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
        self,
        id: int,
        package: int,
        total_packages: int,
        filename: str,
        filesize: int,
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


class FileDelete(Chunk):
    def __init__(
        self,
        id: int,
        filename: str,
    ):
        self.id = id
        self.content = bytes((len(filename),)) + filename.encode("utf-8")

    def packet(self):
        return (
            int(5).to_bytes(2, "little")
            + self.id.to_bytes(2, "little")
            + self.content
            + b"\0" * (MAX_CHUNK_SIZE - len(self.content))
        )


class TransferFile:
    def __init__(self, id, filename: str | pathlib.Path):
        self.id = id
        if isinstance(filename, str):
            file = pathlib.Path(filename)
        else:
            file = filename
        self.filename = file.name
        self.packages_sent: list[int] = []
        self._chunks: list[Chunk] = []
        if self.filename.endswith(".delete"):
            self.filename = self.filename[:-7]
            self._chunks = [FileDelete(self.id, self.filename)]
            return

        with open(file, "rb") as f:
            self.content = f.read()
        self.size = len(self.content)
        self.make_chunks()
        _logger.debug("File %s has %s chunks", self.filename, len(self._chunks))

    def make_chunks(self):
        total_packages = self.size // MAX_CHUNK_SIZE
        self._chunks.append(
            FileStart(self.id, 0, total_packages, self.filename, self.size),
        )
        for i in range(0, self.size, MAX_CHUNK_SIZE):
            self._chunks.append(
                FileChunk(
                    self.id,
                    i // MAX_CHUNK_SIZE,
                    total_packages,
                    self.content[i : i + MAX_CHUNK_SIZE],
                ),
            )
        self._chunks.append(FileEnd(self.id))

    def get_next_chunk(self) -> Chunk:
        next = max(self.packages_sent) + 1 if len(self.packages_sent) > 0 else 0
        self.packages_sent.append(next)
        return self._chunks[next]

    def ack_chunk(self, chunk: DeviceFileChunk):
        if chunk.id != self.id:
            return
        _logger.info("Acked chunk %s", chunk.segment)

    @property
    def chunks(self):
        return len(self._chunks)

    def get_chunk(self, request: DeviceFileChunk) -> Chunk:
        if (
            request.segment < 0
            or request.segment >= len(self._chunks)
            or not request.is_request
        ):
            raise ValueError("Invalid request")
        return self._chunks[request.segment + 1]

    def is_complete(self):
        return len(self.packages_sent) == len(self._chunks)


def perform_hid_upgrade(device: hid.device, files: Sequence[str | pathlib.Path]):
    _logger.debug("Opening device for update")
    _logger.debug("Sending prepare update")
    device.write([1, 0xE0] + [0] * 7)
    time.sleep(STATE_CHANGE_SLEEP_TIME)

    transfer_files = [TransferFile(i, file) for i, file in enumerate(files)]

    chunk_requests = []
    finished = False
    finished_at: float = float("inf")

    _logger.debug("Preparing to send %s files", len(transfer_files))
    file_progress_bars = {
        file.id: tqdm(
            total=file.chunks,
            desc=f"{file.id}/{len(transfer_files)} {file.filename}",
        )
        for file in transfer_files
    }

    while True:
        received = device.read(24, 100)
        if len(received) > 0:
            rc = DeviceFileChunk(bytes(received))
            if rc.is_valid() and rc.is_request:
                chunk_requests.append(rc)
            if rc.is_ack:
                file = next((f for f in transfer_files if f.id == rc.id), None)
                if not file:
                    print("File not found")
                    _logger.warning("File not found")
                    raise FileNotFoundError("File not found")
                file_progress_bars[file.id].update(1)

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
            _logger.debug("Sending chunk of file %s", file.filename)
            cnk = bytes((2,)) + chunk.packet()
            device.write(cnk)
            time.sleep(DATA_TRANSFER_SLEEP_TIME)
        except StopIteration:
            if (
                finished
                and (time.monotonic() - finished_at) > WAIT_FOR_REQUESTS_SLEEP_TIME
            ):
                break
            time.sleep(WAIT_FOR_REQUESTS_SLEEP_TIME / 5)
            if not finished:
                print("All files transfered, waiting a bit for file requests")
                finished = True
                finished_at = time.monotonic()
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    device.write([2, 4] + [0] * 59)
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    print("Resetting")
    device.write([1, 0xE1] + [0] * 7)


# region: Update Application
def check_for_self_update(major: int, minor: int, patch: int):
    current_version = f"{major}.{minor}.{patch}"
    try:
        result = requests.get(
            "https://api.github.com/repos/mutenix-org/software-host/releases/latest",
        )
        if result.status_code != 200:
            _logger.error(
                "Failed to fetch latest release info, status code: %s",
                result.status_code,
            )
            return

        releases = result.json()
        latest_version = releases.get("tag_name", "v0.0.0")[1:]
        _logger.debug("Latest version: %s", latest_version)
        if semver.compare(current_version, latest_version) >= 0:
            _logger.info("Host Software is up to date")
            return

        _logger.info("Application update available, but auto update is disabled")
        webbrowser.open(releases.get("html_url"))
    except requests.RequestException as e:
        _logger.error("Failed to check for application update availability: %s", e)


# endregion
