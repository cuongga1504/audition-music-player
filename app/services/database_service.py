from __future__ import annotations
from pathlib import Path
import sqlite3
from app.models.track import Track


class DatabaseService:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS tracks (path TEXT PRIMARY KEY COLLATE NOCASE, title TEXT NOT NULL, artist TEXT NOT NULL DEFAULT "", duration REAL NOT NULL DEFAULT 0, favorite INTEGER NOT NULL DEFAULT 0)')
        self.connection.commit()

    def load(self) -> list[Track]:
        return [Track(p, t, a, d, bool(f)) for p, t, a, d, f in self.connection.execute('SELECT path,title,artist,duration,favorite FROM tracks ORDER BY rowid')]

    def add(self, tracks: list[Track]) -> None:
        with self.connection:
            self.connection.executemany('INSERT OR IGNORE INTO tracks(path,title,artist,duration,favorite) VALUES (?,?,?,?,?)', [(t.path,t.title,t.artist,t.duration,int(t.favorite)) for t in tracks])

    def update(self, track: Track) -> None:
        with self.connection:
            self.connection.execute('UPDATE tracks SET duration=?,favorite=? WHERE path=?', (track.duration, int(track.favorite), track.path))

    def remove(self, path: str) -> None:
        with self.connection:
            self.connection.execute('DELETE FROM tracks WHERE path=?', (path,))

    def close(self) -> None:
        self.connection.close()
