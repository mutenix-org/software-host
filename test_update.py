import hid
import time
from tqdm import tqdm
import pathlib


HEADER_SIZE = 8
MAX_CHUNK_SIZE = 60 - HEADER_SIZE


class RequestChunk:
    def __init__(self, data: bytes):
        self.parse(data)
        self.id = ""
        self.segment = 0

    def parse(self, data: bytes):
        self.identifier = data[:2].decode("utf-8")
        if self.identifier != "RQ":
            return
        self.id = int.from_bytes(data[2:4], "little")
        self.package = int.from_bytes(data[4:6], "little")

    def is_valid(self):
        return self.identifier == "RQ"

    def __str__(self):
        if self.is_valid():
            return f"File: {self.id}, Package: {self.package}"
        return "Invalid Request"


class FileChunk:
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


class FileStart:
    def __init__(
        self, id: int, package: int, total_packages: int, filename: bytes, filesize: int
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

class FileEnd:
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
        self.filename = pathlib.Path(filename).name
        self.content = open(filename, "rb").read()
        self.size = len(self.content)
        self.packages_sent = []
        self._chunks = []
        self.make_chunks()

    def make_chunks(self):
        total_packages = self.size // MAX_CHUNK_SIZE
        self._chunks.append(FileStart(self.id, 0, total_packages, self.filename, self.size))
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

    def get_next_chunk(self):
        next = max(self.packages_sent) + 1 if len(self.packages_sent) > 0 else 0
        self.packages_sent.append(next)
        return self._chunks[next]
    
    @property
    def chunks(self):
        return len(self._chunks)

    def get_chunk(self, request: RequestChunk):
        if request.id != self.id:
            raise FileNotFoundError("File not found")
        if request.segment < 0 or request.segment >= len(self._chunks):  
            raise ValueError("Invalid request")
        return self._chunks[request.segment+1]

    def is_complete(self):
        return len(self.packages_sent) == len(self._chunks)


def main():
    _device = hid.device()
    _device.open(0x2E8A, 0x2083)
    _device.write([1, 0xE0] + [0] * 7)
    time.sleep(0.5)

    transfer_files = [
        TransferFile(1, "../firmware-macro-board/code.py"),
    ]

    chunk_requests = []
    finished = False
    finished_at = None
    
    file_progress_bars = {file.id: tqdm(total=file.chunks, desc=f"{file.id}/{len(transfer_files)} {file.filename}") for file in transfer_files}

    while True:
        received = _device.read(24, 100)
        if len(received) > 0:
            rc = RequestChunk(bytes(received))
            if rc.is_valid():
                print(rc)
                try:
                    chunk_requests.append(rc)
                except FileNotFoundError:
                    print("File not found")

        if len(chunk_requests) > 0:
            cr = chunk_requests.pop(0)
            file = transfer_files.get(cr.filename)
            chunk = file.get_chunk(cr)
            _device.write(bytearray((2,)) + chunk.packet())
            time.sleep(0.02)

        try:
            file = next(filter(lambda x: not x.is_complete(), transfer_files))
            chunk = file.get_next_chunk()
            if chunk:
                cnk = bytes((2,)) + chunk.packet()
                _device.write(cnk)
                file_progress_bars[file.id].update(1)
                time.sleep(0.02)
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
    time.sleep(0.5)
    _device.write([2, 4] + [0] * 59)
    time.sleep(0.5)
    print("Resetting")
    _device.write([1, 0xE1] + [0] * 7)


if __name__ == "__main__":
    main()
