from enum import IntEnum

from mutenix.updates.constants import MAX_CHUNK_SIZE


class ChunkType(IntEnum):
    FILE_START = 1
    FILE_CHUNK = 2
    FILE_END = 3
    COMPLETE = 4
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
