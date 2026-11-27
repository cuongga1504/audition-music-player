"""Offline TBM reader derived from the supplied VTC client, without running it.

Native reference addresses: 0040E880 (reader), 00863F30 (keys),
00BBF7F0/00BC0850 (permutation), 00BC1D00 (MT19937).
The missing Vorbis headers are reconstructed from generated libvorbis templates.
"""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

from Crypto.Cipher import Blowfish
from audio_utils import ExportError, read_vorbis, ogg_crc, MAX_STREAM

MASK = 0xffffffff
KEYS = {
    0xff01ff1a: bytes.fromhex('c6bcbeb2b8aebfa3c5cdc5d7c0ceb8d5c6ae20bfc0b5f0bcc720b5a5c0ccc5b820c6c4c0cf'),
    0xff02ff01: bytes.fromhex('bfc0b5f0bcc7b9c2c1f7b5a5c0ccc5b8c6c4c0cf'),
}


class MT19937:
    def __init__(self, seed):
        self.words = [seed & MASK]
        for i in range(1, 624):
            v = self.words[-1]
            self.words.append((1812433253 * (v ^ (v >> 30)) + i) & MASK)
        self.index = 624

    def next(self):
        if self.index == 624:
            for i in range(624):
                v = (self.words[i] & 0x80000000) | (self.words[(i + 1) % 624] & 0x7fffffff)
                self.words[i] = self.words[(i + 397) % 624] ^ (v >> 1) ^ (0x9908b0df if v & 1 else 0)
            self.index = 0
        v = self.words[self.index]
        self.index += 1
        v ^= v >> 11
        v ^= (v << 7) & 0x9d2c5680
        v ^= (v << 15) & 0xefc60000
        return (v ^ (v >> 18)) & MASK

    def between(self, low, high):
        if high < low:
            raise ExportError('Khoảng MT không hợp lệ.')
        return low + self.next() % (high - low + 1)


def resources():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent))


def tables():
    return json.loads((resources() / 'vorbis_templates.json').read_text(encoding='utf-8'))


def permutation(size, first, second, third, primes):
    if not 1 <= size <= primes[-1] or any(not 0 <= i < len(primes) for i in (first, second, third)):
        raise ExportError('Tham số hoán vị TBM không được hỗ trợ.')
    rng = MT19937(size)
    a, b, c = (rng.between(0, primes[i]) for i in (first, second, third))
    step = (c + 1 + ((a + 1) * size + 1 + b) * size) & 0x3fffffff
    modulus = next(x for x in primes if x >= size)
    if step % modulus == 0:
        step += 1
    out = []
    pos = 0
    for _ in range(modulus):
        pos = (pos + step) % modulus
        if pos < size:
            out.append(pos)
    if len(out) != size or len(set(out)) != size:
        raise ExportError('Hoán vị TBM không hợp lệ.')
    return out


def unpack_body(data, primes):
    if len(data) < 3000 or len(data) > MAX_STREAM:
        raise ExportError('Kích thước TBM không được hỗ trợ (3 KiB đến 64 MiB).')
    if data[:13] != b'AuditionMusic':
        raise ExportError('Tệp không có chữ ký AuditionMusic.')
    if data[13:16] == b'\x12\x34\0':
        return data[2500:], {'container': 'ABM', 'source_bytes': len(data)}
    if data[13:16] != b'\x12\x35\0':
        raise ExportError('Phiên bản TBM/ABM này chưa được hỗ trợ.')
    # Older client branch: fixed 12-byte trailer, no permutation or random tail.
    compressed_old, packed_old, size_old = struct.unpack_from('<3I', data, len(data) - 12)
    if (packed_old == len(data) - 2512 and packed_old % 8 == 0
            and 0 < compressed_old <= packed_old and packed_old - compressed_old < 8
            and 2504 < size_old <= MAX_STREAM):
        key = b'AuditionMusic_ABM_FILE_T3ENTERTAINMENT'.ljust(56, b'\0')
        plain = Blowfish.new(key, Blowfish.MODE_ECB).decrypt(data[2500:-12])
        decoder = zlib.decompressobj()
        try:
            raw = decoder.decompress(plain[:compressed_old], size_old - 2500 + 1)
        except zlib.error as e:
            raise ExportError('TBM cũ có checksum zlib không hợp lệ.') from e
        if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
                or len(raw) != size_old - 2500):
            raise ExportError('Kích thước hoặc kết thúc zlib TBM cũ không khớp.')
        return raw, {'container': 'TBM', 'tag': 'legacy-fixed-trailer',
                     'source_bytes': len(data), 'decoded_original_size': size_old,
                     'compressed_bytes': compressed_old, 'packed_bytes': packed_old}
    tail = data[-1] * 4 + 17
    if tail + 53 + 2500 >= len(data):
        raise ExportError('Metadata TBM bị cắt ngắn.')
    seed_at = len(data) - tail - 53
    decoded_size = struct.unpack_from('<I', data, seed_at)[0] & 0xffffff
    if not 2504 < decoded_size <= MAX_STREAM:
        raise ExportError('Kích thước giải mã TBM không hợp lệ.')
    rng = MT19937(decoded_size)
    upper = [rng.between(300, 330), rng.between(40, 80), rng.between(5, 10)]
    indices = [rng.between(0, x) for x in upper]
    positions = [x for x in permutation((decoded_size - 4) >> 10, *indices, primes) if x][:3]
    if len(positions) != 3:
        raise ExportError('TBM không có đủ vị trí metadata.')
    # Native fseek failure before file start retains the prior file cursor.
    offsets = []
    cursor = seed_at + 4
    for position in positions:
        offset = len(data) - tail - (position << 10)
        if offset < 0:
            offset = cursor
        offsets.append(offset)
        cursor = offset + 4
    if any(x + 4 > len(data) - tail for x in offsets):
        raise ExportError('Vị trí metadata TBM nằm ngoài phần thân.')
    tag, compressed, packed = (struct.unpack_from('<I', data, x)[0] for x in offsets)
    compressed &= 0xffffff
    packed &= 0xffffff
    if tag not in KEYS:
        raise ExportError(f'Biến thể TBM {tag:08X} chưa được hỗ trợ.')
    if (not 0 < compressed <= packed <= MAX_STREAM or packed % 8
            or packed - compressed >= 8 or packed + 2500 > len(data) - tail):
        raise ExportError('Các trường kích thước TBM không khớp.')
    restore = struct.unpack_from('<4I', data, len(data) - tail)
    buff = bytearray(data[:-tail])
    struct.pack_into('<I', buff, seed_at, restore[2])
    for offset, value in zip(offsets, (restore[3], restore[0], restore[1])):
        struct.pack_into('<I', buff, offset, value)
    count = 13 if tag == 0xff02ff01 else 10
    order = permutation(count, indices[0] % count, indices[1] % (count // 2),
                        indices[2] % (count // 3), primes)
    unit = packed // sum(x + 1 for x in order)
    if unit == 0:
        raise ExportError('Khối TBM quá nhỏ.')
    parts = []
    pos = 2500
    for x in order:
        size = (x + 1) * unit
        parts.append(bytes(buff[pos:pos + size]))
        pos += size
    encoded = b''.join(parts[order.index(x)] for x in range(count)) + bytes(buff[pos:2500 + packed])
    plain = Blowfish.new(KEYS[tag].ljust(56, b'\0'), Blowfish.MODE_ECB).decrypt(encoded)
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(plain[:compressed], decoded_size - 2500 + 1)
    except zlib.error as e:
        raise ExportError('Giải mã TBM thất bại: checksum/luồng zlib không hợp lệ.') from e
    if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
            or len(raw) != decoded_size - 2500):
        raise ExportError('Kích thước hoặc kết thúc zlib không khớp metadata TBM.')
    return raw, {'container': 'TBM', 'tag': f'{tag:08X}', 'source_bytes': len(data),
                 'decoded_original_size': decoded_size, 'compressed_bytes': compressed,
                 'packed_bytes': packed, 'source_adler32': f'{struct.unpack_from("<I", data, 16)[0]:08x}'}


def make_page(flags, seq, serial, packets):
    lacing = bytearray()
    for packet in packets:
        lacing.extend([255] * (len(packet) // 255) + [len(packet) % 255])
    if len(lacing) > 255:
        raise ExportError('Header Vorbis quá lớn.')
    page = bytearray(b'OggS\0' + bytes([flags]) + struct.pack('<QIII', 0, serial, seq, 0)
                     + bytes([len(lacing)]) + lacing + b''.join(packets))
    struct.pack_into('<I', page, 22, ogg_crc(page))
    return bytes(page)


def rebuild_ogg(body, templates):
    # A real first body page must be sequence 2, CRC-valid, and complete.
    candidate = 0
    first = None
    while True:
        candidate = body.find(b'OggS\0', candidate)
        if candidate < 0 or candidate > 64000:
            break
        if candidate + 27 <= len(body):
            h = body[candidate:candidate + 27]
            n = h[26]
            if candidate + 27 + n <= len(body):
                length = 27 + n + sum(body[candidate + 27:candidate + 27 + n])
                page = bytearray(body[candidate:candidate + length])
                if len(page) == length and struct.unpack_from('<I', h, 18)[0] == 2 and h[5] == 0:
                    expected = struct.unpack_from('<I', page, 22)[0]
                    page[22:26] = b'\0' * 4
                    if ogg_crc(page) == expected:
                        first = candidate
                        break
        candidate += 1
    if first is None or first < 32:
        raise ExportError('Không tìm thấy phần OGG đủ dữ liệu để khôi phục header.')
    tail = body[:first]
    matches = {}
    for item in templates:
        setup = base64.b64decode(item['setup'])
        identification = base64.b64decode(item['identification'])
        if len(setup) < first:
            continue
        expected = setup[-first:]
        differences = [i for i, (x, y) in enumerate(zip(tail, expected)) if x != y]
        # The protocol's optional repair contains 32 bytes within OGG[2500:2787].
        if differences and not (differences[0] <= 255 and differences[-1] - differences[0] < 32
                                and differences[-1] < 287):
            continue
        core = identification[:16] + identification[28:]
        identity = hashlib.sha256(core + setup).hexdigest()
        record = (len(differences), identification, setup, item['profile'])
        if identity not in matches or record[0] < matches[identity][0]:
            matches[identity] = record
    if not matches:
        raise ExportError('Chưa có mẫu codebook Vorbis khớp bài này. Không tạo tệp nhạc đoán sai.')
    minimum = min(m[0] for m in matches.values())
    best = [m for m in matches.values() if m[0] == minimum]
    if len(best) != 1:
        raise ExportError('Có nhiều codebook có thể khớp; chưa thể xác định header an toàn cho bài này.')
    repaired, identification, setup, profile = best[0]
    serial = struct.unpack_from('<I', body, first + 14)[0]
    vendor = b'Audition TBM Offline Decoder'
    comment = b'\x03vorbis' + struct.pack('<I', len(vendor)) + vendor + struct.pack('<I', 0) + b'\x01'
    header = make_page(2, 0, serial, [identification]) + make_page(0, 1, serial, [comment, setup])
    result = header + body[first:]
    def read(address, count):
        if address + count > len(result):
            raise ExportError('Luồng OGG bị cắt ngắn.')
        return result[address:address + count]
    track = read_vorbis(read, 0)
    if len(track.data) != len(result):
        raise ExportError('Có dữ liệu dư sau trang kết thúc OGG.')
    return track, {'header_reconstructed': True, 'template': profile,
                   'setup_tail_bytes_matched': first - repaired, 'setup_bytes_reconstructed': repaired,
                   'audio_pages_sha256': hashlib.sha256(body[first:]).hexdigest(),
                   'serial': serial, 'seconds': track.seconds, 'sample_rate': track.rate,
                   'channels': track.channels, 'ogg_sha256': track.digest}


def decode_file(path):
    path = Path(path)
    if path.stat().st_size > MAX_STREAM:
        raise ExportError('Tệp vượt giới hạn 64 MiB.')
    data = path.read_bytes()
    info = tables()
    body, receipt = unpack_body(data, info['permutation_primes'])
    track, details = rebuild_ogg(body, info['templates'])
    receipt.update(details)
    receipt.update(source=str(path), source_sha256=hashlib.sha256(data).hexdigest())
    return track, receipt
