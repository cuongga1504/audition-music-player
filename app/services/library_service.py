from __future__ import annotations
from pathlib import Path
from threading import Event
from PySide6.QtCore import QObject, Signal, QThreadPool, QUrl
from app.models.playlist_model import PlaylistModel, TrackFilter
from app.models.track import Track
from app.services.database_service import DatabaseService
from app.workers.scanner_worker import ScannerWorker
from player import SongCatalog


class LibraryService(QObject):
    changed = Signal()
    status = Signal(str)

    def __init__(self, database: DatabaseService) -> None:
        super().__init__()
        self.database = database
        self.model = PlaylistModel(database.load())
        self.proxy = TrackFilter(self.model)
        self.catalog = SongCatalog.load()
        self.roots: list[str] = []
        self.generation = 0
        self.cancel = Event()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.workers: dict[int, ScannerWorker] = {}

    def scan(self, paths: list[str]) -> None:
        self.cancel.set()
        self.pool.clear()
        self.workers.clear()
        self.cancel = Event()
        self.generation += 1
        self.roots = list(dict.fromkeys(self.roots + paths))
        worker = ScannerWorker(self.generation, self.roots, self.cancel)
        worker.signals.completed.connect(self._scanned)
        self.workers[self.generation] = worker
        self.status.emit('Đang quét thư viện…')
        self.pool.start(worker)

    def _scanned(self, generation: int, paths: list[str], error: str) -> None:
        self.workers.pop(generation, None)
        if generation != self.generation:
            return
        tracks = []
        for path in paths:
            if self.model.find(path) is None:
                title, artist = self.catalog.details(Path(path))
                tracks.append(Track(path, title, artist))
        self.database.add(tracks)
        self.model.append(tracks)
        self.changed.emit()
        self.status.emit(error or f'Đã thêm {len(tracks)} bài • {self.model.rowCount()} bài trong thư viện')

    def favorite(self, path: str) -> None:
        t = self.model.find(path)
        if t:
            t.favorite = not t.favorite
            self.database.update(t)
            self.model.changed(path)
            self.changed.emit()

    def duration(self, path: str, seconds: float) -> None:
        t = self.model.find(path)
        if t:
            t.duration = seconds
            self.database.update(t)
            self.model.changed(path)

    def remove(self, path: str) -> None:
        self.database.remove(path)
        self.model.remove(path)
        self.changed.emit()

    def visible_paths(self) -> list[str]:
        return [self.proxy.data(self.proxy.index(i, 0), 257) for i in range(self.proxy.rowCount())]

    def close(self) -> None:
        self.cancel.set()
        self.pool.clear()
        self.pool.waitForDone()
