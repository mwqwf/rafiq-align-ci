"""Exact sample duration of one complete, checksum-verified Ogg Vorbis stream.

No duration estimate or container extension is trusted. Chained streams,
missing pages, incomplete packets, bad checksums and missing EOS are rejected.
The ordinary MP3 frame counter remains a separate unchanged path.
"""
import struct


def _table():
    out = []
    for value in range(256):
        crc = value << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
        out.append(crc)
    return tuple(out)


_CRC = _table()


def checksum(page):
    crc = 0
    for byte in page:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CRC[(crc >> 24) ^ byte]
    return crc


def duration_ms(path):
    serial = None
    expected_seq = 0
    last_granule = 0
    sample_rate = None
    pending = bytearray()
    headers = 0
    eos = False
    with open(path, 'rb') as stream:
        while True:
            header = stream.read(27)
            if not header:
                break
            if eos or len(header) != 27:
                raise ValueError('Ogg truncated header or data after EOS')
            magic, version, flags, granule, stream_id, seq, stored_crc, count = struct.unpack(
                '<4sBBQIIIB', header)
            if magic != b'OggS' or version != 0 or flags & ~7:
                raise ValueError('Invalid Ogg page')
            if serial is None:
                serial = stream_id
                if flags != 2:
                    raise ValueError('Ogg must begin with a single BOS identification page')
            elif stream_id != serial or flags & 2:
                raise ValueError('Chained or interleaved Ogg streams are unsupported')
            if seq != expected_seq or bool(flags & 1) != bool(pending):
                raise ValueError('Ogg missing page or broken packet continuation')
            expected_seq += 1
            lacing = stream.read(count)
            if len(lacing) != count:
                raise ValueError('Ogg truncated lacing')
            payload = stream.read(sum(lacing))
            if len(payload) != sum(lacing):
                raise ValueError('Ogg truncated payload')
            page = header[:22] + bytes(4) + header[26:] + lacing + payload
            if checksum(page) != stored_crc:
                raise ValueError('Ogg checksum mismatch')
            pos = 0
            for size in lacing:
                pending.extend(payload[pos:pos + size])
                pos += size
                if len(pending) > 1024 * 1024:
                    raise ValueError('Ogg packet exceeds bounded size')
                if size == 255:
                    continue
                if headers < 3:
                    kind = (1, 3, 5)[headers]
                    if pending[:7] != bytes([kind]) + b'vorbis':
                        raise ValueError('Expected complete Vorbis headers')
                    if headers == 0:
                        if (len(pending) != 30 or struct.unpack_from('<I', pending, 7)[0] != 0
                                or not 1 <= pending[11] <= 8 or pending[29] != 1):
                            raise ValueError('Invalid Vorbis identification')
                        sample_rate = struct.unpack_from('<I', pending, 12)[0]
                        if not 8000 <= sample_rate <= 384000:
                            raise ValueError('Invalid Vorbis sample rate')
                    headers += 1
                pending.clear()
            if granule != 0xFFFFFFFFFFFFFFFF:
                if granule < last_granule:
                    raise ValueError('Ogg granule moved backwards')
                last_granule = granule
            if flags & 4:
                if pending or granule == 0xFFFFFFFFFFFFFFFF or headers != 3 or not granule:
                    raise ValueError('Ogg invalid EOS')
                eos = True
    if not eos or sample_rate is None:
        raise ValueError('Ogg stream lacks complete EOS')
    return last_granule * 1000.0 / sample_rate
