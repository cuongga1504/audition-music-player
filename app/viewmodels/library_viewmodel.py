from __future__ import annotations
from pathlib import Path
import os
import subprocess
from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog
from app.models.playlist_model import normalized
from app.services.library_service import LibraryService
from app.services.player_service import PlayerService


class LibraryViewModel(QObject):
    changed = Signal()
    statusChanged = Signal()

    def __init__(self, library: LibraryService, player: PlayerService) -> None:
        super().__init__()
        self.library, self.player = library, player
        self.message = 'Offline. Your music stays on this device.'
        library.changed.connect(self.changed.emit)
        library.proxy.rowsInserted.connect(lambda *args: self.changed.emit())
        library.proxy.rowsRemoved.connect(lambda *args: self.changed.emit())
        library.proxy.modelReset.connect(lambda *args: self.changed.emit())
        library.status.connect(self.set_status)
        player.status.connect(self.set_status)

    def set_status(self, message: str) -> None:
        self.message = message
        self.statusChanged.emit()

    count = Property(int, lambda self: self.library.model.rowCount(), notify=changed)
    visibleCount = Property(int, lambda self: self.library.proxy.rowCount(), notify=changed)
    favoritesOnly = Property(bool, lambda self: self.library.proxy.favorites, notify=changed)
    status = Property(str, lambda self: self.message, notify=statusChanged)

    @Slot()
    def openFiles(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(None, 'Open TBM audio', '', 'Game music (*.tbm *.abm)')
        if paths:
            self.library.scan(paths)

    @Slot()
    def openFolder(self) -> None:
        path = QFileDialog.getExistingDirectory(None, 'Open music folder')
        if path:
            self.library.scan([path])

    @Slot('QVariantList')
    def dropFiles(self, urls: list) -> None:
        paths = [QUrl(url).toLocalFile() for url in urls if QUrl(url).isLocalFile()]
        if paths:
            self.library.scan(paths)

    @Slot()
    def refresh(self) -> None:
        roots = self.library.roots or [t.path for t in self.library.model.tracks]
        if roots:
            self.library.scan(roots)

    @Slot(str)
    def search(self, query: str) -> None:
        self.library.proxy.query = normalized(query.strip())
        self.library.proxy.refresh_filter()
        self.changed.emit()

    @Slot()
    def toggleFavorites(self) -> None:
        self.library.proxy.favorites = not self.library.proxy.favorites
        self.library.proxy.refresh_filter()
        self.changed.emit()

    @Slot(int)
    def sort(self, mode: int) -> None:
        self.library.proxy.sort_mode = mode
        self.library.proxy.sort(0, Qt.DescendingOrder if mode == 1 else Qt.AscendingOrder)
        self.changed.emit()

    @Slot(str)
    def play(self, path: str) -> None:
        self.player.select(path)

    @Slot(str)
    def favorite(self, path: str) -> None:
        self.library.favorite(path)

    @Slot(str)
    def playNext(self, path: str) -> None:
        self.player.queue.append(path)
        self.set_status('Đã thêm vào hàng đợi phát tiếp.')

    @Slot(str)
    def remove(self, path: str) -> None:
        if self.player.path == path:
            self.player.stop()
            self.player.engine.close()
            self.player.path = ''
            self.player.loaded = False
            self.player.duration = 0
            self.player.changed.emit()
        self.library.remove(path)

    @Slot(str)
    def reveal(self, path: str) -> None:
        if os.name == 'nt':
            subprocess.Popen(['explorer.exe', '/select,', str(Path(path))])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    @Slot(str)
    def export(self, path: str) -> None:
        if self.player.busy:
            self.set_status('Chờ giải mã hoàn tất trước khi xuất.')
            return
        destination, _ = QFileDialog.getSaveFileName(None, 'Export original decoded OGG (new file)', str(Path(path).with_suffix('.ogg')), 'OGG Vorbis (*.ogg)')
        if destination:
            if not destination.lower().endswith('.ogg'):
                destination += '.ogg'
            if Path(destination).exists():
                self.set_status('Tệp đã tồn tại. Chọn tên mới để tránh ghi đè.')
                return
            self.player.select(path, export=destination)
