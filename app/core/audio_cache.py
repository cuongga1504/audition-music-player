"""Byte-bounded LRU of validated decoded streams."""
from collections import OrderedDict
from pathlib import Path
import hashlib


def revision(path: str) -> tuple:
    source = Path(path)
    before = source.stat()
    with source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_size, after.st_mtime_ns, after.st_ctime_ns
    ):
        raise OSError('Tệp đang được cập nhật. Hãy thử lại.')
    return str(source.resolve()), digest


class AudioCache:
    def __init__(self, budget: int = 96 * 1024 * 1024) -> None:
        self.budget = budget
        self.entries: OrderedDict[tuple, tuple[bytes, dict]] = OrderedDict()
        self.size = 0

    def get(self, key: tuple) -> tuple[bytes, dict] | None:
        value = self.entries.get(key)
        if value:
            self.entries.move_to_end(key)
        return value

    def put(self, key: tuple, data: bytes, metadata: dict) -> None:
        for old in list(self.entries):
            if old[0] == key[0]:
                self.size -= len(self.entries.pop(old)[0])
        if len(data) > self.budget:
            return
        self.entries[key] = data, metadata
        self.size += len(data)
        while self.size > self.budget:
            self.size -= len(self.entries.popitem(last=False)[1][0])
