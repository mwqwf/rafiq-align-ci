"""نقل بايتات أصل يوسف المحفوظة دون تغيير المصدر أو أحكام الفحص."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://archive.org/download/Adel_Al-Kalbani_128MP3_Quran/012.ogg'
SHA = '3a4cd57413d021cd4a12f51b7f9a8fe44947eca666d3bfd98268779386f4566b'
SIZE = 22578205
DURATION_MS = 1897534.693877551
MANIFEST = 'ops/source-repair/audio-fixtures/kalbani-yusuf-3a4cd574.json'
PREFIX = 'ops/source-repair/audio-fixtures/kalbani-yusuf-3a4cd574.ogg.part'

def eligible(idx):
    if idx.get('reciterId') != 'a_klb' or idx.get('riwaya') != 'hafs':
        return False
    hashes = idx.get('audioSha256') or []
    if len(hashes) < 12 or hashes[11] != SHA:
        return False
    rows = [e for e in idx.get('entries', []) if e.get('ayahId', '').startswith('12:')]
    return bool(rows) and all(e.get('fileRef') == URL for e in rows)

def assemble(dst, root=ROOT):
    root, dst = Path(root), Path(dst)
    m = json.loads((root / MANIFEST).read_text())
    if (m.get('originalUrl') != URL or m.get('sourceSha256') != SHA
            or m.get('bytes') != SIZE or m.get('sourceBytesChanged') is not False
            or m.get('canonicalTextChanged') is not False
            or m.get('partsCount') != 51):
        raise ValueError('هوية نسخة الصوت الأصلية غير مطابقة')
    parts = m.get('transportParts', [])
    if len(parts) != 51:
        raise ValueError('أجزاء نقل الصوت ناقصة')
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=dst.name + '.', suffix='.part', dir=dst.parent)
    try:
        full = hashlib.sha256()
        count = 0
        with os.fdopen(fd, 'wb') as out:
            for i, part in enumerate(parts):
                expected = PREFIX + f'{i:03d}'
                if part.get('index') != i or part.get('path') != expected:
                    raise ValueError('مسار أو ترتيب جزء النقل غير مطابق')
                data = (root / expected).read_bytes()
                want_size = 450000 if i < 50 else SIZE - 50 * 450000
                if (len(data) != want_size or part.get('bytes') != want_size
                        or hashlib.sha256(data).hexdigest() != part.get('sha256')):
                    raise ValueError('بصمة أو حجم جزء النقل غير مطابق')
                out.write(data)
                full.update(data)
                count += len(data)
        if count != SIZE or full.hexdigest() != SHA:
            raise ValueError('بصمة الصوت الكامل غير مطابقة للأصل')
        os.replace(tmp, dst)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return dst

def prime(idx, runner, destination=None):
    if not eligible(idx):
        return None
    dst = Path(destination) if destination else runner.LOCAL_CACHE / (hashlib.sha256(URL.encode()).hexdigest()[:16] + '.mp3')
    # Reconstruct and verify every time: stale or partial cache never counts as evidence.
    assemble(dst)
    container = runner._file_duration_ms(dst)
    pcm = runner._full_decode_pcm(dst)
    native = len(pcm) * 1000.0 / 16000
    if abs(container - DURATION_MS) > 2 or abs(native - DURATION_MS) > 2:
        raise ValueError('مدة الصوت الأصلي أو فكه الكامل غير مطابق')
    return {'originalUrl': URL, 'sourceSha256': SHA, 'bytes': SIZE,
            'manifest': MANIFEST, 'containerMs': container, 'nativeMs': native,
            'sourceBytesChanged': False, 'canonicalTextChanged': False,
            'wholeDecodeStrict': True, 'transportPartsVerified': 51}
