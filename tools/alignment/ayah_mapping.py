# -*- coding: utf-8 -*-
"""جدول تعيين معتمد مدني↔كوفي للرواية — بمطابقة نصية مبرهنة لا اجتهاداً.

المصدر المدني: حزمة المجمع الرسمية (JSON بترقيم الرواية 6214).
المصدر الكوفي: نص التطبيق text_{riwaya}.jz (6236 slot موحد).
المنهج: لكل سورة نبني سيل كلمات الطرفين (بعد تطبيع rasm) — يجب أن يتطابقا حرفياً
(نفس مصحف المدينة) — ثم نسقط حدود المدني على مواضع الكوفي فينتج لكل آية مدنية
مداها الكوفي [بداية سورة:آية:كلمة ← نهاية]. أي عدم تطابق نصي = فشل صريح.

python ayah_mapping.py --riwaya qalun
المخرج: work/mapping_{riwaya}.json + ملخص أنواع التعيين.
"""
import argparse
import json
import os
import sys
import zipfile

from common import QURAN_ASSETS, load_index, load_text, norm, read_jz

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PKG = {
    "qalun": ("UthmanicQaloun_v2-1.zip", "UthmanicQaloun_v2-1 data/QalounData_v2-1.json"),
    "warsh": ("UthmanicWarsh_v2-1.zip", None),  # يُكتشف اسم json داخلياً
}
ARCHIVE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "QuranRafiq", "assets-archive", "qurancomplex")
# ملاحظة: common.ROOT هو جذر QuranRafiq — استعمله مباشرة
from common import ROOT
ARCHIVE = os.path.join(ROOT, "assets-archive", "qurancomplex")


def load_official(riwaya):
    zname, jpath = PKG[riwaya]
    z = zipfile.ZipFile(os.path.join(ARCHIVE, zname))
    if jpath is None:
        jpath = next(n for n in z.namelist() if n.lower().endswith(".json"))
    data = json.loads(z.read(jpath))
    # الحقول المتوقعة: id, jozz, sura_no, sura_name_ar,.., aya_no, aya_text
    by_surah = {}
    for row in data:
        sn = int(row.get("sura_no") or row.get("SuraNum") or row["sura"])
        an = int(row.get("aya_no") or row.get("AyaNum") or row["aya"])
        txt = row.get("aya_text") or row.get("AyaText") or row["text"]
        by_surah.setdefault(sn, []).append((an, txt))
    for sn in by_surah:
        by_surah[sn].sort()
    return by_surah


def map_riwaya(riwaya):
    official = load_official(riwaya)
    kufi_text = load_text(riwaya)
    index = load_index()
    mapping = {}
    stats = {"1to1": 0, "merge": 0, "split_part": 0, "surah_mismatch": []}
    for s in index["surahs"]:
        sn, start, count = s["n"], s["start"], s["ayahs"]
        kufi = [norm(kufi_text[start + i]).split() for i in range(count)]
        mad = [(an, norm(t).split()) for an, t in official.get(sn, [])]
        # آية المدني الأولى قد تشمل البسملة غير الموجودة في نص التطبيق (أو العكس) — قصّها إن زادت
        flat_k = [w for ws in kufi for w in ws]
        flat_m = [w for _, ws in mad for w in ws]
        if flat_m[:4] == ["بسم", "الله", "الرحمن", "الرحيم"] and flat_k[:4] != flat_m[:4] and sn != 1:
            mad[0] = (mad[0][0], mad[0][1][4:])
            flat_m = flat_m[4:]
        kufi_offset = 0
        if sn == 1 and flat_k[:4] == ["بسم", "الله", "الرحمن", "الرحيم"] and flat_m[0] == "الحمد":
            # الفاتحة: الكوفي يعدّ البسملة 1:1 والمدني لا يعدّها — نقصّها من الكوفي
            # ونزيح فهارسه؛ بسملة 1:1 الكوفية بلا نظير مدني (توثَّق في الميتا).
            kufi = kufi[1:]
            flat_k = flat_k[4:]
            kufi_offset = 1
        if flat_k != flat_m:
            # اعثر على أول اختلاف للتقرير
            i = next((i for i, (a, b) in enumerate(zip(flat_k, flat_m)) if a != b),
                     min(len(flat_k), len(flat_m)))
            stats["surah_mismatch"].append(
                (sn, i, flat_k[i:i+3], flat_m[i:i+3], len(flat_k), len(flat_m)))
            continue
        # حدود تراكمية بالكلمات
        kb, acc = [], 0
        for ws in kufi:
            kb.append((acc, acc + len(ws)))
            acc += len(ws)
        rows, acc = [], 0
        for an, ws in mad:
            m0, m1 = acc, acc + len(ws)
            acc = m1
            # الآيات الكوفية المتقاطعة مع [m0,m1)
            span = [i for i, (a, b) in enumerate(kb) if a < m1 and b > m0]
            row = {"madani": an,
                   "kufiFrom": span[0] + 1 + kufi_offset, "kufiTo": span[-1] + 1 + kufi_offset,
                   "exact": kb[span[0]][0] == m0 and kb[span[-1]][1] == m1}
            if not row["exact"]:
                row["wordFrom"] = m0 - kb[span[0]][0]
                row["wordTo"] = m1 - kb[span[-1]][0]
                stats["split_part"] += 1
            elif len(span) > 1:
                stats["merge"] += 1
            else:
                stats["1to1"] += 1
            rows.append(row)
        mapping[sn] = rows
    return mapping, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", required=True, choices=list(PKG))
    args = ap.parse_args()
    mapping, stats = map_riwaya(args.riwaya)
    total = sum(len(v) for v in mapping.values())
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work",
                       f"mapping_{args.riwaya}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"riwaya": args.riwaya, "source": PKG[args.riwaya][0],
                   "madaniTotal": total, "surahs": mapping}, f, ensure_ascii=False)
    print(f"آيات مدنية معينة: {total} (الهدف 6214)")
    print(f"‏1↔1: {stats['1to1']} · دمج كوفي: {stats['merge']} · قسمة جزئية: {stats['split_part']}")
    if stats["surah_mismatch"]:
        print(f"❌ سور لم يتطابق نصها ({len(stats['surah_mismatch'])}):")
        for m in stats["surah_mismatch"][:10]:
            print("  ", m)
    else:
        print("✅ تطابق نصي حرفي في السور كلها")
    print("كُتب:", out)


if __name__ == "__main__":
    main()
