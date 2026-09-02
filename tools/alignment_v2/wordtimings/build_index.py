# -*- coding: utf-8 -*-
"""توليد `wordtimings_{reciterId}.jz` — ملف **جانبي** لا يمسّ الفهرس المرفوع.

المخرج بصيغة §4.2 حرفياً على حدود **HIGH** وحدها. الملف **يحمل برهانه معه** في
ترويسته (`endsPolicy` و`benchmark`).

**مصمَّم لشبكة متدهورة** (أمر المالك 2026-09-01):
  · **الأطول أولاً** — أكبر ملف يُنتزع والشبكة أقوى ما تكون.
  · **جلب متحقَّق** بـContent-Length (⛔ `fetch_retry` يقبل أي ملف >1000 بايت،
    وقد مرّ علينا تنزيل مبتور صامت كاد يفسد فهرساً).
  · **نقطة حفظ بعد كل سورة** — الانقطاع لا يُفقد ما أُنجز.
  · **استئناف** من المخرج القائم بلا إعادة حساب.
  · الفاشل شبكياً **يُتخطى ويُلحق آخراً**.
  · سورة واحدة على القرص، تُحذف فور معالجتها (D-024 + قيد القرص).
"""
import argparse
import os
import sys
import time
import subprocess
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _V2)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import FFMPEG, load_index, load_text, read_jz, write_jz  # noqa: E402
from vad import read_wav, silences  # noqa: E402

from generate import ayah_word_times  # noqa: E402

ENGINE = "wordtimes-1.0-dtwend"
QALUN_URL = "https://server13.mp3quran.net/husr/Rewayat-Qalon-A-n-Nafi/{surah:03d}.mp3"
# مرآة R2 (rafiq-net) — مطابقة بايتاً-بايتاً؛ ⚠️ r2.dev يحجب وكيل بايثون
MIRROR_URL = ("https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/"
              "audio/qalun/husary_qalun/{surah:03d}.mp3")
UA = "Mozilla/5.0"
ONSET_PAD_MS = 700          # نافذة كشف بدء الكلام حول الحد (بدل VAD السورة كلها)

# ⛔ **وسم الأدلة** (مطلب حوكمة 2026-09-01): كل رقم منشور موسوم بنوعه كي يعرف
# قارئ الغد ما يستطيع البناء عليه:
#   · DETERMINISTIC = قياس على بيانات ثابتة يعطي النتيجة نفسها دوماً (لا يحتاج تكراراً).
#   · SAMPLE(n)     = عيّنة بحجم n — لها مجال ثقة ولا تُعمَّم بلا تحفظ.
BENCHMARK = {
    # عيّنة: 83 كلمة من 3 سور (الحصري/المعلم) مقارنةً بـsegments_husary (QUL).
    "startMedianErrMs": 180, "startWithin250Pct": 69.9,
    "startEvidence": "SAMPLE(83 words / 3 surahs)",
    # عيّنة: 40 كلمة لكل قياس، بذرة عشوائية ثابتة (قابل لإعادة الإنتاج حرفياً).
    "roundTripOursStrictPct": 40.0, "roundTripOursLenientPct": 72.5,
    "roundTripQulCeilingStrictPct": 20.0, "roundTripQulCeilingLenientPct": 35.0,
    "roundTripEvidence": "SAMPLE(40 words each, fixed seed 1234)",
    # عيّنة: 40 كلمة من آيات قبلتها قاعدة البرهان الكامل وحدها (بذرة 7).
    "shortAyahRuleStrictPct": 45.0, "shortAyahRuleLenientPct": 57.5,
    "shortAyahRuleEvidence": "SAMPLE(40 words, fixed seed 7)",
    # حتمي: جرد كامل على 6236 آية — لا عيّنة ولا عشوائية.
    "waqfTokensQalun": 0, "waqfTokensWarsh": 0, "waqfTokensHafs": 4364,
    "waqfEvidence": "DETERMINISTIC(full 6236 inventory)",
    "gate": "relative: ours >= QUL-ceiling - 5 points (absolute >=90% rejected: "
            "the ground truth itself does not reach it on this instrument)",
    "calibratedOn": "husary_muallim (everyayah) vs segments_husary.jz (QUL)",
    # ⚠️ حد صلاحية: السقف مقيس على حفص/المعلم والكلمات المقارَنة من قالون —
    #    ليس تكافؤاً تاماً، والهامش (+30/+27.5 نقطة) أوسع من أن يفسره فارق قارئ.
    "ceilingCaveat": "ceiling measured on hafs/muallim; our words are qalun",
}

def _open(url, method="GET"):
    return urllib.request.urlopen(
        urllib.request.Request(url, method=method, headers={"User-Agent": UA}),
        timeout=90)


def fetch_verified(url, dest, attempts=6, log=print):
    """تنزيل متين: تحقق Content-Length + إعادات بتراجع. يرفع IOError عند اليأس."""
    expect = None
    try:
        h = _open(url, "HEAD")
        expect = int(h.headers.get("Content-Length") or 0) or None
    except Exception:
        pass
    if os.path.exists(dest) and expect and os.path.getsize(dest) == expect:
        return dest
    for i in range(attempts):
        try:
            with _open(url) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            size = os.path.getsize(dest)
            if expect and size != expect:
                raise IOError("مبتور: %d من %d" % (size, expect))
            if size < 10000:
                raise IOError("ملف شبه فارغ")
            return dest
        except Exception as e:
            if os.path.exists(dest):
                os.remove(dest)
            log("    محاولة %d/%d: %s %s" % (i + 1, attempts, type(e).__name__, e))
            time.sleep(min(10 * (i + 1), 60))
    raise IOError("تعذّر تنزيل " + url)


def parse_range(spec):
    out = set()
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out or None


def index_fingerprint(path, ti):
    """بصمة الفهرس المصدر: حجم+زمن+توليد+عدد HIGH — يكشف الانحراف آلياً."""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {"file": os.path.basename(path), "sha256": h.hexdigest(),
            "generatedAt": ti.get("generatedAt"),
            "engineVersion": ti.get("engineVersion"),
            "highCount": sum(1 for e in ti.get("entries", [])
                             if e.get("confBand") == "HIGH")}


def write_doc(args, ti, entries, coverage=None):
    doc = {"schema": 1, "riwaya": args.riwaya, "reciterId": ti.get("reciterId"),
           "engineVersion": ENGINE, "method": "ASR_DTW_WORD",
           "endsPolicy": "contiguous", "benchmark": BENCHMARK,
           # ⛔ اصطلاح الفهرسة صريح كي لا يخمّنه مستهلك بعد سنة: الكلمة الواحدة =
           #    **رمز خام واحد** من `text_{riwaya}.jz` (split على النص كما هو).
           #    قياس github-7c: `segments_husary` تحاذي الرموز الخام 6236/6236 =
           #    100% مقابل 56.4% للكلمات «الحقيقية» — فعلامة الوقف المستقلة تأخذ
           #    مقطعاً زمنياً. أي اصطلاح آخر يُزيغ التظليل في كل آية فيها علامة وقف.
           "indexing": "RAW_TOKENS",
           # أساس الزمن: SURAH_FILE (أزمنة مطلقة في ملف السورة) أو PER_FILE (كل آية ملف يبدأ من 0)
           "timeBase": getattr(args, "time_base", None) or "SURAH_FILE",
           "generatedAt": int(time.time() * 1000),
           "sourceIndex": os.path.basename(args.index),
           # ⛔ الفهرس قد يُعاد توليده تحت المخرج (حدث فعلاً: 4018←4217 HIGH).
           #    البصمة تجعل الانحراف مكشوفاً آلياً لأي قارئ لاحق.
           "generatedAgainst": index_fingerprint(args.index, ti),
           # ⛔ نطاق التغطية **بالأرقام لا بالأسماء**: «جزء 30» اسماً تعني للتطبيق
           #    تغطية كاملة، والحقيقة قد تكون 53% — فيصير الاسم وعداً كاذباً.
           #    الكائن {item, covered, high} يجعل التطبيق يعرض الميزة عند الآية
           #    التي تملك توقيتاً ويصمت عند غيرها، بلا ادعاء على مستوى الجزء.
           "coverageScope": list(coverage or []),
           "notes": "t_dtw يؤشّر نهاية الكلمة؛ الكلمة j = [نهاية j-1، نهاية j]. "
                    "النهايات ملصوقة عمداً (تظليل متصل) فلا تُقارن بنهايات QUL.",
           "entries": sorted(entries,
                             key=lambda e: (int(e["ayahId"].split(":")[0]),
                                            int(e["ayahId"].split(":")[1])))}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    write_jz(args.out, doc)


def local_onset(src, t_ms, tag_dir, key=""):
    """بدء الكلام قرب الحد، من **نافذة قصيرة** لا من wav السورة كاملة.

    ⛔ الدرس الذي فرض هذا: تحويل سورة البقرة إلى wav 16ك أنتج **336م.ب** لملف
    mp3 حجمه 168م.ب — أي نصف غيغابايت لسورة واحدة على قرص حرّه أقل من ذلك.
    والـwav لم يكن مطلوباً إلا لكشف بدء الكلام؛ وffmpeg يقصّ من الـmp3 مباشرة.
    """
    lo = max(0, t_ms - ONSET_PAD_MS)
    # ⛔ اسم فريد: الاسم الثابت تصادم مع بقايا عملية سابقة (WinError 32) فأسقط
    #    سورة كاملة بوصفها «تعذّراً شبكياً» — وهو تشخيص خاطئ لعلة محلية.
    tmp = os.path.join(tag_dir, "onset_%s_%d.wav" % (key, os.getpid()))
    try:
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src,
                        "-ss", "%.3f" % (lo / 1000.0),
                        "-t", "%.3f" % ((ONSET_PAD_MS * 2) / 1000.0),
                        "-ar", "16000", "-ac", "1", tmp],
                       check=True, timeout=120, stdin=subprocess.DEVNULL)
        sil = silences(tmp, min_silence_ms=80)
        for a, b in sil:
            if a <= (t_ms - lo) <= b:
                return lo + b
        return t_ms
    except Exception:
        return t_ms
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def process_surah(sn, args, ayahs, text, starts, out, stats, log=print):
    """يعالج سورة واحدة من الـmp3 مباشرة (بلا wav كامل). يرفع IOError عند تعذّر الجلب."""
    mp3 = os.path.join(args.audio_dir, "%03d.mp3" % sn)
    # مصدر الصوت قابل للتبديل بالرواية/القارئ (--audio-base/--audio-mirror)؛ الافتراضي الحصري/قالون
    base_url = getattr(args, "audio_base", None) or QALUN_URL
    # ⛔ لا تراجع إلى مرآة قالون لقارئ آخر: صوت خاطئ بصمت أسوأ من فشل صريح
    mirror_url = getattr(args, "audio_mirror", None) or (MIRROR_URL if base_url == QALUN_URL else None)
    try:
        try:
            fetch_verified(base_url.format(surah=sn), mp3, log=log)
        except IOError:
            if not mirror_url:
                raise
            log("    المصدر الأصلي تعذّر — أجرّب المرآة")
            fetch_verified(mirror_url.format(surah=sn), mp3, log=log)
        # ⚡ على خادم بقرص واسع: wav 16ك واحد للسورة يجعل كل قصّ فورياً. مقيس على
        #    الخادم 2026-09-01: القصّ من mp3 بـ`-ss` بعد `-i` يفكّ الملف من أوله في كل
        #    مرة (ffmpeg ~190% CPU لكل آية، والكلفة تتصاعد مع موضع الآية) ⇒ ~8ث/آية في
        #    البقرة. الـwav محلياً ممنوع (قيد القرص، انظر local_onset) فالعلم اختياري.
        src = mp3
        if getattr(args, "full_wav", False):
            from common import to_wav16k
            src = to_wav16k(mp3)
        added = 0
        for e in sorted(ayahs, key=lambda x: x["startMs"]):
            stats["ayahs"] += 1
            an = int(e["ayahId"].split(":")[1])
            raw = text[starts[sn] + an - 1]
            onset = local_onset(src, e["startMs"], args.audio_dir, e["ayahId"].replace(":", "_"))
            try:
                words, meta = ayah_word_times(
                    src, e["startMs"], e["endMs"], raw,
                    "wt_%s_%03d_%03d" % (args.riwaya, sn, an), onset_ms=onset)
            except Exception as ex:
                # ⛔ آية واحدة معطوبة لا تُسقط 99 سورة (انهار whisper على 2:29 فقتل
                #    الدفعة كلها). تُحسب ساقطة وتمضي المعالجة.
                log("    ⚠️ %s سقطت باستثناء: %s" % (e["ayahId"], type(ex).__name__))
                stats["dropped"]["exception"] = stats["dropped"].get("exception", 0) + 1
                continue
            if not words:
                r = meta["reason"]
                stats["dropped"][r] = stats["dropped"].get(r, 0) + 1
                continue
            if len(words) != len(raw.split()):
                # ⛔ لا يُكتب مدخل عدد كلماته ≠ عدد الرموز الخام — التطابق تام لا تقريبي
                log("    ⛔ %s: %d كلمة مقابل %d رمزاً خاماً — رُفضت"
                    % (e["ayahId"], len(words), len(raw.split())))
                stats["dropped"]["token-count"] = stats["dropped"].get("token-count", 0) + 1
                continue
            added += 1
            stats["words"] += len(words)
            out.append({
                "ayahId": e["ayahId"],
                # ⛔ برهان المدخل يُشحن معه (مطلب 2026-09-01: «لا آية تُكتب بلا برهان»):
                #    الدمج يقبل بمعيار القبول المطلق (استقراء=0 + برهان كامل) ويطبع أرقامه.
                "evidence": {"n": meta["n"], "matched": meta["matched"],
                             "exact": meta.get("exact", 0), "acc": meta["acc"],
                             "interp": meta["interp"],
                             "interpSpeech": meta.get("interpSpeech", meta["interp"]),
                             "fullEvidence": bool(meta.get("fullEvidence", False)),
                             "zeroLen": meta.get("zeroLen", 0)},
                "words": [{"wordId": "%s:%d" % (e["ayahId"], w["subIndex"] + 1),
                           "subIndex": w["subIndex"],
                           "startMs": w["startMs"], "endMs": w["endMs"],
                           "conf": round(e["conf"] * (0.7 if w["interpolated"]
                                                      else 0.95), 3)}
                          for w in words]})
        stats["withWords"] += added
        log("سورة %d: +%d/%d (الإجمالي %d)" % (sn, added, len(ayahs), len(out)))
    finally:
        for p in (mp3, mp3 + ".16k.wav"):
            if os.path.exists(p):
                os.remove(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--riwaya", default="qalun")
    ap.add_argument("--out", required=True)
    ap.add_argument("--surahs", default=None)
    ap.add_argument("--audio-dir", default=os.path.join(_HERE, "work", "audio"))
    ap.add_argument("--order", choices=["desc", "asc"], default="desc",
                    help="desc: الأطول أولاً (خطر الشبكة) · "
                         "asc: الأقصر أولاً (تعظيم التغطية لكل ساعة — القيد المعالج)")
    args = ap.parse_args()

    ti = read_jz(args.index)
    idx = load_index()
    text = load_text(args.riwaya)
    starts = {s["n"]: s["start"] for s in idx["surahs"]}
    ayah_counts = {s["n"]: s["ayahs"] for s in idx["surahs"]}
    only = parse_range(args.surahs)
    os.makedirs(args.audio_dir, exist_ok=True)

    by_surah = {}
    for e in ti["entries"]:
        if e.get("confBand") != "HIGH" or e.get("startMs") is None:
            continue
        sn = int(e["ayahId"].split(":")[0])
        if only and sn not in only:
            continue
        by_surah.setdefault(sn, []).append(e)

    done = {}
    if os.path.exists(args.out):
        try:
            done = {e["ayahId"]: e for e in read_jz(args.out).get("entries", [])}
            print("استئناف: %d آية محفوظة سلفاً" % len(done), flush=True)
        except Exception:
            done = {}
    for sn in list(by_surah):
        if all(e["ayahId"] in done for e in by_surah[sn]):
            del by_surah[sn]

    out = list(done.values())
    stats = {"ayahs": 0, "withWords": 0, "words": 0, "dropped": {}}
    sign = -1 if args.order == "desc" else 1
    order = sorted(by_surah, key=lambda n: sign * ayah_counts.get(n, 0))
    print("سور للمعالجة: %d · الترتيب %s · الأوائل: %s"
          % (len(order), args.order, order[:5]), flush=True)

    failed = []
    for sn in order:
        try:
            process_surah(sn, args, by_surah[sn], text, starts, out, stats)
        except IOError as ex:
            print("⚠️ سورة %d تعذّرت (%s) — تُلحق آخراً" % (sn, ex), flush=True)
            failed.append(sn)
            continue
        write_doc(args, ti, out)
        print("  💾 نقطة حفظ: %d آية" % len(out), flush=True)
    if failed:
        print("\n=== إعادة محاولة %d سورة ===" % len(failed), flush=True)
        still = []
        for sn in failed:
            try:
                process_surah(sn, args, by_surah[sn], text, starts, out, stats)
                write_doc(args, ti, out)
            except IOError:
                still.append(sn)
        if still:
            print("⛔ بقيت متعذّرة: %s" % still, flush=True)

    write_doc(args, ti, out)
    print("\nالمخرج: %d آية · %d كلمة جديدة ← %s" % (len(out), stats["words"], args.out))
    print("ساقطة: %s · الحجم: %d ك.ب" % (stats["dropped"],
                                          os.path.getsize(args.out) // 1024))


if __name__ == "__main__":
    main()
