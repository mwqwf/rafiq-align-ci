# -*- coding: utf-8 -*-
"""ممرّ «قصّ البسملة»: كشفٌ ثم قصٌّ — ولا يقصّ إلا ببرهانٍ كلمي.

> ⛔ **نتيجة الميدان (‏2026-09-02): الفرضية منفيّة — لا تُشغّل هذه الأداة للقصّ.**
> مسبارٌ كلمي على **35 سورة مرشّحة من خمسة قرّاء** وجد **صفر بسملة**: ما سُمع في
> مطلع كل واحدة هو نصّ الآية نفسه (‏س4 «يا ايها الناس اتقوا…» · س63 «اذا جاك
> المنافقون…»). ⇒ **عزل البسملة في الممرّ الإنتاجي يعمل.**
> **وعلّة الترشيح الكاذب في المقياس نفسه:** قِيست **مدّة** الآية الأولى
> (`endMs − startMs`) ونُسب فائضها إلى البداية — **والفائض في النهاية** (صمتٌ
> أو ذيلٌ حتى الآية التالية). **قياسُ عَرَضٍ في طرفٍ لا يشهد على علّةٍ في الطرف
> الآخر.**
> **وشهادةٌ عرضية:** طوابع `wordtimings_*` لا تصلح شاهداً هنا — أول كلمةٍ فيها
> تبدأ **عند `startMs` بالضبط** (فجوة صفر) لأنها مشتقّةٌ من الفهرس لا مستقلّة
> عنه. فالمسبار الصوتي (`basmala_probe.py`) وحده يشهد.

**المشكلة:** في السور غير الفاتحة والتوبة تُتلى البسملة قبل الآية الأولى. فإن
لم تُعزَل، ابتلعتها الآية الأولى ⇒ بدايتها **أبكر من موضعها**، فيسمع المستخدم
بسملةً حين يطلب الآية، ويُظلَّل النص قبل أوانه.

**مبدأ الأداة:** القصّ يحتاج **موضع نهاية آخر كلمة من البسملة**، وهو لا يُعرف
إلا بطوابع كلمية. فإن توفّرت ⇒ **قصٌّ ببرهان**. وإن لم تتوفّر ⇒ **كشفٌ فقط**:
تُرشَّح السور التي تبدو آيتها الأولى منتفخة بمقدار بسملة (بمقارنة مدّتها
بمعدّل م.ث/كلمة عند القارئ نفسه)، **ولا يُكتب رقمٌ مخمَّن في فهرس**.

⛔ لا تكتب فوق الأصل، ولا تلمس الفاتحة (‏1) ولا التوبة (‏9).

    python tools/tasmi_bench/basmala_trim.py --index a.jz --surah-json DIR --dry-run
    python tools/tasmi_bench/basmala_trim.py --index a.jz --words w.jz --out b.jz
"""
import argparse
import collections
import glob
import hashlib
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from common import load_index, load_text, norm, read_jz, write_jz  # noqa: E402

BASMALA = norm("بسم الله الرحمن الرحيم").split()      # أربع كلمات
SKIP = {1, 9}                                          # الفاتحة والتوبة
# ⛔ الفواتح المقطّعة تُستبعد من الترشيح: ﴿كهيعص﴾ «كلمةٌ» واحدة تُتلى في ثوانٍ،
# فنموذج «م.ث لكل كلمة» يراها منتفخة دائماً. (وقع فعلاً: 10 من 29 مرشّحاً عند
# hawashi و10 من 15 عند koshi كانت فواتح لا بسملة.)
MUQATTAAT = {2, 3, 7, 10, 11, 12, 13, 14, 15, 19, 20, 26, 27, 28, 29, 30, 31, 32,
             36, 38, 40, 41, 42, 43, 44, 45, 46, 50, 68}
EXCESS_RATIO = 0.6      # تُرشَّح السورة إن تجاوز الفائض 60% من مدّة بسملةٍ متوقّعة


def rate_ms_per_word(entries, words_of):
    """معدّل م.ث/كلمة عند هذا القارئ — من الآيات الوسطى وحدها (تُستبعد الأولى
    من كل سورة لأنها المشتبهة، والقصيرة جداً لأن نسبتها مضطربة)."""
    vals = []
    for e in entries:
        s, a = (int(x) for x in e["ayahId"].split(":"))
        if a == 1 or e.get("startMs") is None or e.get("endMs") is None:
            continue
        w = words_of(s, a)
        d = e["endMs"] - e["startMs"]
        if w >= 4 and 500 < d < 120_000:
            vals.append(d / w)
    return statistics.median(vals) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--riwaya", default=None, help="افتراضه من ترويسة الفهرس")
    ap.add_argument("--words", help="فهرس توقيتات كلمية (يفتح القصّ بالبرهان)")
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ti = read_jz(args.index)
    riwaya = args.riwaya or ti.get("riwaya", "hafs")
    text = load_text(riwaya)
    idx = load_index()
    start_of = {s["n"]: s["start"] for s in idx["surahs"]}

    def words_of(s, a):
        return len(text[start_of[s] + a - 1].split())

    rate = rate_ms_per_word(ti["entries"], words_of)
    if rate is None:
        sys.exit("⛔ تعذّر حساب معدّل القارئ — فهرسٌ فارغ؟")
    basmala_ms = rate * len(BASMALA)
    first = {int(e["ayahId"].split(":")[0]): e for e in ti["entries"]
             if e["ayahId"].endswith(":1")}

    flagged, ok = [], 0
    for s, e in sorted(first.items()):
        if s in SKIP or e.get("startMs") is None or e.get("endMs") is None:
            continue
        if s in MUQATTAAT:                 # فواتح: النموذج لا يصلح لها
            continue
        dur = e["endMs"] - e["startMs"]
        expected = words_of(s, 1) * rate
        excess = dur - expected
        if excess >= EXCESS_RATIO * basmala_ms:
            flagged.append((s, round(dur / 1000, 1), round(expected / 1000, 1),
                            round(excess / 1000, 1)))
        else:
            ok += 1

    print(f"القارئ: {ti.get('reciterId','?')} · رواية {riwaya} · معدّل {rate:.0f}م.ث/كلمة "
          f"· بسملة متوقّعة ≈{basmala_ms/1000:.1f}ث")
    print(f"سور فُحصت: {len(flagged)+ok} · **مرشّحة لابتلاع البسملة: {len(flagged)}** "
          f"({len(flagged)/max(1,len(flagged)+ok)*100:.0f}%)")
    for s, d, x, ex in flagged[:12]:
        print(f"   سورة {s:3d}: الآية 1 مدّتها {d}ث · المتوقَّع {x}ث · **فائض {ex}ث**")
    if len(flagged) > 12:
        print(f"   … و{len(flagged)-12} غيرها")

    if not args.words:
        print("\n⚠️ **كشفٌ لا قصّ**: لا طوابع كلمية ⇒ لا يُعرف أين تنتهي البسملة "
              "بالضبط. القصّ بالتقدير يزيح الحدّ بلا برهان، فيُترك.")
        return
    wt = read_jz(args.words)
    by_ayah = {w["ayahId"]: w for w in wt.get("entries", [])}
    trimmed = 0
    for s, e in sorted(first.items()):
        if s in SKIP:
            continue
        w = by_ayah.get(f"{s}:1")
        if not w or not w.get("words"):
            continue
        # آخر كلمةٍ من البسملة داخل مدى الآية الأولى: أول أربع كلمات إن طابقت
        ws = w["words"]
        if len(ws) <= len(BASMALA):
            continue
        cut = ws[len(BASMALA) - 1].get("endMs")
        if cut and e["startMs"] < cut < e["endMs"]:
            e["startMs"] = int(cut)
            e["basmalaTrimmed"] = True
            trimmed += 1
    print(f"\n✂️ قُصَّت بالبرهان الكلمي: **{trimmed}** سورة")
    if args.dry_run or not args.out:
        print("(تجربة جافّة — لم يُكتب شيء)" if args.dry_run else
              "⛔ حدّد `--out`: لا يُكتب فوق الأصل بحال")
        return
    ti["basmalaTrim"] = {"tool": "basmala_trim.py", "at": int(time.time()),
                         "trimmed": trimmed, "flagged": len(flagged),
                         "sourceIndex": os.path.basename(args.index)}
    write_jz(args.out, ti)
    print(f"✅ {args.out} · sha256 "
          f"{hashlib.sha256(open(args.out,'rb').read()).hexdigest()[:16]}…")


if __name__ == "__main__":
    main()
