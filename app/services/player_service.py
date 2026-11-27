from __future__ import annotations
from collections import deque
import json
import logging
from pathlib import Path
import random
import sys
from PySide6.QtCore import QObject, Signal, QProcess
from app.core.audio_cache import AudioCache
from app.core.audio_engine import AudioEngine
from app.core.audio_analyzer import AudioAnalyzer
from app.services.library_service import LibraryService
from app.services.settings_service import SettingsService


class PlayerService(QObject):
    changed = Signal()
    spectrumChanged = Signal(list)
    status = Signal(str)

    def __init__(self, engine: AudioEngine, library: LibraryService, settings: SettingsService) -> None:
        super().__init__()
        self.engine, self.library, self.settings = engine, library, settings
        self.cache = AudioCache()
        self.path = str(settings.get('track', ''))
        if not library.model.find(self.path):
            self.path = ''
        self.position = int(settings.get('position', 0)) if self.path else 0
        self.duration = int((library.model.find(self.path).duration if self.path else 0) * 1000)
        self.volume = float(settings.get('volume', 0.7))
        self.muted = False
        self.playing = self.busy = self.loaded = False
        self.shuffle = settings.get('shuffle', 'false') in (True, 'true')
        self.repeat = int(settings.get('repeat', 0))
        self.front_visible = True
        self.queue: deque[str] = deque()
        self.history: list[str] = []
        self.shuffle_remaining: list[str] = []
        self.shuffle_seen: set[str] = set()
        self.process: QProcess | None = None
        self.retired: list[QProcess] = []
        self.export_path = ''
        self.analyzer = AudioAnalyzer()
        self.analyzer.levels.connect(self.spectrumChanged.emit)
        engine.pcm.connect(self.analyzer.consume)
        engine.positionChanged.connect(self._position)
        engine.durationChanged.connect(self._duration)
        engine.playingChanged.connect(self._playing)
        engine.ended.connect(lambda: self.next(natural=True))
        engine.error.connect(self._error)
        engine.set_volume(self.volume)
        library.model.set_current(self.path)

    @property
    def title(self) -> str:
        track = self.library.model.find(self.path)
        return track.title if track else 'Your next favorite soundtrack'

    def _position(self, value: int) -> None:
        self.position = value
        self.changed.emit()

    def _duration(self, value: int) -> None:
        if value > 0:
            self.duration = value
            self.library.duration(self.path, value / 1000)
            self.changed.emit()

    def _playing(self, value: bool) -> None:
        self.playing = value
        self.analyzer.active = value and self.front_visible
        if not value:
            self.analyzer.reset()
        self.changed.emit()

    def _error(self, message: str) -> None:
        self.busy = False
        logging.error(message)
        self.status.emit(message)
        self.changed.emit()

    def cancel(self) -> None:
        if self.process:
            process, self.process = self.process, None
            self.retired.append(process)
            process.finished.connect(lambda *args: self.retired.remove(process) if process in self.retired else None)
            process.kill()
        self.busy = False

    def select(self, path: str, position: int = 0, export: str = '', record_history: bool = True) -> None:
        self.cancel()
        if not export:
            if record_history and self.path and self.path != path:
                self.history.append(self.path)
                self.history = self.history[-256:]
            self.shuffle_seen.add(path)
            self.engine.close()
            self.loaded = False
            self.path, self.position = path, position
            track = self.library.model.find(path)
            self.duration = int(track.duration * 1000) if track else 0
            self.library.model.set_current(path)
        self.busy = True
        self.status.emit('Đang giải mã TBM…' if not export else 'Đang chuẩn bị xuất OGG…')
        self.changed.emit()
        proc = QProcess(self)
        self.process = proc
        self.export_path = export
        cached = next((key for key in reversed(self.cache.entries) if key[0].casefold() == str(Path(path).resolve()).casefold()), None)
        args = ['--decode-worker', path, cached[1] if cached and not export else '', export]
        if not getattr(sys, 'frozen', False):
            args.insert(0, str(Path(__file__).resolve().parents[2] / 'main.py'))
        proc.finished.connect(lambda code, status: self._decoded(proc, path, position, export, code))
        proc.finished.connect(proc.deleteLater)
        proc.errorOccurred.connect(lambda error: self._process_error(proc, error))
        proc.start(sys.executable, args)

    def _process_error(self, proc: QProcess, error) -> None:
        if proc is self.process and error == QProcess.FailedToStart:
            self.process = None
            proc.deleteLater()
            self._error('Không khởi động được decoder worker: ' + proc.errorString())

    def _decoded(self, proc: QProcess, path: str, position: int, export: str, code: int) -> None:
        if proc is not self.process:
            return
        self.process = None
        self.busy = False
        try:
            if code:
                raise ValueError(bytes(proc.readAllStandardError()).decode('utf-8', errors='replace').strip() or 'Decoder worker thất bại.')
            header, data = bytes(proc.readAllStandardOutput()).split(b'\n', 1)
            info = json.loads(header)
            key = tuple(info['key'])
            if info.get('cached'):
                entry = self.cache.get(key)
                if entry is None:
                    raise ValueError('Cache đã thay đổi; hãy phát lại.')
                data, metadata = entry
            else:
                metadata = info['metadata']
                if not export:
                    self.cache.put(key, data, metadata)
            self.library.duration(path, metadata['seconds'])
            if export:
                if not info.get('exported'):
                    raise ValueError('Worker chưa hoàn tất xuất âm thanh.')
                self.status.emit('Đã xuất OGG: ' + export)
            else:
                self.duration = int(metadata['seconds'] * 1000)
                self.loaded = True
                self.engine.load(data, min(position, max(0, self.duration - 1)))
                self.status.emit('OGG Vorbis • ' + str(metadata['sample_rate']) + ' Hz • ' + str(metadata['channels']) + ' ch')
        except Exception as error:
            self._error(str(error))
        finally:
            proc.deleteLater()
            self.changed.emit()

    def toggle(self) -> None:
        if self.busy:
            return
        if self.playing:
            self.engine.pause()
        elif self.loaded:
            self.engine.play()
        else:
            paths = self.library.visible_paths()
            path = self.path or ((random.choice(paths) if self.shuffle else paths[0]) if paths else '')
            if path:
                self.select(path, self.position if path == self.path else 0)
            else:
                self.status.emit('Mở tệp hoặc thư mục TBM để bắt đầu.')

    def set_shuffle(self, enabled: bool) -> None:
        self.shuffle = enabled
        self.shuffle_remaining.clear()
        self.shuffle_seen = {self.path} if self.path else set()
        self.settings.set('shuffle', enabled)
        self.status.emit('Đã bật phát ngẫu nhiên • không lặp bài trong cùng lượt.' if enabled else 'Đã tắt phát ngẫu nhiên.')
        self.changed.emit()

    def stop(self) -> None:
        self.cancel()
        self.engine.stop()
        self.position = 0
        self.changed.emit()

    def next(self, natural: bool = False) -> None:
        paths = self.library.visible_paths()
        if natural and self.repeat == 1 and self.path:
            self.select(self.path)
            return
        while self.queue:
            queued = self.queue.popleft()
            if self.library.model.find(queued):
                self.select(queued)
                return
        if not paths:
            self.stop()
            return
        if self.shuffle:
            self.shuffle_remaining = [p for p in self.shuffle_remaining if p in paths and p not in self.shuffle_seen and p != self.path]
            if not self.shuffle_remaining:
                self.shuffle_remaining = [p for p in paths if p not in self.shuffle_seen and p != self.path]
                if not self.shuffle_remaining:
                    if natural and self.repeat != 2:
                        return
                    self.shuffle_seen = {self.path}
                    self.shuffle_remaining = [p for p in paths if p != self.path]
                random.shuffle(self.shuffle_remaining)
            if self.shuffle_remaining:
                self.select(self.shuffle_remaining.pop())
            elif self.repeat == 2 or not natural:
                self.select(paths[0])
            return
        index = paths.index(self.path) + 1 if self.path in paths else 0
        if index < len(paths):
            self.select(paths[index])
        elif not natural or self.repeat == 2:
            self.select(paths[0])

    def previous(self) -> None:
        if self.position > 3000 and self.loaded:
            self.engine.seek(0)
        elif self.history:
            path = self.history.pop()
            if self.library.model.find(path):
                self.select(path, record_history=False)
            else:
                self.previous()
        else:
            paths = self.library.visible_paths()
            if paths:
                i = paths.index(self.path) if self.path in paths else 0
                self.select(paths[(i - 1) % len(paths)])

    def close(self) -> None:
        for key, value in {'track': self.path, 'position': self.position, 'volume': self.volume, 'shuffle': self.shuffle, 'repeat': self.repeat}.items():
            self.settings.set(key, value)
        self.cancel()
        for process in list(self.retired):
            process.waitForFinished(3000)
        self.engine.close()
        self.cache.entries.clear()
        self.cache.size = 0
