from dataclasses import dataclass


@dataclass
class Track:
    path: str
    title: str
    artist: str = ''
    duration: float = 0.0
    favorite: bool = False
