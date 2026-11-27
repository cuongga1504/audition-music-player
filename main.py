"""Desktop entry point; --decode-worker runs without importing the GUI."""
from __future__ import annotations
import sys

if '--decode-worker' in sys.argv:
    from app.workers.decoder_worker import run
    index = sys.argv.index('--decode-worker')
    raise SystemExit(run(sys.argv[index + 1], sys.argv[index + 2] if len(sys.argv) > index + 2 else '', sys.argv[index + 3] if len(sys.argv) > index + 3 else ''))

import argparse
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Property, Signal, Slot, QStandardPaths, QTimer, QUrl, Qt, qInstallMessageHandler
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from app.core.audio_engine import QtAudioEngine
from app.services.database_service import DatabaseService
from app.services.settings_service import SettingsService
from app.services.library_service import LibraryService
from app.services.player_service import PlayerService
from app.viewmodels.player_viewmodel import PlayerViewModel
from app.viewmodels.library_viewmodel import LibraryViewModel


class WindowViewModel(QObject):
    changed = Signal()

    def __init__(self, settings: SettingsService) -> None:
        super().__init__()
        self.settings = settings
        self.dark = settings.get('dark', 'false') in (True, 'true')
        self.pinned = settings.get('pinned', 'false') in (True, 'true')
        self.window = None

    darkTheme = Property(bool, lambda self: self.dark, notify=changed)
    alwaysOnTop = Property(bool, lambda self: self.pinned, notify=changed)

    @Slot()
    def toggleTheme(self) -> None:
        self.dark = not self.dark
        self.settings.set('dark', self.dark)
        self.changed.emit()

    @Slot()
    def togglePin(self) -> None:
        self.pinned = not self.pinned
        self.settings.set('pinned', self.pinned)
        if self.window:
            self.window.setFlag(Qt.WindowStaysOnTopHint, self.pinned)
            self.window.show()
        self.changed.emit()

    @Slot()
    def minimizeToTray(self) -> None:
        if self.window and QSystemTrayIcon.isSystemTrayAvailable():
            self.window.hide()
        elif self.window:
            self.window.showMinimized()


def run() -> int:
    parser = argparse.ArgumentParser(description='TBM Cassette Player')
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--smoke-test', action='store_true', help='Load QML and exit after 2 seconds')
    parser.add_argument('--play', action='store_true', help='Play the first imported track after scanning')
    args = parser.parse_args()
    application = QApplication(sys.argv)
    application.setApplicationName('TBM Cassette Player')
    application.setOrganizationName('TBM')
    application.setStyle('Fusion')
    QQuickStyle.setStyle('Basic')
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=data_dir / 'player.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    def qt_message(kind, context, message: str) -> None:
        logging.info('Qt: %s', message)
        if sys.stderr:
            print(message, file=sys.stderr)
    qInstallMessageHandler(qt_message)
    icon = QIcon(str(root / 'assets/icons/cassette.svg'))
    application.setWindowIcon(icon)
    settings = SettingsService()
    database = DatabaseService(data_dir / 'library.sqlite3')
    library = LibraryService(database)
    transport = QtAudioEngine()
    service = PlayerService(transport, library, settings)
    player_vm = PlayerViewModel(service)
    library_vm = LibraryViewModel(library, service)
    window_vm = WindowViewModel(settings)
    engine = QQmlApplicationEngine()
    for name, obj in {'playerVM': player_vm, 'libraryVM': library_vm, 'playlistModel': library.proxy, 'windowVM': window_vm}.items():
        engine.rootContext().setContextProperty(name, obj)
    engine.load(QUrl.fromLocalFile(str(root / 'ui/Main.qml')))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    window_vm.window = window
    if window_vm.pinned:
        window.setFlag(Qt.WindowStaysOnTopHint, True)
        window.show()
    saved = settings.get('windowPosition')
    if saved is not None and any(screen.availableGeometry().contains(saved) for screen in application.screens()):
        window.setPosition(saved)
    tray = QSystemTrayIcon(icon, application)
    tray.setToolTip('TBM Cassette Player')
    menu = QMenu()
    def show_window() -> None:
        window.showNormal()
        window.raise_()
        window.requestActivate()
    menu.addAction('Show player', show_window)
    menu.addAction('Play / pause', player_vm.toggle)
    menu.addAction('Next', player_vm.next)
    menu.addSeparator()
    menu.addAction('Quit', application.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: show_window() if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
    tray.show()
    shortcuts = []
    for key, callback in [('Media Play', player_vm.toggle), ('Media Pause', player_vm.toggle), ('Media Next', player_vm.next), ('Media Previous', player_vm.previous), ('Media Stop', player_vm.stop)]:
        shortcut = QShortcut(QKeySequence(key), window)
        shortcut.activated.connect(callback)
        shortcuts.append(shortcut)
    def shutdown() -> None:
        settings.set('windowPosition', window.position())
        settings.set('roots', library.roots)
        service.close()
        library.close()
        database.close()
        settings.sync()
        tray.hide()
    application.aboutToQuit.connect(shutdown)
    roots = settings.get('roots', [])
    library.roots = roots if isinstance(roots, list) else ([roots] if roots else [])
    if args.paths:
        if args.play:
            def play_imported() -> None:
                library.changed.disconnect(play_imported)
                imported = [t.path for t in library.model.tracks if any(Path(p).resolve() == Path(t.path) or Path(p).is_dir() and Path(t.path).is_relative_to(Path(p).resolve()) for p in args.paths)]
                if imported:
                    service.select(imported[0])
            library.changed.connect(play_imported)
        library.scan([str(Path(path).resolve()) for path in args.paths])
    smoke = {'audio': False}
    if args.smoke_test:
        service.spectrumChanged.connect(lambda levels: smoke.update(audio=True) if any(levels) else None)
        QTimer.singleShot(10000 if args.play else 2000, application.quit)
    result = application.exec()
    # Destroy QML while its context objects are still alive.
    import shiboken6
    shiboken6.delete(engine)
    return 2 if args.smoke_test and args.play and not smoke['audio'] else result


if __name__ == '__main__':
    raise SystemExit(run())
