from __future__ import annotations
import json
import math
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QObject, QUrl, qInstallMessageHandler, Qt, QPoint
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import shiboken6
from app.core.audio_cache import AudioCache, revision
from app.core.audio_analyzer import AudioAnalyzer, spectrum
from app.core.audio_engine import AudioEngine, QtAudioEngine
from app.models.track import Track
from app.services.database_service import DatabaseService
from app.services.library_service import LibraryService
from app.services.player_service import PlayerService
from app.viewmodels.player_viewmodel import PlayerViewModel
from app.viewmodels.library_viewmodel import LibraryViewModel
from main import WindowViewModel

ROOT = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle('Basic')
APPLICATION = QApplication.instance() or QApplication([])
MESSAGES: list[str] = []
qInstallMessageHandler(lambda kind, context, message: MESSAGES.append(message))


def until(predicate, timeout=15000):
    start = time.monotonic()
    while time.monotonic() - start < timeout / 1000:
        APPLICATION.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
        # QTest.qWait may retain the Python GIL on Windows. Allow Python
        # scanner threads to run between nested Qt event loop iterations.
        time.sleep(0.002)
    return False


class MemorySettings:
    def __init__(self):
        self.values = {}
    def get(self, key, default=None):
        return self.values.get(key, default)
    def set(self, key, value):
        self.values[key] = value


class FakeEngine(AudioEngine):
    def __init__(self):
        super().__init__()
        self.loads = []
        self.seeks = []
    def load(self, data, position=0, autoplay=True):
        self.loads.append((data, position))
        self.playingChanged.emit(autoplay)
    def play(self):
        self.playingChanged.emit(True)
    def pause(self):
        self.playingChanged.emit(False)
    def stop(self):
        self.playingChanged.emit(False)
    def seek(self, position):
        self.seeks.append(position)
        self.positionChanged.emit(position)
    def set_volume(self, value):
        pass
    def set_muted(self, value):
        pass
    def close(self):
        self.stop()


class CacheAndSpectrumTests(unittest.TestCase):
    def test_lru_byte_budget_and_revision_replacement(self):
        cache = AudioCache(6)
        cache.put(('a', '1'), b'aaa', {})
        cache.put(('b', '1'), b'bbb', {})
        cache.get(('a', '1'))
        cache.put(('c', '1'), b'ccc', {})
        self.assertIsNone(cache.get(('b', '1')))
        cache.put(('a', '2'), b'aa', {})
        self.assertIsNone(cache.get(('a', '1')))
        self.assertEqual(cache.size, 5)

    def test_hash_detects_same_size_same_timestamp_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'song.tbm')
            path.write_bytes(b'old')
            stat = path.stat()
            before = revision(str(path))
            path.write_bytes(b'new')
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            self.assertNotEqual(before, revision(str(path)))

    def test_spectrum_distinguishes_silence_and_known_tone(self):
        silence = spectrum([0.0] * 512, 44100)
        tone = spectrum([math.sin(2 * math.pi * 1000 * i / 44100) for i in range(512)], 44100)
        self.assertEqual(silence, [0.0] * 24)
        peak = max(range(24), key=tone.__getitem__)
        self.assertTrue(10 <= peak <= 15, peak)
        self.assertGreater(tone[peak], 0.9)


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = DatabaseService(Path(self.temp.name, 'library.sqlite'))
        self.library = LibraryService(self.db)
        self.settings = MemorySettings()
        self.transport = FakeEngine()
        self.player = PlayerService(self.transport, self.library, self.settings)
        self.vm = PlayerViewModel(self.player)
        self.lib_vm = LibraryViewModel(self.library, self.player)
        self.window_vm = WindowViewModel(self.settings)
        self.qml = None

    def tearDown(self):
        if self.qml:
            shiboken6.delete(self.qml)
        self.player.close()
        self.library.close()
        self.db.close()
        self.temp.cleanup()

    def add(self, path: str, title='Track', duration=0):
        track = Track(path, title, duration=duration)
        self.db.add([track])
        self.library.model.append([track])

    def load_qml(self):
        self.qml = QQmlApplicationEngine()
        for name, obj in {'playerVM': self.vm, 'libraryVM': self.lib_vm, 'playlistModel': self.library.proxy, 'windowVM': self.window_vm}.items():
            self.qml.rootContext().setContextProperty(name, obj)
        MESSAGES.clear()
        self.qml.load(QUrl.fromLocalFile(str(ROOT / 'ui/Main.qml')))
        self.assertTrue(self.qml.rootObjects(), '\n'.join(MESSAGES))
        window = self.qml.rootObjects()[0]
        self.window_vm.window = window
        QTest.qWait(150)
        return window

    def test_library_scan_search_favorite_remove_never_deletes_source(self):
        path = Path(self.temp.name, 'song.tbm')
        path.write_bytes(b'not decoded while scanning')
        self.library.scan([self.temp.name])
        self.assertTrue(until(lambda: self.library.model.rowCount() == 1))
        self.assertEqual(self.transport.loads, [])
        self.lib_vm.search('song')
        self.assertEqual(self.library.proxy.rowCount(), 1)
        self.lib_vm.toggleFavorites()
        self.assertEqual(self.library.proxy.rowCount(), 0)
        self.library.favorite(str(path))
        self.assertEqual(self.library.proxy.rowCount(), 1)
        self.assertTrue(self.db.load()[0].favorite)
        self.lib_vm.remove(str(path))
        self.assertTrue(path.exists())
        self.assertEqual(self.db.load(), [])

    def test_invalid_decode_is_reported_and_can_be_cancelled(self):
        path = Path(self.temp.name, 'bad.tbm')
        path.write_bytes(b'bad')
        self.add(str(path))
        messages = []
        self.player.status.connect(messages.append)
        self.player.select(str(path))
        self.assertTrue(until(lambda: not self.player.busy))
        self.assertFalse(self.transport.loads)
        self.assertTrue(any('TBM' in m for m in messages))
        self.player.select(str(path))
        self.player.stop()
        QTest.qWait(150)
        self.assertFalse(self.transport.loads)
        self.assertIsNone(self.player.process)

    def test_library_path_alias_updates_favorite_current_and_removes_database_row(self):
        source = Path(self.temp.name, 'song.tbm')
        source.write_bytes(b'original source')
        nested = Path(self.temp.name, 'nested')
        nested.mkdir()
        alias = os.path.join(str(nested), '..', source.name)
        self.library.scan([self.temp.name])
        self.assertTrue(until(lambda: self.library.model.rowCount() == 1))
        self.lib_vm.toggleFavorites()
        self.library.favorite(alias)
        self.assertEqual(self.library.proxy.rowCount(), 1)
        self.assertTrue(self.db.load()[0].favorite)
        self.library.model.set_current(alias)
        self.assertEqual(self.library.model.current_path, str(source.resolve()))
        self.library.remove(alias)
        self.assertEqual(self.library.model.rowCount(), 0)
        self.assertEqual(self.db.load(), [])
        self.assertEqual(source.read_bytes(), b'original source')

    @unittest.skipUnless(os.name == 'nt', 'Windows short paths only')
    def test_library_scan_accepts_windows_short_path_for_favorite_and_removal(self):
        import ctypes
        folder = Path(self.temp.name, 'Long library folder name')
        folder.mkdir()
        source = folder / 'song.tbm'
        source.write_bytes(b'original source')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        kernel.GetShortPathNameW.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        length = kernel.GetShortPathNameW(str(source), buffer, len(buffer))
        if not length or buffer.value.casefold() == str(source).casefold():
            self.skipTest('8.3 short names are unavailable on this filesystem')
        self.library.scan([buffer.value])
        self.assertTrue(until(lambda: self.library.model.rowCount() == 1))
        self.lib_vm.search('song')
        self.lib_vm.toggleFavorites()
        self.library.favorite(buffer.value)
        self.assertEqual(self.library.proxy.rowCount(), 1)
        self.assertTrue(self.db.load()[0].favorite)
        self.library.remove(buffer.value)
        self.assertEqual(self.db.load(), [])
        self.assertTrue(source.exists())

    def test_sequence_queue_repeat_and_manual_stop(self):
        for p in ('a', 'b', 'c'):
            self.add(p, p)
        selected = []
        self.player.select = lambda path, *a, **k: selected.append(path)
        self.player.path = 'a'
        self.player.next(natural=True)
        self.assertEqual(selected.pop(), 'b')
        self.player.queue.append('c')
        self.player.next()
        self.assertEqual(selected.pop(), 'c')
        self.player.repeat = 1
        self.player.next(natural=True)
        self.assertEqual(selected.pop(), 'a')
        self.player.path = 'c'
        self.player.repeat = 0
        self.player.next(natural=True)
        self.assertEqual(selected, [])
        self.player.stop()
        self.assertEqual(selected, [])

    def test_shuffle_cycle_does_not_repeat_and_repeat_all_starts_new_cycle(self):
        paths = ['a', 'b', 'c', 'd', 'e']
        for path in paths:
            self.add(path, path)
        self.player.path = 'a'
        self.vm.toggleShuffle()
        selected = ['a']
        def select(path, *args, **kwargs):
            self.player.path = path
            self.player.shuffle_seen.add(path)
            selected.append(path)
        self.player.select = select
        for _ in range(4):
            self.player.next(natural=True)
        self.assertEqual(set(selected), set(paths))
        self.assertEqual(len(selected), 5)
        self.player.next(natural=True)
        self.assertEqual(len(selected), 5)
        self.player.repeat = 2
        previous = selected[-1]
        self.player.next(natural=True)
        self.assertEqual(len(selected), 6)
        self.assertNotEqual(selected[-1], previous)
        for _ in range(3):
            self.player.next(natural=True)
        self.assertEqual(len(set(selected[4:9])), 5)

    def test_shuffle_random_first_track_and_setting_persists_immediately(self):
        for path in ('a', 'b', 'c'):
            self.add(path, path)
        self.vm.toggleShuffle()
        self.assertIs(self.settings.get('shuffle'), True)
        with patch('app.services.player_service.random.choice', return_value='c') as choice, patch.object(self.player, 'select') as select:
            self.player.toggle()
            choice.assert_called_once_with(['a', 'b', 'c'])
            select.assert_called_once_with('c', 0)
        self.vm.toggleShuffle()
        self.assertIs(self.settings.get('shuffle'), False)
        self.assertEqual(self.player.shuffle_remaining, [])

    def test_shuffle_respects_filter_queue_and_single_track(self):
        for path in ('a', 'b', 'c'):
            self.add(path, path)
        self.player.path = 'a'
        self.vm.toggleShuffle()
        self.lib_vm.search('b')
        with patch.object(self.player, 'select') as select:
            self.player.next(natural=True)
            select.assert_called_once_with('b', automatic=True)
        self.player.queue.append('c')
        with patch.object(self.player, 'select') as select:
            self.player.next()
            select.assert_called_once_with('c', automatic=False)
        self.player.path = 'b'
        self.player.shuffle_seen.add('b')
        with patch.object(self.player, 'select') as select:
            self.player.next(natural=True)
            select.assert_not_called()
            self.player.next()
            select.assert_called_once_with('b', automatic=False)

    def test_decode_errors_skip_all_bad_tracks_once_even_with_repeat(self):
        for repeat in (0, 1, 2):
            with self.subTest(repeat=repeat):
                self.player.repeat = repeat
                self.player.shuffle = repeat == 2
                paths = []
                for index in range(3):
                    path = Path(self.temp.name, f'bad-{repeat}-{index}.tbm')
                    path.write_bytes(b'invalid TBM')
                    self.add(str(path), str(path.name))
                    paths.append(str(path))
                # Filter out tracks created in previous subtests.
                self.lib_vm.search(f'bad-{repeat}-')
                messages = []
                self.player.status.connect(messages.append)
                self.player.select(paths[0])
                self.assertTrue(until(lambda: any('không còn bài' in m for m in messages)))
                skipped = [m for m in messages if m.startswith('Bỏ qua ')]
                self.assertEqual(len(skipped), 3)
                self.assertEqual(self.player.failed_paths, set(paths))
                self.assertFalse(self.player.playing)
                self.assertFalse(self.player.busy)
                self.assertFalse(self.player.loaded)
                QTest.qWait(250)
                self.assertEqual(len([m for m in messages if m.startswith('Bỏ qua ')]), 3)
                self.player.status.disconnect(messages.append)

    def test_audio_error_skips_to_queued_track_and_stop_cancels_recovery(self):
        for path in ('a', 'b', 'c'):
            self.add(path, path)
        self.player.path = 'a'
        self.player.playback_requested = True
        self.player.loaded = True
        self.player.repeat = 1
        self.player.queue.append('c')
        with patch.object(self.player, 'select') as select:
            self.transport.error.emit('Audio backend rejected track')
            self.assertTrue(until(lambda: select.called))
            select.assert_called_once_with('c', record_history=False, automatic=True)
        self.assertIn('a', self.player.failed_paths)
        self.assertFalse(self.player.loaded)
        self.player.playback_requested = True
        with patch.object(self.player, 'select') as select:
            self.transport.error.emit('Audio backend rejected track')
            self.player.stop()
            QTest.qWait(200)
            select.assert_not_called()

    def test_error_at_end_wraps_and_failed_export_does_not_skip_playback(self):
        for path in ('a', 'b', 'c'):
            self.add(path, path)
        self.player.path = 'c'
        self.player.playback_requested = True
        with patch.object(self.player, 'select') as select:
            self.transport.error.emit('Cannot play')
            self.assertTrue(until(lambda: select.called))
            select.assert_called_once_with('a', record_history=False, automatic=True)
        self.player.path = 'a'
        self.player.playback_requested = True
        self.player.loaded = True
        self.player._playing(True)
        with patch.object(self.player, 'select') as select:
            self.player._error('Cannot write exported OGG', playback=False)
            QTest.qWait(200)
            select.assert_not_called()
        self.assertTrue(self.player.playing)
        self.assertTrue(self.player.loaded)

    def test_manual_selection_cancels_pending_skip_and_allows_retry(self):
        path = Path(self.temp.name, 'retry.tbm')
        path.write_bytes(b'invalid')
        self.add(str(path))
        self.player.path = str(path)
        self.player.playback_requested = True
        self.transport.error.emit('Cannot play')
        self.assertTrue(self.player.recovery_timer.isActive())
        self.player.select(str(path))
        self.assertFalse(self.player.recovery_timer.isActive())
        self.assertEqual(self.player.failed_paths, set())
        self.player.stop()

    def test_qt_engine_only_reports_failure_after_memory_and_file_attempts(self):
        engine = QtAudioEngine()
        errors = []
        engine.error.connect(errors.append)
        try:
            engine.data = b'OggS test'
            with patch.object(engine.player, 'setSource') as set_source:
                engine._error(None, 'Memory source failed')
                self.assertTrue(engine.fallback)
                self.assertEqual(errors, [])
                self.assertEqual(set_source.call_count, 1)
                engine._error(None, 'File source failed')
                self.assertEqual(len(errors), 1)
            engine.close()
            engine._error(None, 'Late error from released source')
            self.assertEqual(len(errors), 1)
        finally:
            engine.close()

    def test_shuffle_button_is_available_on_both_faces(self):
        self.add('a', 'Alpha')
        window = self.load_qml()
        front = window.findChild(QObject, 'playerShuffleButton')
        back = window.findChild(QObject, 'libraryShuffleButton')
        self.assertIsNotNone(front)
        self.assertIsNotNone(back)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(138, 350))
        self.assertTrue(self.player.shuffle)
        self.assertTrue(front.property('accent'))
        self.assertTrue(back.property('accent'))
        self.assertIs(self.settings.get('shuffle'), True)

    def test_qml_flip_maintains_transport_scroll_and_reel_angle(self):
        for i in range(1000):
            self.add(str(i), f'Soundtrack {i:04}')
        window = self.load_qml()
        card = window.findChild(QObject, 'flipCard')
        track_list = window.findChild(QObject, 'trackList')
        hubs = window.findChildren(QObject, 'reelHub')
        self.assertEqual(len(hubs), 2)
        self.player.loaded = True
        self.player.path = '0'
        self.player._playing(True)
        self.assertTrue(until(lambda: hubs[0].property('rotation') > 3, 2000))
        self.player._playing(False)
        QTest.qWait(40)
        angle = hubs[0].property('rotation')
        QTest.qWait(100)
        self.assertAlmostEqual(hubs[0].property('rotation'), angle, delta=0.1)
        self.player._playing(True)
        self.assertTrue(until(lambda: abs(hubs[0].property('rotation') - angle) > 1, 2000))
        card.setProperty('flipped', True)
        QTest.qWait(450)
        track_list.setProperty('contentY', 900)
        before = track_list.property('contentY')
        self.player.loaded = True
        self.player.path = '0'
        self.player._playing(True)
        for _ in range(4):
            card.setProperty('flipped', not card.property('flipped'))
            QTest.qWait(450)
        self.assertAlmostEqual(track_list.property('contentY'), before, delta=1)
        self.assertTrue(self.player.playing)
        self.assertEqual(self.transport.loads, [])
        self.assertEqual((window.width(), window.height()), (640, 440))
        errors = [m for m in MESSAGES if any(s in m for s in ('TypeError', 'ReferenceError', 'failed', 'Error:', 'Unable to assign', 'Binding loop'))]
        self.assertEqual(errors, [])
        output = ROOT / 'work/screenshots'
        output.mkdir(parents=True, exist_ok=True)
        window.grabWindow().save(str(output / 'library.png'))
        card.setProperty('flipped', False)
        QTest.qWait(450)
        window.grabWindow().save(str(output / 'player.png'))

    def test_qml_shortcuts_input_dark_theme_and_context_menu(self):
        self.add('a', 'Alpha')
        self.add('b', 'Beta')
        window = self.load_qml()
        self.player.path = 'a'
        self.player.loaded = True
        QTest.keyClick(window, Qt.Key_Space)
        self.assertTrue(until(lambda: self.player.playing))
        QTest.keyClick(window, Qt.Key_Tab)
        card = window.findChild(QObject, 'flipCard')
        self.assertTrue(until(lambda: card.property('flipped')))
        QTest.qWait(500)
        QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier, QPoint(130, 148))
        QTest.qWait(80)
        QTest.keyClick(window, Qt.Key_Escape)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(125, 92))
        search = window.findChild(QObject, 'searchInput')
        self.assertTrue(search.property('activeFocus'))
        QTest.keyClick(window, Qt.Key_Space)
        self.assertTrue(self.player.playing)
        QTest.keyClick(window, Qt.Key_Tab)
        self.assertTrue(card.property('flipped'))
        self.window_vm.toggleTheme()
        QTest.qWait(100)
        output = ROOT / 'work/screenshots'
        output.mkdir(parents=True, exist_ok=True)
        window.grabWindow().save(str(output / 'dark.png'))
        errors = [m for m in MESSAGES if any(s in m for s in ('TypeError', 'ReferenceError', 'Error:', 'Binding loop'))]
        self.assertEqual(errors, [])

    @unittest.skipUnless(os.getenv('TBM_TEST_FILE'), 'Set TBM_TEST_FILE to test real game audio')
    def test_real_tbm_decode_memory_audio_pcm_pause_seek_export(self):
        path = str(Path(os.environ['TBM_TEST_FILE']).resolve())
        self.add(path)
        self.player.close()
        engine = QtAudioEngine()
        self.player = PlayerService(engine, self.library, self.settings)
        errors, levels = [], []
        engine.error.connect(errors.append)
        self.player.spectrumChanged.connect(levels.append)
        bad = Path(self.temp.name, 'broken-before-real-track.tbm')
        bad.write_bytes(b'invalid TBM')
        self.add(str(bad), 'Broken track')
        self.player.select(str(bad))
        self.assertTrue(until(lambda: self.player.playing or errors, 30000), str(errors))
        self.assertFalse(errors)
        self.assertEqual(self.player.path, path)
        self.assertTrue(until(lambda: self.player.position > 200 and any(max(v) > 0 for v in levels), 10000))
        self.assertFalse(engine.fallback, 'Expected RAM playback')
        self.assertGreater(self.player.duration, 1000)
        self.player.toggle()
        self.assertTrue(until(lambda: not self.player.playing))
        engine.seek(1000)
        self.player.toggle()
        self.assertTrue(until(lambda: self.player.playing))
        export = Path(self.temp.name, 'export.ogg')
        self.player.select(path, export=str(export))
        self.assertTrue(until(lambda: not self.player.busy, 30000))
        self.assertTrue(export.read_bytes().startswith(b'OggS'))
        self.assertTrue(self.player.playing)
        self.assertEqual(len(self.player.cache.entries), 1)
        # Repeated decode requests are killed before replacement starts.
        for _ in range(12):
            self.player.select(path)
        self.assertTrue(until(lambda: not self.player.busy, 30000))
        self.assertTrue(until(lambda: self.player.playing, 10000))
        self.assertFalse(errors)


if __name__ == '__main__':
    unittest.main(verbosity=2)
