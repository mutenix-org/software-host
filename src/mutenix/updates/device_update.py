# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import json
import logging
import math
import os
import pathlib
import tarfile
import tempfile
import time
from collections.abc import Sequence
from typing import BinaryIO

import hid
import python_minifier
from mutenix.updates.chunks import Chunk
from mutenix.updates.chunks import Completed
from mutenix.updates.chunks import FileChunk
from mutenix.updates.chunks import FileDelete
from mutenix.updates.chunks import FileEnd
from mutenix.updates.chunks import FileStart
from mutenix.updates.constants import HID_COMMAND_PREPARE_UPDATE
from mutenix.updates.constants import HID_COMMAND_RESET
from mutenix.updates.constants import HID_REPORT_ID_COMMUNICATION
from mutenix.updates.constants import HID_REPORT_ID_TRANSFER
from mutenix.updates.constants import MAX_CHUNK_SIZE
from mutenix.updates.constants import STATE_CHANGE_SLEEP_TIME
from mutenix.updates.device_messages import ChunkAck
from mutenix.updates.device_messages import LogMessage
from mutenix.updates.device_messages import parse_hid_update_message
from mutenix.updates.device_messages import UpdateError
from tqdm import tqdm

_logger = logging.getLogger(__name__)


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
        _logger.debug("Updating device with files: %s", files)
        perform_hid_upgrade(device, files)
        _logger.info("Successfully updated device firmware")


class TransferFile:
    def __init__(self, file_id, filename: str | pathlib.Path):
        self.id = file_id
        file = pathlib.Path(filename) if isinstance(filename, str) else filename
        self.filename = file.name
        self.packages_sent: list[int] = []
        self._chunks: list[Chunk] = []
        if self.filename.endswith(".delete"):
            self.filename = self.filename[:-7]
            self._chunks = [FileDelete(self.id, self.filename)]
            return

        with open(file, "r") as f:
            if file.suffix == ".py":
                self.content = python_minifier.minify(
                    f.read(),
                    remove_annotations=True,
                    rename_globals=False,
                ).encode("utf-8")
            else:
                self.content = f.read().encode("utf-8")
        # Workaround for update issue
        self.size = len(self.content)
        self.content = self.content + b"\x20" * (
            MAX_CHUNK_SIZE - (len(self.content) % MAX_CHUNK_SIZE)
        )
        _logger.info("Size %s, %s", self.size, json.dumps(self.content.decode("utf-8")))
        self.make_chunks()
        _logger.debug("File %s has %s chunks", self.filename, len(self._chunks))

    def make_chunks(self):
        total_packages = self.calculate_total_packages()
        self.add_file_start_chunk(total_packages)
        self.add_file_chunks(total_packages)
        self.add_file_end_chunk()

    def calculate_total_packages(self):
        return math.ceil(self.size / MAX_CHUNK_SIZE)

    def add_file_start_chunk(self, total_packages):
        self._chunks.append(
            FileStart(self.id, 0, total_packages, self.filename, self.size),
        )

    def add_file_chunks(self, total_packages):
        for i in range(0, self.size, MAX_CHUNK_SIZE):
            self._chunks.append(
                FileChunk(
                    self.id,
                    i // MAX_CHUNK_SIZE,
                    total_packages,
                    self.content[i : i + MAX_CHUNK_SIZE],
                ),
            )

    def add_file_end_chunk(self):
        self._chunks.append(FileEnd(self.id))

    def get_next_chunk(self) -> Chunk | None:
        if self.is_complete():
            return None
        return next((chunk for chunk in self._chunks if not chunk.acked), None)

    def acknowledge_chunk(self, chunk: ChunkAck):
        # This line is excluded from coverage reports because it is a safeguard
        # and is unlikely to be met during normal execution.
        if chunk.id != self.id:  # pragma: no cover
            return
        acked_chunk = next(
            (
                x
                for x in self._chunks
                if x.type_ == chunk.type_ and x.package == chunk.package
            ),
            None,
        )
        if not acked_chunk:  # pragma: no cover
            _logger.warning("No chunk found for ack")
            return
        acked_chunk._acked = True
        _logger.debug("Acked chunk %s", chunk)

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

    transfer_files = [TransferFile(file_id, file) for file_id, file in enumerate(files)]

    _logger.debug("Preparing to send %s files", len(transfer_files))
    cancelled = False

    for i, file in enumerate(transfer_files, 1):
        if cancelled:
            break
        fileprogress = tqdm(
            total=file.chunks,
            desc=f"Sending file {file.filename:25} {i:2}/{len(transfer_files)}",
        )
        while True:
            received = device.read(100, 1000)
            if len(received) > 0:
                rcvd = parse_hid_update_message(bytes(received[1:]))

                if isinstance(rcvd, ChunkAck):
                    ack_file = next(
                        (f for f in transfer_files if f.id == rcvd.id),
                        None,
                    )
                    if not ack_file:
                        _logger.warning("No file id found for ack")
                        continue
                    fileprogress.update(1)
                    ack_file.acknowledge_chunk(rcvd)
                elif isinstance(rcvd, UpdateError):
                    print("Error received from device: ", rcvd)
                    _logger.error("Error received from device: %s", rcvd)
                    cancelled = True
                    break
                elif isinstance(rcvd, LogMessage):
                    print(rcvd)

            chunk = file.get_next_chunk()
            if not chunk:
                fileprogress.close()
                break
            _logger.debug(
                "Sending chunk (%s...) of file %s",
                chunk.packet()[:10],
                file.filename,
            )
            cnk = bytes((HID_REPORT_ID_TRANSFER,)) + chunk.packet()
            try:
                device.write(cnk)
            except Exception as e:
                _logger.error("Failed to write chunk to device: %s", e)
                cancelled = True
                break

    time.sleep(STATE_CHANGE_SLEEP_TIME)
    try:
        device.write(bytes((HID_REPORT_ID_TRANSFER,)) + Completed().packet())
    except Exception as e:
        _logger.error("Failed to write Completed packet to device: %s", e)
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    print("Resetting")
    _logger.info("Resetting")
    send_hid_command(device, HID_COMMAND_RESET)
