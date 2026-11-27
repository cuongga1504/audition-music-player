"""Adapter only: the original decoder and its validation remain untouched."""
from pathlib import Path
from audio_utils import Track
from tbm_decoder import decode_file


def decode(path: Path) -> tuple[Track, dict]:
    track, receipt = decode_file(path)
    if not track.data.startswith(b'OggS') or track.seconds <= 0:
        raise ValueError('Decoder did not return a complete OGG stream.')
    return track, receipt
