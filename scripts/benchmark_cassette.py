"""Reproducible source GUI benchmark. Uses a temporary library and settings."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT))
from test_cassette import ApplicationTests, APPLICATION, until, QTest, MESSAGES
from app.core.audio_engine import QtAudioEngine
from app.services.player_service import PlayerService
from app.viewmodels.player_viewmodel import PlayerViewModel
from app.viewmodels.library_viewmodel import LibraryViewModel
from PySide6.QtCore import QObject


class Counters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]


def memory_mb() -> float:
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi')
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return round(counters.WorkingSetSize / 1024**2, 2)


def sample(seconds=3) -> dict:
    cpu, wall = time.process_time(), time.monotonic()
    QTest.qWait(int(seconds * 1000))
    elapsed = time.monotonic() - wall
    return {'working_set_mb': memory_mb(), 'cpu_one_core_percent': round((time.process_time() - cpu) / elapsed * 100, 2), 'sample_seconds': round(elapsed, 2)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    parser.add_argument('--output', default='work/benchmark.json')
    args = parser.parse_args()
    fixture = ApplicationTests()
    fixture.setUp()
    output = ROOT / 'docs/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    try:
        fixture.player.close()
        transport = QtAudioEngine()
        fixture.player = PlayerService(transport, fixture.library, fixture.settings)
        fixture.vm = PlayerViewModel(fixture.player)
        fixture.lib_vm = LibraryViewModel(fixture.library, fixture.player)
        start = time.monotonic()
        window = fixture.load_qml()
        result = {'python': sys.version, 'platform': sys.platform, 'qml_load_and_150ms_settle_seconds': round(time.monotonic() - start, 3)}
        result['idle'] = sample()
        start = time.monotonic()
        fixture.library.scan([str(Path(args.folder).resolve())])
        assert until(lambda: fixture.library.model.rowCount() > 0, 30000)
        result['scan_seconds'] = round(time.monotonic() - start, 3)
        result['library_tracks'] = fixture.library.model.rowCount()
        paths = [t.path for t in fixture.library.model.tracks[:3]]
        fixture.player.select(paths[0])
        assert until(lambda: fixture.player.playing, 30000), fixture.lib_vm.message
        result['memory_playback'] = not transport.fallback
        result['playing_front'] = sample()
        window.grabWindow().save(str(output / 'player.png'))
        card = window.findChild(QObject, 'flipCard')
        card.setProperty('flipped', True)
        QTest.qWait(600)
        result['playing_back'] = sample()
        window.grabWindow().save(str(output / 'library.png'))
        for i in range(30):
            fixture.player.select(paths[i % len(paths)])
            card.setProperty('flipped', not card.property('flipped'))
            QTest.qWait(12)
        assert until(lambda: fixture.player.playing and not fixture.player.busy, 30000)
        QTest.qWait(700)
        result['after_30_rapid_switches'] = sample()
        result['cache_bytes'] = fixture.player.cache.size
        result['retired_workers'] = len(fixture.player.retired)
        baseline = memory_mb()
        for i in range(30):
            card.setProperty('flipped', not card.property('flipped'))
            QTest.qWait(420)
        result['after_30_complete_flips'] = sample()
        result['flip_working_set_delta_mb'] = round(memory_mb() - baseline, 2)
        result['qml_errors'] = [m for m in MESSAGES if any(s in m for s in ('TypeError', 'ReferenceError', 'Error:', 'Binding loop'))]
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
    finally:
        fixture.tearDown()


if __name__ == '__main__':
    main()
