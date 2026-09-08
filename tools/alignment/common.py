# -*- coding: utf-8 -*-
"""أساس عدة المحاذاة (D-024) — مسارات، قراءة أصول .jz، تطبيع rasm-aware، اكتشاف الأدوات.

المبدأ: لا نقصّ الصوت ولا نعيد توزيعه — نفهرسه (DECISIONS D-024).
"""
import json
import os
import re
import socket
import urllib.request
import subprocess
import sys
import zlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# مهلة شبكية عامة: دفعة 08-31 علقت 48 دقيقة على urlretrieve بلا مهلة
socket.setdefaulttimeout(60)

# فاتحٌ **موضعيّ** بترويسة وكيلٍ صريحة (‏r2.dev يردّ 403 على وكيل بايثون الافتراضي).
# ⛔ لا يُنصَّب عامّاً بـ`install_opener` — انظر التعليل في `fetch_retry`.
_UA_OPENER = urllib.request.build_opener()
_UA_OPENER.addheaders = [("User-Agent", "Mozilla/5.0 (QuranRafiq tools)")]


def fetch_retry(url, dest, attempts=5, timeout=120):
    """تنزيل بمهلة وإعادة محاولات وتحقق Content-Length الكامل (درس rafiq-v2:
    تنزيل مبتور بصمت 21/37.8م.ب كاد يمر) — يحذف الجزئي عند الفشل.

    ⚠️ درس 2026-09-02: السورة التي يفشل جلبها تُسقط من الفهرس نهائياً، فينقص
    القارئ بلا أن يظهر عطبٌ في أي مكان — والخادم البعيد يخنق الطلبات المتلاحقة
    من أربع عمليات متوازية. فالمحاولات خمسٌ **بتراجع أسّي** (1·2·4·8ث) لا
    متلاحقة، ومهلةٌ صريحة على المقبس كي لا تُعلّق الدفعةَ وصلةٌ ميتة بلا نهاية.
    """
    import time as _time
    # ⚠️ r2.dev يردّ 403 على وكيل بايثون الافتراضي (درس 2026-09-06) — فترويسةٌ صريحة.
    # ⛔ **ولا `install_opener`**: هو أثرٌ جانبيٌّ على **العملية كلِّها**، فأيُّ شفرةٍ أخرى في العملية
    # نفسِها تستعمل `urllib` تصير بوكيلنا بلا أن تدري — وهذه عدّةٌ مشتركة بين التسميع والفهرسة
    # (تنبيهُ جلسة الفهرسة `github-17`، 2026-09-08). فالفاتحُ **موضعيٌّ** ويُستعمل بـ`_UA_OPENER.open`.
    last = None
    for i in range(attempts):
        try:
            with _UA_OPENER.open(url, timeout=timeout) as r:
                expected = int(r.headers.get("Content-Length") or 0)
                with open(dest, "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
            got = os.path.getsize(dest)
            # ⚠️ عطبٌ أُصلح (2026-09-08): كان الشرط `got > 1000 and (...)` فيرفض **كلَّ ملفٍ دون ألف
            # بايت ولو طابق حجمُه المعلَن** (‏`healthcheck.txt` ‏8/8 يُردّ «مبتوراً»). وحدُّ الألف موضوعٌ
            # لردّ صفحات الخطأ الصغيرة حين **لا يُعلن الخادمُ الحجم**؛ فإن أعلنه فالمطابقةُ هي الحكم.
            if (expected > 0 and got == expected) or (expected == 0 and got > 1000):
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
    """ffmpeg من أماكنه المعروفة على هذا الجهاز أو من PATH.

    ⚠️ 2026-09-07: كاش منبر (`migration-cache/ffmpeg`) حُذف في تنظيف الجهاز، وكانت الدالّة
    تسقط إلى "ffmpeg" وهو **غير موجود في PATH** فتفشل كل عدّة الصوت بلا رسالة مفهومة.
    فالبحث الآن في قائمة جذور، وآخرها PATH.
    """
    roots = [
        os.path.join(os.path.expanduser("~"), "Desktop", "claude-media", "ffbin"),
        os.path.join(os.path.dirname(ROOT), "MinbarAdkshk", "migration-cache", "ffmpeg"),
        os.path.join(ROOT, "assets-archive", "ffbin"),
    ]
    for base in roots:
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
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
        # ⛔ errors="replace": وسوم ID3 في mp3 تُسرّب بايتات ليست utf-8 إلى
        #    مخرج ffprobe، فيرمي فكّ الترميز ويُسقط السورة كلها (سورة 70/f_hajry:
        #    0xa2). العطب ترميزٌ لا صوت — فلا يُسكت الصوت من أجل بايتٍ.
        capture_output=True, text=True, errors="replace", check=True,
    ).stdout.strip()
    return int(float(out) * 1000)


def to_wav16k(src, dst=None):
    """MP3 ⇐ wav أحاديّ 16ك.هز — **بأخذ تيّار الصوت وحده**.

    ⛔ **عطبٌ مقيسٌ بثمنه (2026-09-08):** كان الأمرُ بلا `-vn`، فيتركُ اختيارَ
    التيّار لـffmpeg. وكثيرٌ من ملفّات mp3quran تحمل **غلافاً مضمَّناً في وسم
    ID3** (`APIC`)، فإن كان الغلافُ تالفاً حاول ffmpeg فكَّه **كتيّار فيديو**
    وأخرج `Failed to parse picture unit` و`PPS id 0 not available` ثم خرج
    بشفرةٍ غير صفرية — و`check=True` يجعلها قاتلة. **فتسقط السورةُ كلُّها
    لأجل صورةٍ لا يحتاجها أحد.**
    وقع على `obk` س36 (‏11.3م.ب · `Content-Type: audio/mpeg` · يبدأ بـ`ID3`
    — أي صوتٌ سليمٌ تماماً)، وأسقطه من الفهرسة **مرّتين**: في البناء الأصليّ
    فترك بصمتَه فارغةً، ثم في إعادة المحاذاة. والصوتُ بريء.
    ⇒ `-vn` يطرح كلَّ تيّارِ صورة، فلا يبقى إلا ما نريد.
    """
    dst = dst or src + ".16k.wav"
    if not os.path.exists(dst):
        base = [FFMPEG, "-y", "-v", "error"]
        tail = ["-vn", "-ar", "16000", "-ac", "1", dst]
        try:
            subprocess.run(base + ["-i", src] + tail, check=True)
        except subprocess.CalledProcessError:
            # ⛔ **الاحتياطُ الثاني — وهو الذي أنقذ `obk` س36** (قياس 2026-09-08):
            #    وسمُ ID3 فيه إطارُ غلافٍ `APIC` **يعلن 11,835 بايت والوسمُ كلُّه
            #    6,166** — فيجري المُستكشِفُ خارجَ الوسم إلى الصوت ويفكّ بايتاته
            #    كصورة، فلا يسجّل تيّارَ صوتٍ قطّ ويقول «Output file does not
            #    contain any stream». والصوتُ سليمٌ تماماً: أوّلُ إطارٍ عند 6176
            #    مزامنتُه `ff fb` أي MPEG-1 Layer III صحيح.
            #    ⇒ `-f mp3` يفرض المُفكِّك فيمسح بحثاً عن المزامنة ويتخطّى الوسم.
            #    مقيسٌ على البايتات نفسِها: بدونه لا مخرَج، وبه 512,646 بايت.
            #    ⛔ **احتياطٌ لا بديل**: يُجرَّب بعد الفشل فقط، فالمسارُ الأوّل
            #    يخدم wav وغيرَه، وفرضُ `mp3` عليها يكسرها.
            if os.path.exists(dst):
                os.remove(dst)
            subprocess.run(base + ["-f", "mp3", "-i", src] + tail, check=True)
    return dst
