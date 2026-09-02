# -*- coding: utf-8 -*-
"""أساس عدة المحاذاة (D-024) — مسارات، قراءة أصول .jz، تطبيع rasm-aware، اكتشاف الأدوات.

المبدأ: لا نقصّ الصوت ولا نعيد توزيعه — نفهرسه (DECISIONS D-024).
"""
import json
import os
import re
import socket
import subprocess
import sys
import zlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# مهلة شبكية عامة: دفعة 08-31 علقت 48 دقيقة على urlretrieve بلا مهلة
socket.setdefaulttimeout(60)


def fetch_retry(url, dest, attempts=5, timeout=120):
    """تنزيل بمهلة وإعادة محاولات وتحقق Content-Length الكامل (درس rafiq-v2:
    تنزيل مبتور بصمت 21/37.8م.ب كاد يمر) — يحذف الجزئي عند الفشل.

    ⚠️ درس 2026-09-02: السورة التي يفشل جلبها تُسقط من الفهرس نهائياً، فينقص
    القارئ بلا أن يظهر عطبٌ في أي مكان — والخادم البعيد يخنق الطلبات المتلاحقة
    من أربع عمليات متوازية. فالمحاولات خمسٌ **بتراجع أسّي** (1·2·4·8ث) لا
    متلاحقة، ومهلةٌ صريحة على المقبس كي لا تُعلّق الدفعةَ وصلةٌ ميتة بلا نهاية.
    """
    import urllib.request
    import time as _time
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                expected = int(r.headers.get("Content-Length") or 0)
                with open(dest, "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
            got = os.path.getsize(dest)
            if got > 1000 and (expected == 0 or got == expected):
                return dest
            raise IOError(f"ملف مبتور: {got}/{expected}")
        except Exception as ex:
            last = ex
            if os.path.exists(dest):
                os.remove(dest)
            if i == attempts - 1:
                raise
            _time.sleep(2 ** i)  # 1 · 2 · 4 · 8 ثوانٍ
    raise last  # لا يُبلَغ عملياً — للوضوح لا للتنفيذ

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QURAN_ASSETS = os.path.join(ROOT, "core", "quran", "src", "main", "assets", "quran")
GGML_BIN = os.path.join(ROOT, "assets-archive", "ggml", "bin", "Release")
WHISPER_CLI = os.path.join(GGML_BIN, "whisper-cli.exe")
MODEL_Q8 = os.path.join(ROOT, "assets-archive", "ggml", "ggml-tiny-ar-quran-q8_0.bin")
WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")  # خارج git


def find_ffmpeg():
    """ffmpeg من كاش منبر (bench_whisper.py سبق واستعمله) أو من PATH."""
    for root, _, files in os.walk(
        os.path.join(os.path.dirname(ROOT), "MinbarAdkshk", "migration-cache", "ffmpeg")
    ):
        if "ffmpeg.exe" in files:
            return os.path.join(root, "ffmpeg.exe")
    return "ffmpeg"


FFMPEG = find_ffmpeg()
FFPROBE = os.path.join(os.path.dirname(FFMPEG), "ffprobe.exe") if FFMPEG.endswith(".exe") else "ffprobe"


def read_jz(path):
    with open(path, "rb") as f:
        return json.loads(zlib.decompress(f.read(), 31))


def write_jz(path, obj):
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    co = zlib.compressobj(9, zlib.DEFLATED, 31)
    with open(path, "wb") as f:
        f.write(co.compress(raw) + co.flush())


def load_index():
    return read_jz(os.path.join(QURAN_ASSETS, "index.jz"))


def load_text(riwaya):
    """نص الرواية قائمة 6236 بفهرس كوفي موحّد (فهرس الأصول القائم)."""
    return read_jz(os.path.join(QURAN_ASSETS, f"text_{riwaya}.jz"))


def surah_slice(index, surah_no):
    s = next(x for x in index["surahs"] if x["n"] == surah_no)
    return s["start"], s["start"] + s["ayahs"], s


# تطبيع rasm-aware موحّد للمرجع والمخرج (النموذج يُخرج إملائياً بلا تشكيل).
_DIAC = re.compile("[ً-ٰٟـۖ-ۭ࣓-ࣿؕ-ؚ]")
_SUBS = [
    ("ٱ", "ا"), ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
    ("ؤ", "و"), ("ئ", "ي"), ("ى", "ي"), ("ة", "ه"), ("ء", ""),
    ("ے", "ي"),  # YEH BARREE: ياء طرفية في رسم ورش/قالون (~3000 موضع) — اكتشاف rafiq-quraat
]


def norm(t):
    t = _DIAC.sub("", t)
    for a, b in _SUBS:
        t = t.replace(a, b)
    return re.sub(r"[^ء-ي ]", "", re.sub(r"\s+", " ", t)).strip()


def ffprobe_duration_ms(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return int(float(out) * 1000)


def to_wav16k(src, dst=None):
    dst = dst or src + ".16k.wav"
    if not os.path.exists(dst):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src, "-ar", "16000", "-ac", "1", dst], check=True)
    return dst
