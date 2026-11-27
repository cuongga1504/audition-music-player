from __future__ import annotations
import os
from pathlib import Path
from threading import Event
from PySide6.QtCore import QObject, QRunnable, Signal


class ScanSignals(QObject):
    completed = Signal(int, list, str)


class ScannerWorker(QRunnable):
    def __init__(self, generation: int, paths: list[str], cancel: Event) -> None:
        super().__init__()
        self.signals = ScanSignals()
        self.generation, self.paths, self.cancel = generation, paths, cancel

    def run(self) -> None:
        found: dict[str, str] = {}
        errors: list[str] = []
        def on_error(error: OSError) -> None:
            errors.append(str(error))
        for item in self.paths:
            if self.cancel.is_set():
                self.signals.completed.emit(self.generation, [], '')
                return
            path = Path(item)
            if path.is_dir():
                for root, dirs, files in os.walk(path, onerror=on_error):
                    if self.cancel.is_set():
                        self.signals.completed.emit(self.generation, [], '')
                        return
                    dirs[:] = [d for d in dirs if not Path(root, d).is_symlink()]
                    for name in files:
                        candidate = Path(root, name)
                        if candidate.suffix.lower() in ('.tbm', '.abm'):
                            value = str(candidate.resolve())
                            found[value.casefold()] = value
            elif path.is_file() and path.suffix.lower() in ('.tbm', '.abm'):
                value = str(path.resolve())
                found[value.casefold()] = value
            else:
                errors.append(f'Không tìm thấy tệp TBM: {path}')
        self.signals.completed.emit(self.generation, sorted(found.values(), key=str.casefold), '\n'.join(errors))
