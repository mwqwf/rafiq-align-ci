# -*- coding: utf-8 -*-
"""مواءمة مقاطع QUL الكلمية (حفص) مع التقطيع الموحّد — بيانات بحتة بلا صوت.

**المشكلة:** `segments_husary.jz` (وبه يظلّل التطبيق حفصاً اليوم) مبنيّ على تقطيع
`text_hafs.jz` القديم. وتوحيد النص على حزمة المجمع غيّر مواضع المسافات في **ست**
آيات (ثلاث انقسمت وثلاث اتصلت) — بلا تغيير حرف أو حركة (متحقَّق: سيل الحروف
مطابق 100% في الـ6236). فبمجرد شحن النص الموحّد يصير عدد الكلمات ≠ عدد المقاطع في
الست، **فينزاح التظليل في بقية الآية كلها** لأن الربط ترتيبي بالفهرس.

**العلاج:** قسمة المقطع المنقسم بنسبة حروف الكلمتين، ودمج المقطعين المتصلين
(الأول يبدأ والثاني ينتهي). لا صوت ولا whisper ولا إعادة محاذاة.

⛔ لا يُكتب داخل `core/quran/assets` — المخرج في `out/` وتسليمه لجلسة التطبيق.

python unify_segments.py --report | --apply
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
_ROOT = os.path.dirname(os.path.dirname(_V2))
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import QURAN_ASSETS, load_index, read_jz, write_jz  # noqa: E402

UNIFIED = os.path.join(_ROOT, "tools", "quraat", "out", "text_hafs_unified.jz")
SRC = os.path.join(QURAN_ASSETS, "segments_husary.jz")
OUT = os.path.join(_V2, "out", "segments_husary_unified.jz")


def bare(w):
    """سيل الحروف بلا مسافات (للمطابقة البنيوية فقط)."""
    return w.replace(" ", "")


def find_change(old_words, new_words):
    """يعيد (نوع، موضع): SPLIT عند i (old[i] = new[i]+new[i+1]) أو MERGE عند i."""
    n = min(len(old_words), len(new_words))
    for i in range(n):
        if old_words[i] == new_words[i]:
            continue
        if len(new_words) > len(old_words):
            if i + 1 < len(new_words) and \
               bare(new_words[i]) + bare(new_words[i + 1]) == bare(old_words[i]):
                return "SPLIT", i
        else:
            if i + 1 < len(old_words) and \
               bare(old_words[i]) + bare(old_words[i + 1]) == bare(new_words[i]):
                return "MERGE", i
        return "UNKNOWN", i
    # الاختلاف في الذيل
    return ("SPLIT" if len(new_words) > len(old_words) else "MERGE"), n - 1


def split_segment(seg, w1, w2):
    """يقسم [بداية، نهاية] إلى مقطعين بنسبة حروف الكلمتين."""
    s, e = seg
    n1, n2 = max(len(bare(w1)), 1), max(len(bare(w2)), 1)
    cut = int(s + (e - s) * n1 / float(n1 + n2))
    cut = max(s + 1, min(cut, e - 1))
    return [[s, cut], [cut, e]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    old_text = read_jz(os.path.join(QURAN_ASSETS, "text_hafs.jz"))
    new_text = read_jz(UNIFIED)
    seg = read_jz(SRC)
    idx = load_index()

    def aid(i):
        for s in idx["surahs"]:
            if s["start"] <= i < s["start"] + s["ayahs"]:
                return "%d:%d" % (s["n"], i - s["start"] + 1)
        return "?"

    # ⛔ حارس: سيل الحروف يجب ألا يتغير في أي آية
    drift = [i for i in range(len(old_text))
             if bare(old_text[i]) != bare(new_text[i])]
    if drift:
        print("⛔ سيل الحروف تغيّر في %d آية — توقّف: %s"
              % (len(drift), [aid(i) for i in drift[:5]]))
        return

    changes, out = [], dict(seg)
    for i in range(len(old_text)):
        ow, nw = old_text[i].split(), new_text[i].split()
        if len(ow) == len(nw):
            continue
        kind, pos = find_change(ow, nw)
        g = seg.get(str(i))
        rec = {"ayah": aid(i), "gidx": i, "kind": kind, "pos": pos,
               "old": len(ow), "new": len(nw),
               "segBefore": len(g) if g else None}
        if g is None:
            rec["note"] = "لا مقاطع لهذه الآية في QUL"
            changes.append(rec)
            continue
        if kind == "UNKNOWN":
            rec["note"] = "⛔ نمط غير معروف — لم يُعدَّل"
            changes.append(rec)
            continue
        segs = [list(x) for x in g]
        if kind == "SPLIT":
            segs = segs[:pos] + split_segment(segs[pos], nw[pos], nw[pos + 1]) \
                + segs[pos + 1:]
        else:
            merged = [segs[pos][0], segs[pos + 1][1]]
            segs = segs[:pos] + [merged] + segs[pos + 2:]
        out[str(i)] = segs
        rec["segAfter"] = len(segs)
        rec["ok"] = len(segs) == len(nw)
        changes.append(rec)

    print("=== مواضع التغيّر (%d) ===" % len(changes))
    for c in changes:
        print("  %-8s %s pos=%d · كلمات %d→%d · مقاطع %s→%s %s"
              % (c["ayah"], c["kind"], c["pos"], c["old"], c["new"],
                 c.get("segBefore"), c.get("segAfter"), c.get("note", "")))

    # === شرط القبول: عدد المقاطع = عدد الكلمات في كل آية لها مقاطع ===
    mism, noseg = [], 0
    for i in range(len(new_text)):
        g = out.get(str(i))
        if g is None:
            noseg += 1
            continue
        if len(g) != len(new_text[i].split()):
            mism.append((aid(i), len(g), len(new_text[i].split())))
    print("\n=== شرط القبول على الـ6236 ===")
    print("  آيات بلا مقاطع في QUL أصلاً: %d" % noseg)
    print("  عدم تطابق مقاطع/كلمات: %d %s" % (len(mism), mism[:8]))

    # === سلامة الاتصال الزمني ===
    # ⚠️ الأصل نفسه فيه «تداخل» في 2763 آية من 6236 (44.3%) **قبل أي تعديل مني** —
    # فهو خاصية في بيانات QUL لا عطب أُحدثه، ولا يجوز أن يمنع الكتابة ولا أن
    # أصلحه (ليس نطاقي ولا أعرف نيّة مُنتِجه). فأقيس **ما أُحدثه أنا** فقط:
    # هل ساءت حال آية بسبب تعديلي؟
    def flaw(g):
        return (sum(1 for a, b in zip(g, g[1:]) if a[1] > b[0]),
                sum(1 for x in g if x[0] >= x[1]))

    worsened, edited = [], [c["gidx"] for c in changes if c.get("segAfter")]
    for i in edited:
        before, after = flaw(seg[str(i)]), flaw(out[str(i)])
        if after > before:
            worsened.append((aid(i), before, after))
    pre = sum(1 for k, g in seg.items() if flaw(g)[0] or flaw(g)[1])
    post = sum(1 for k, g in out.items() if flaw(g)[0] or flaw(g)[1])
    print("  خلل زمني قائم في الأصل (ليس مني): %d آية" % pre)
    print("  بعد التعديل: %d آية (الفارق %+d)" % (post, post - pre))
    print("  آيات ساءت **بسبب تعديلي**: %d %s" % (len(worsened), worsened))
    bad = worsened

    if args.apply and not mism and not bad:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        write_jz(OUT, out)
        print("\n✅ كُتب: %s (%d ك.ب)" % (OUT, os.path.getsize(OUT) // 1024))
    elif args.apply:
        print("\n⛔ لم يُكتب: شرط القبول غير مستوفٍ")


if __name__ == "__main__":
    main()
