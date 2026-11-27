from PySide6.QtCore import QObject, Property, Signal, Slot
from app.services.player_service import PlayerService


class PlayerViewModel(QObject):
    changed = Signal()
    spectrumChanged = Signal()

    def __init__(self, service: PlayerService) -> None:
        super().__init__()
        self.service = service
        self.levels = [0.0] * 24
        service.changed.connect(self.changed.emit)
        service.spectrumChanged.connect(self._levels)

    def _levels(self, levels: list) -> None:
        self.levels = levels
        self.spectrumChanged.emit()

    title = Property(str, lambda self: self.service.title, notify=changed)
    position = Property(int, lambda self: self.service.position, notify=changed)
    duration = Property(int, lambda self: self.service.duration, notify=changed)
    playing = Property(bool, lambda self: self.service.playing, notify=changed)
    busy = Property(bool, lambda self: self.service.busy, notify=changed)
    hasTrack = Property(bool, lambda self: bool(self.service.path), notify=changed)
    volume = Property(float, lambda self: self.service.volume, notify=changed)
    muted = Property(bool, lambda self: self.service.muted, notify=changed)
    shuffle = Property(bool, lambda self: self.service.shuffle, notify=changed)
    repeat = Property(int, lambda self: self.service.repeat, notify=changed)
    spectrum = Property('QVariantList', lambda self: self.levels, notify=spectrumChanged)

    @Slot()
    def toggle(self) -> None:
        self.service.toggle()

    @Slot()
    def stop(self) -> None:
        self.service.stop()

    @Slot()
    def next(self) -> None:
        self.service.next()

    @Slot()
    def previous(self) -> None:
        self.service.previous()

    @Slot(int)
    def seek(self, position: int) -> None:
        if self.service.loaded:
            self.service.engine.seek(position)

    @Slot(float)
    def setVolume(self, volume: float) -> None:
        self.service.volume = max(0.0, min(1.0, volume))
        self.service.engine.set_volume(self.service.volume)
        self.changed.emit()

    @Slot()
    def toggleMute(self) -> None:
        self.service.muted = not self.service.muted
        self.service.engine.set_muted(self.service.muted)
        self.changed.emit()

    @Slot()
    def toggleShuffle(self) -> None:
        self.service.set_shuffle(not self.service.shuffle)

    @Slot()
    def cycleRepeat(self) -> None:
        self.service.repeat = (self.service.repeat + 1) % 3
        self.changed.emit()

    @Slot(bool)
    def setFrontVisible(self, visible: bool) -> None:
        self.service.front_visible = visible
        self.service.analyzer.active = visible and self.service.playing
        if not visible:
            self.service.analyzer.reset()
