"""Killable decoder subprocess. Binary stdout protocol, diagnostics on stderr."""
from __future__ import annotations
import json
import sys
import os
from app.core.audio_cache import revision
from app.core.tbm_decoder import decode
from pathlib import Path


def run(path: str, cached_digest: str = '', export: str = '') -> int:
    # PyInstaller's windowed bootloader sets sys.stdout/stderr to None, while
    # QProcess still supplies valid inherited Windows pipe handles.
    if os.name == 'nt' and (sys.stdout is None or sys.stderr is None):
        import ctypes
        import io
        import msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetStdHandle.argtypes = [ctypes.c_ulong]
        kernel.GetStdHandle.restype = ctypes.c_void_p
        for name, code in [('stdout', -11), ('stderr', -12)]:
            handle = kernel.GetStdHandle(code & 0xffffffff)
            fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
            setattr(sys, name, io.TextIOWrapper(os.fdopen(fd, 'wb', buffering=0), encoding='utf-8'))
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        key = revision(path)
        if key[1] == cached_digest and not export:
            sys.stdout.buffer.write(json.dumps({'key': key, 'cached': True}).encode() + b'\n')
            return 0
        track, receipt = decode(Path(path))
        if revision(path) != key:
            raise OSError('Tệp thay đổi trong lúc giải mã. Hãy thử lại.')
        if export:
            destination = Path(export)
            if destination.suffix.lower() != '.ogg':
                raise ValueError('Chỉ xuất OGG Vorbis nguyên bản.')
            created = False
            try:
                with destination.open('xb') as output:
                    created = True
                    output.write(track.data)
            except Exception:
                if created:
                    destination.unlink(missing_ok=True)
                raise
        header = json.dumps({'key': key, 'metadata': receipt, 'exported': bool(export)}).encode() + b'\n'
        sys.stdout.buffer.write(header)
        if not export:
            sys.stdout.buffer.write(track.data)
        sys.stdout.buffer.flush()
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
