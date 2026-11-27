"""24 logarithmic frequency bands from actual PCM; no synthetic animation."""
from __future__ import annotations
import cmath
import math
import struct
import time
from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QAudioBuffer, QAudioFormat


def spectrum(samples: list[float], rate: int, bands: int = 24) -> list[float]:
    size = 512
    if len(samples) < size or rate <= 0:
        return [0.0] * bands
    values = [complex(samples[i] * (0.5 - 0.5 * math.cos(2 * math.pi * i / (size - 1)))) for i in range(size)]
    j = 0
    for i in range(1, size):
        bit = size >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            values[i], values[j] = values[j], values[i]
    length = 2
    while length <= size:
        step = cmath.exp(-2j * math.pi / length)
        for start in range(0, size, length):
            phase = 1 + 0j
            for k in range(length // 2):
                u = values[start + k]
                v = values[start + k + length // 2] * phase
                values[start + k], values[start + k + length // 2] = u + v, u - v
                phase *= step
        length *= 2
    result = []
    upper = min(rate / 2, 16000)
    for band in range(bands):
        lo = max(1, int(40 * (upper / 40) ** (band / bands) * size / rate))
        hi = min(size // 2, max(lo + 1, int(40 * (upper / 40) ** ((band + 1) / bands) * size / rate)))
        peak = max((abs(values[i]) * 4 / size for i in range(lo, hi)), default=0)
        result.append(max(0.0, min(1.0, (20 * math.log10(max(peak, 1e-6)) + 60) / 60)))
    return result


class AudioAnalyzer(QObject):
    levels = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.last_update = 0.0
        self.samples: list[float] = []

    def consume(self, buffer: QAudioBuffer) -> None:
        now = time.monotonic()
        if not self.active or not buffer.isValid():
            return
        fmt = buffer.format()
        types = {
            QAudioFormat.SampleFormat.Float: ('f', 1.0, 0),
            QAudioFormat.SampleFormat.Int16: ('h', 32768.0, 0),
            QAudioFormat.SampleFormat.Int32: ('i', 2147483648.0, 0),
            QAudioFormat.SampleFormat.UInt8: ('B', 128.0, 128),
        }
        spec = types.get(fmt.sampleFormat())
        if not spec or fmt.channelCount() < 1:
            return
        code, scale, offset = spec
        raw = bytes(buffer.constData())[:buffer.byteCount()]
        count = min(len(raw) // struct.calcsize(code), 8192 * fmt.channelCount())
        values = struct.unpack_from('<' + code * count, raw)
        channels = fmt.channelCount()
        self.samples.extend((sum(values[i:i+channels]) / channels - offset) / scale for i in range(0, count - channels + 1, channels))
        self.samples = self.samples[-512:]
        if now - self.last_update >= 1 / 30:
            self.last_update = now
            self.levels.emit(spectrum(self.samples, fmt.sampleRate()))

    def reset(self) -> None:
        self.samples.clear()
        self.levels.emit([0.0] * 24)
