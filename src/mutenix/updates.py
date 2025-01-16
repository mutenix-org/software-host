# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import io
import logging
import os
import pathlib
import tarfile
import tempfile
import time
import webbrowser
from collections.abc import Sequence
from enum import IntEnum
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
            timeout=4,
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
        online_version = semver.Version.parse(latest_version)
        local_version = semver.Version.parse(device_version.version)
        if online_version.compare(local_version) <= 0:
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
DATA_TRANSFER_SLEEP_TIME = 1
STATE_CHANGE_SLEEP_TIME = 0.5
WAIT_FOR_REQUESTS_SLEEP_TIME = STATE_CHANGE_SLEEP_TIME
HID_REPORT_ID_COMMUNICATION = 1
HID_REPORT_ID_TRANSFER = 2

HID_COMMAND_PREPARE_UPDATE = 0xE0
HID_COMMAND_RESET = 0xE1


def perform_upgrade_with_file(device: hid.device, file_stream: BinaryIO):
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = pathlib.Path(tmpdirname)
        with tarfile.open(fileobj=file_stream, mode="r:gz") as tar:
            tar.extractall(path=tmpdirname)
        files = list(
            map(
                lambda x: tmpdir / x,
                filter(
                    lambda x: (x.endswith(".py") or x.endswith(".delete"))
                    and not x.startswith("."),
                    os.listdir(tmpdirname),
                ),
            ),
        )
        _logger.debug("Updateing device with files: %s", files)
        perform_hid_upgrade(device, files)
        _logger.info("Successfully updated device firmware")


class ChunkAck:
    def __init__(self, data: bytes):
        self.id = 0
        self.package = 0
        self.type_ = 0
        self.parse(data)

    def parse(self, data: bytes):
        self.identifier = data[:2].decode("utf-8")
        if not self.is_valid:
            return
        self.id = int.from_bytes(data[2:4], "little")
        self.package = int.from_bytes(data[4:6], "little")
        self.type_ = int.from_bytes(data[6:7], "little")
        _logger.info("Ack: %s", self)

    @property
    def is_valid(self):
        return self.identifier == "AK"

    def __str__(self):
        if self.is_valid:
            return f"File: {self.id}, Type: {self.type_}, Package: {self.package}"
        return "Invalid Request"


class ChunkType(IntEnum):
    FILE_START = 1
    FILE_CHUNK = 2
    FILE_END = 3
    COMPLETE = 3
    FILE_DELETE = 5


class Chunk:
    def __init__(self, type_: int, id: int, package: int = 0, total_packages: int = 0):
        self.type_ = type_
        self.id = id
        self.package = package
        self.total_packages = total_packages
        self._acked = False
        self.content = b""

    def packet(self):  # pragma: no cover
        return (
            self._base_packet()
            + self.content
            + b"\0" * (MAX_CHUNK_SIZE - len(self.content))
        )

    def _base_packet(self):
        return (
            int(self.type_).to_bytes(2, "little")
            + self.id.to_bytes(2, "little")
            + self.total_packages.to_bytes(2, "little")
            + self.package.to_bytes(2, "little")
        )

    @property
    def acked(self):
        return self._acked


class FileChunk(Chunk):
    def __init__(self, id: int, package: int, total_packages: int, content: bytes):
        super().__init__(ChunkType.FILE_CHUNK, id, package, total_packages)
        self.content = content


class FileStart(Chunk):
    def __init__(
        self,
        id: int,
        package: int,
        total_packages: int,
        filename: str,
        filesize: int,
    ):
        super().__init__(ChunkType.FILE_START, id, package, total_packages)
        self.content = (
            bytes((len(filename),))
            + filename.encode("utf-8")
            + bytes((2,))
            + filesize.to_bytes(2, "little")
        )


class FileEnd(Chunk):
    def __init__(self, id: int):
        super().__init__(ChunkType.FILE_END, id)


class FileDelete(Chunk):
    def __init__(
        self,
        id: int,
        filename: str,
    ):
        super().__init__(ChunkType.FILE_DELETE, id)
        self.content = bytes((len(filename),)) + filename.encode("utf-8")


class Completed(Chunk):
    def __init__(self):
        super().__init__(ChunkType.COMPLETE, 0)


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

    def get_next_chunk(self) -> Chunk | None:
        if self.is_complete():
            return None
        return next((chunk for chunk in self._chunks if not chunk.acked))

    def ack_chunk(self, chunk: ChunkAck):
        if chunk.id != self.id:
            return

        acked_chunk = next(
            filter(
                lambda x: x.type_ == chunk.type_ and x.package == chunk.package,
                self._chunks,
            ),
            None,
        )
        if acked_chunk:
            acked_chunk._acked = True
            _logger.info("Acked chunk %s", chunk.package)
        else:
            _logger.warning("Chunk not found %s: %s", chunk.type_, chunk.package)

    @property
    def chunks(self):
        return len(self._chunks)

    def is_complete(self):
        return all(map(lambda x: x.acked, self._chunks))


def send_hid_command(device: hid.device, command: int):
    device.write([HID_REPORT_ID_COMMUNICATION, command] + [0] * 7)


def perform_hid_upgrade(device: hid.device, files: Sequence[str | pathlib.Path]):
    _logger.debug("Opening device for update")
    _logger.debug("Sending prepare update")
    send_hid_command(device, HID_COMMAND_PREPARE_UPDATE)
    time.sleep(STATE_CHANGE_SLEEP_TIME)

    transfer_files = [TransferFile(i, file) for i, file in enumerate(files)]

    _logger.debug("Preparing to send %s files", len(transfer_files))
    file_progress_bars = {
        file.id: tqdm(
            total=file.chunks,
            desc=f"{file.id}/{len(transfer_files)} {file.filename}",
        )
        for file in transfer_files
    }

    while True:
        received = device.read(100, 1000)
        if len(received) > 0:
            rc = ChunkAck(bytes(received[1:]))
            if rc.is_valid:
                _logger.debug("Received Ack")
                file = next((f for f in transfer_files if f.id == rc.id), None)
                if not file:
                    _logger.warning("No file id found for ack")
                    continue
                file_progress_bars[file.id].update(1)
                file.ack_chunk(rc)

        try:
            file = next(filter(lambda x: not x.is_complete(), transfer_files))
            chunk = file.get_next_chunk()
            if not chunk:
                continue
            _logger.debug(
                "Sending chunk (%s...) of file %s",
                chunk.packet()[:10],
                file.filename,
            )
            cnk = bytes((HID_REPORT_ID_TRANSFER,)) + chunk.packet()
            device.write(cnk)
        except StopIteration:
            break
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    device.write(bytes((HID_REPORT_ID_TRANSFER,)) + Completed().packet())
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    print("Resetting")
    send_hid_command(device, HID_COMMAND_RESET)


# region: Update Application
def check_for_self_update(major: int, minor: int, patch: int):
    try:
        result = requests.get(
            "https://api.github.com/repos/mutenix-org/software-host/releases/latest",
            timeout=4,
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
        online_version = semver.Version.parse(latest_version)
        local_version = semver.Version(major=major, minor=minor, patch=patch)
        if online_version.compare(local_version) <= 0:
            _logger.info("Host Software is up to date")
            return

        _logger.info("Application update available, but auto update is disabled")
        webbrowser.open(releases.get("html_url"))
    except requests.RequestException as e:
        _logger.error("Failed to check for application update availability: %s", e)


# endregion
