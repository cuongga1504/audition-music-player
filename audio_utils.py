"""Validated OGG parsing and local audio export helpers."""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
MAX_STREAM = 64 * 1024 * 1024
NO_WINDOW = 134217728 if os.name == 'nt' else 0

class ExportError(Exception):
    pass

def _crc_table():
    table = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = (c << 1 ^ (79764919 if c & 2147483648 else 0)) & 4294967295
        table.append(c)
    return table
CRC = _crc_table()

def ogg_crc(data):
    value = 0
    for byte in data:
        value = value << 8 & 4294967295 ^ CRC[value >> 24 ^ byte]
    return value

@dataclass
class Track:
    data: bytes
    address: int
    pid: int
    seconds: float
    rate: int
    channels: int
    digest: str

def read_vorbis(read, address, pid=0, cancel=None):
    """Validate a contiguous, complete logical stream, including every page CRC.

    read(address, size) must return the exact requested byte count or fail.
    Partial streams, chains, multiplexing, CRC failures and sequence gaps fail.
    """
    parts = []
    cursor = address
    serial = None
    sequence = 0
    first_packet = bytearray()
    packet_complete = False
    last_granule = 0
    rate = channels = 0
    previous_continues = False
    for _ in range(100000):
        if cancel is not None and cancel.is_set():
            raise ExportError('Đã hủy quét.')
        header = read(cursor, 27)
        if len(header) != 27 or header[:5] != b'OggS\x00':
            raise ExportError('Luồng OGG không liên tục hoặc không đầy đủ.')
        flags = header[5]
        granule, page_serial, seq, stored_crc = struct.unpack_from('<QIII', header, 6)
        if flags & ~7:
            raise ExportError('Cờ trang OGG không hợp lệ.')
        if sequence == 0:
            if flags != 2 or seq != 0:
                raise ExportError('Không phải đầu luồng OGG.')
            serial = page_serial
        elif flags & 2 or page_serial != serial or seq != sequence:
            raise ExportError('Thiếu trang hoặc luồng OGG bị trộn.')
        if bool(flags & 1) != previous_continues:
            raise ExportError('Gói OGG bị đứt đoạn.')
        segments = read(cursor + 27, header[26])
        if len(segments) != header[26]:
            raise ExportError('Thiếu bảng phân đoạn OGG.')
        length = 27 + len(segments) + sum(segments)
        if cursor - address + length > MAX_STREAM:
            raise ExportError('Luồng vượt giới hạn 64 MiB.')
        payload = read(cursor + 27 + len(segments), sum(segments))
        if len(payload) != sum(segments):
            raise ExportError('Thiếu dữ liệu OGG.')
        page = header + segments + payload
        check = bytearray(page)
        check[22:26] = b'\x00' * 4
        if ogg_crc(check) != stored_crc:
            raise ExportError('Checksum OGG không khớp; chưa thể xuất nhạc nguyên vẹn.')
        if not packet_complete:
            offset = 0
            for size in segments:
                first_packet.extend(payload[offset:offset + size])
                offset += size
                if len(first_packet) > 1024:
                    raise ExportError('Header nhận dạng Vorbis không hợp lệ.')
                if size < 255:
                    packet_complete = True
                    break
            if packet_complete:
                if len(first_packet) != 30 or first_packet[:7] != b'\x01vorbis':
                    raise ExportError('Không phải nhạc OGG Vorbis.')
                version = struct.unpack_from('<I', first_packet, 7)[0]
                channels = first_packet[11]
                rate = struct.unpack_from('<I', first_packet, 12)[0]
                if version != 0 or not 1 <= channels <= 8 or (not 8000 <= rate <= 192000):
                    raise ExportError('Thông số Vorbis không được hỗ trợ.')
                if not first_packet[29] & 1:
                    raise ExportError('Header Vorbis thiếu framing bit.')
        if granule != 18446744073709551615:
            if granule < last_granule:
                raise ExportError('Thứ tự thời gian OGG không hợp lệ.')
            last_granule = granule
        parts.append(page)
        cursor += length
        sequence += 1
        previous_continues = bool(segments and segments[-1] == 255)
        if flags & 4:
            if not packet_complete or previous_continues or sequence < 3 or (not rate) or (not last_granule):
                raise ExportError('Luồng OGG chưa kết thúc đầy đủ.')
            data = b''.join(parts)
            return Track(data, address, pid, last_granule / rate, rate, channels, hashlib.sha256(data).hexdigest())
    raise ExportError('Quá nhiều trang OGG.')

def find_tool(name):
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    for candidate in [base / (name + '.exe'), Path('C:\\ffmpeg\\bin') / (name + '.exe'), Path('D:\\Audition') / (name + '64.exe')]:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)

def export_audio(track, destination, ffmpeg=None):
    destination = Path(destination)
    if destination.suffix.lower() not in ('.mp3', '.ogg', '.wav'):
        raise ExportError('Định dạng xuất cần là .mp3, .ogg hoặc .wav.')
    with destination.open('xb'):
        pass
    temp = None
    try:
        if destination.suffix.lower() == '.ogg':
            destination.write_bytes(track.data)
            return
        ffmpeg = ffmpeg or find_tool('ffmpeg')
        if not ffmpeg:
            raise ExportError('Chưa tìm thấy FFmpeg. Chọn ffmpeg.exe hoặc lưu OGG trước.')
        fd, temp = tempfile.mkstemp(suffix=destination.suffix, prefix='.audition-', dir=destination.parent)
        os.close(fd)
        codec = ['-c:a', 'libmp3lame', '-q:a', '2'] if destination.suffix.lower() == '.mp3' else ['-c:a', 'pcm_s16le']
        result = subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-xerror', '-nostdin', '-y', '-f', 'ogg', '-i', 'pipe:0', '-vn', *codec, temp], input=track.data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW, timeout=180)
        if result.returncode or os.path.getsize(temp) == 0:
            detail = result.stderr.decode('utf-8', errors='replace')[-1500:]
            raise ExportError('FFmpeg không chuyển đổi được luồng: ' + detail)
        os.replace(temp, destination)
        temp = None
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        if temp:
            Path(temp).unlink(missing_ok=True)
