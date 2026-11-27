from __future__ import annotations
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from PySide6.QtCore import QObject, Signal, QByteArray, QBuffer, QIODevice, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioBufferOutput


class AudioEngine(QObject):
    """Replaceable transport contract. QML never accesses a backend directly."""
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    playingChanged = Signal(bool)
    ended = Signal()
    error = Signal(str)
    pcm = Signal(object)

    def load(self, data: bytes, position: int = 0, autoplay: bool = True) -> None:
        raise NotImplementedError

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def seek(self, position: int) -> None:
        raise NotImplementedError

    def set_volume(self, volume: float) -> None:
        raise NotImplementedError

    def set_muted(self, muted: bool) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class QtAudioEngine(AudioEngine):
    def __init__(self) -> None:
        super().__init__()
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.player.setAudioOutput(self.output)
        self.tap = QAudioBufferOutput(self)
        self.player.setAudioBufferOutput(self.tap)
        self.tap.audioBufferReceived.connect(self.pcm.emit)
        self.player.positionChanged.connect(self.positionChanged.emit)
        self.player.durationChanged.connect(self.durationChanged.emit)
        self.player.playbackStateChanged.connect(lambda state: self.playingChanged.emit(state == QMediaPlayer.PlayingState))
        self.player.mediaStatusChanged.connect(self._status)
        self.player.errorOccurred.connect(self._error)
        self.buffer: QBuffer | None = None
        self.data = b''
        self.temp: TemporaryDirectory | None = None
        self.pending_position = 0
        self.autoplay = True
        self.fallback = False

    def _release(self) -> None:
        self.data = b''
        self.player.stop()
        self.player.setSource(QUrl())
        if self.buffer:
            self.buffer.close()
            self.buffer.deleteLater()
            self.buffer = None
        if self.temp:
            self.temp.cleanup()
            self.temp = None
        self.data = b''

    def load(self, data: bytes, position: int = 0, autoplay: bool = True) -> None:
        self._release()
        self.data = data
        self.pending_position, self.autoplay = position, autoplay
        self.fallback = False
        self.buffer = QBuffer(self)
        self.buffer.setData(QByteArray(data))
        self.buffer.open(QIODevice.ReadOnly)
        self.player.setSourceDevice(self.buffer, QUrl('memory.ogg'))

    def _status(self, status: QMediaPlayer.MediaStatus) -> None:
        if not self.data:
            return
        if status == QMediaPlayer.LoadedMedia:
            self.player.setPosition(self.pending_position)
            if self.autoplay:
                self.player.play()
        elif status == QMediaPlayer.EndOfMedia:
            self.ended.emit()

    def _error(self, code, message: str) -> None:
        if not self.data:
            return
        if not self.fallback:
            logging.warning('Memory playback failed; retrying local OGG: %s', message)
            self.fallback = True
            try:
                self.temp = TemporaryDirectory(prefix='tbm-cassette-')
                path = Path(self.temp.name, 'audio.ogg')
                path.write_bytes(self.data)
                self.player.setSource(QUrl.fromLocalFile(str(path)))
            except Exception as error:
                self.error.emit(f'Không phát được OGG: {message}; {error}')
        else:
            self.error.emit(f'Không phát được OGG: {message}')

    def play(self) -> None:
        self.autoplay = True
        self.player.play()

    def pause(self) -> None:
        self.autoplay = False
        self.player.pause()

    def stop(self) -> None:
        self.autoplay = False
        self.pending_position = 0
        self.player.stop()

    def seek(self, position: int) -> None:
        self.pending_position = position
        self.player.setPosition(position)

    def set_volume(self, volume: float) -> None:
        self.output.setVolume(volume)

    def set_muted(self, muted: bool) -> None:
        self.output.setMuted(muted)

    def close(self) -> None:
        self._release()
