# -*- coding: utf-8 -*-
"""تحقق المخرج الكلمي من انحرافه عن فهرس الآيات النهائي — وإعادة توليد المختلف.

**لماذا:** الفهرس قد يُعاد توليده **تحت** المخرج أثناء العمل (حدث فعلاً ليلة
2026-09-01: 4018 ← 4217 حداً HIGH بعد دمج الصقل في الإنتاج). فالآيات التي وُلِّدت
على حدود قديمة تحمل توقيتات كلمية مبنية على مدى لم يعد قائماً — **عطب صامت**:
الملف سليم البنية، والأرقام داخل مدى خاطئ.

يقارن كل آية في المخرج بحدودها في الفهرس الحالي، ويصنّفها:
  · `ok`        — الحدود لم تتغير (أو ضمن التسامح).
  · `shifted`   — تغيّرت ⇒ **يُعاد توليدها** (الكاش يجعلها رخيصة إن لم يتغير الصوت).
  · `dropped`   — لم تعد HIGH في الفهرس ⇒ تُحذف من المخرج (لا نشحن ما لا نضمنه).
  · `missing`   — HIGH في الفهرس بلا توقيت كلمي ⇒ تُضاف للطابور.

python verify_against_index.py --index <idx.jz> --out <wordtimings.jz> [--apply]
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _V2)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import load_index, load_text, read_jz  # noqa: E402

import build_index as B  # noqa: E402

TOL_MS = 50          # فارق أصغر منه لا أثر له على توقيت كلمي


def classify(index_path, out_path):
    ti = read_jz(index_path)
    doc = read_jz(out_path)
    cur = {e["ayahId"]: e for e in ti["entries"]
           if e.get("confBand") == "HIGH" and e.get("startMs") is not None}
    have = {e["ayahId"]: e for e in doc["entries"]}
    ok, shifted, dropped, missing = [], [], [], []
    for aid, e in have.items():
        c = cur.get(aid)
        if not c:
            dropped.append(aid)
            continue
        w = e["words"]
        # الكلمة الأولى تبدأ من بدء الكلام المقيس (VAD) لا من حدّ الآية (وسيط +180م.ث)،
        # فالشرط عليها «لا تسبق الحدّ» فقط؛ أما النهاية فمساواة تامة (cuts[-1] = end_ms).
        if w[0]["startMs"] < c["startMs"] or            abs(w[-1]["endMs"] - c["endMs"]) > TOL_MS:
            shifted.append(aid)
        else:
            ok.append(aid)
    for aid in cur:
        if aid not in have:
            missing.append(aid)
    return ti, doc, cur, ok, shifted, dropped, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="نفّذ: احذف الساقط وأعد توليد المنزاح")
    ap.add_argument("--riwaya", default="qalun")
    ap.add_argument("--audio-dir", default=os.path.join(_HERE, "work", "audio"))
    args = ap.parse_args()

    ti, doc, cur, ok, shifted, dropped, missing = classify(args.index, args.out)
    print("المخرج: %d آية · الفهرس HIGH: %d" % (len(doc["entries"]), len(cur)))
    print("  ✅ مطابق: %d" % len(ok))
    print("  ↔️ منزاح (يُعاد توليده): %d %s" % (len(shifted), shifted[:8]))
    print("  🗑️ لم يعد HIGH (يُحذف): %d %s" % (len(dropped), dropped[:8]))
    print("  ➕ ناقص (يُضاف للطابور): %d" % len(missing))
    fp = doc.get("generatedAgainst")
    if fp:
        print("  بُني على: %s (HIGH=%s)" % (fp.get("file"), fp.get("highCount")))
    if not args.apply:
        print("\n(معاينة فقط — أضف --apply للتنفيذ)")
        return

    keep = [e for e in doc["entries"]
            if e["ayahId"] not in dropped and e["ayahId"] not in shifted]
    if len(keep) != len(doc["entries"]):
        print("حُذف %d مدخلاً (ساقط أو منزاح)" % (len(doc["entries"]) - len(keep)))
    doc["entries"] = keep
    B.write_doc(args, ti, keep)
    print("كُتب المخرج المنقّى: %d آية. أعد تشغيل build_index لاستكمال "
          "المنزاح والناقص (%d آية)." % (len(keep), len(shifted) + len(missing)))


if __name__ == "__main__":
    main()
