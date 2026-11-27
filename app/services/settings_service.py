from PySide6.QtCore import QSettings


class SettingsService:
    def __init__(self) -> None:
        self.store = QSettings('TBM', 'CassettePlayer')

    def get(self, key: str, default=None):
        return self.store.value(key, default)

    def set(self, key: str, value) -> None:
        self.store.setValue(key, value)

    def sync(self) -> None:
        self.store.sync()
