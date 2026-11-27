from __future__ import annotations
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QSortFilterProxyModel
from app.models.track import Track
from pathlib import Path
import unicodedata


def normalized(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value.casefold().replace('đ', 'd')) if not unicodedata.combining(c))


class PlaylistModel(QAbstractListModel):
    roles = {Qt.UserRole + i: name.encode() for i, name in enumerate(('filePath', 'title', 'artist', 'duration', 'favorite', 'current'), 1)}

    def __init__(self, tracks: list[Track]) -> None:
        super().__init__()
        self.tracks = tracks
        self.current_path = ''
        self.lookup = {t.path.casefold(): i for i, t in enumerate(tracks)}

    def roleNames(self) -> dict:
        return self.roles

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.tracks)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.tracks):
            return None
        t = self.tracks[index.row()]
        values = (t.path, t.title, t.artist, t.duration, t.favorite, t.path == self.current_path)
        return values[role - Qt.UserRole - 1] if role in self.roles else None

    def append(self, tracks: list[Track]) -> None:
        added = [t for t in tracks if t.path.casefold() not in self.lookup]
        if added:
            start = len(self.tracks)
            self.beginInsertRows(QModelIndex(), start, start + len(added) - 1)
            self.tracks.extend(added)
            self.lookup.update({t.path.casefold(): i for i, t in enumerate(self.tracks[start:], start)})
            self.endInsertRows()

    def _row(self, path: str) -> int | None:
        """Resolve aliases only on a lookup miss; normal QML paths stay cheap."""
        row = self.lookup.get(path.casefold())
        if row is None and path:
            try:
                row = self.lookup.get(str(Path(path).resolve()).casefold())
            except (OSError, RuntimeError):
                return None
        return row

    def find(self, path: str) -> Track | None:
        row = self._row(path)
        return self.tracks[row] if row is not None else None

    def changed(self, path: str) -> None:
        row = self._row(path)
        if row is not None:
            self.dataChanged.emit(self.index(row), self.index(row), list(self.roles))

    def set_current(self, path: str) -> None:
        track = self.find(path)
        old, self.current_path = self.current_path, track.path if track else path
        self.changed(old)
        self.changed(path)

    def remove(self, path: str) -> None:
        row = self._row(path)
        if row is None:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self.tracks[row]
        self.lookup = {t.path.casefold(): i for i, t in enumerate(self.tracks)}
        self.endRemoveRows()


class TrackFilter(QSortFilterProxyModel):
    def __init__(self, model: PlaylistModel) -> None:
        super().__init__()
        self.query = ''
        self.favorites = False
        self.sort_mode = 0
        self.setSourceModel(model)
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        t = self.sourceModel().tracks[row]
        return (not self.favorites or t.favorite) and self.query in normalized(f'{t.title} {t.artist} {t.path}')

    def refresh_filter(self) -> None:
        if hasattr(self, 'beginFilterChange') and hasattr(self, 'endFilterChange'):
            self.beginFilterChange()
            self.endFilterChange()
        else:
            self.invalidateFilter()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        a, b = self.sourceModel().tracks[left.row()], self.sourceModel().tracks[right.row()]
        if self.sort_mode == 2:
            return a.duration < b.duration
        return normalized(a.title) < normalized(b.title)
