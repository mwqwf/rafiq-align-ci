#!/usr/bin/env python3
"""🔬 تفتيشُ وسمِ مجموعةِ المتعلّمين قبل أن يُقاس بها المحرّك ([[D-722]] · القاعدةُ الثالثة في أمر 2026-09-20).

المجموعةُ تدّعي دعويَين: أنّ `surah`/`ayah` موضعُ التسجيل، وأنّ مفتاحَ `errors` كلمةٌ منه. وكلتاهما
تُختبر ولا تُصدَّق.

**وقاعدتان تعلّمناهما بالقياس هنا:**
1. ⛔ **الآيةُ تُثبَّت بنصّها لا برقمها.** ترقيمُ المجموعة **مدنيٌّ في مواضع** (سورةُ الفاتحة والنازعات
   مزاحتان ‎+1 في قالون) — فمن وثق بالرقم قاس تلاوةً على نصِّ آيةٍ أخرى. هنا يُبحث عن الآية التي
   **يطابق نصُّها نصَّ الصفّ** في مدى ‎±2، وتُعلَن الإزاحةُ المستعملة.
2. ⛔ **المطابقةُ بهيكلِ الحروف لا بالرسم.** صفوفُ حفصٍ مكتوبةٌ **إملائيّاً** ومصحفُنا **عثمانيّ**
   (‏«قران»/«قرءان» · «امنوا»/«ءامنوا» · «ذلك»/«ذالك» · «اله»/«الاه»)، فالمطابقةُ الحرفيّةُ تردّ
   **104 صفوفٍ سليمة**. فيُقارَن هيكلٌ تُطرح منه الألفُ والهمزةُ وتُوحَّد الياءُ والهاء.

    python learner_check.py --rows work/learner_rows.jsonl --out work/learner_check.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zlib
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                        # noqa: BLE001
        pass

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                      "core", "quran", "src", "main", "assets", "quran")
COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6]
OFFS = [0]
for _c in COUNTS:
    OFFS.append(OFFS[-1] + _c)

RIWAYA = {"hafs": "hafs", "qaloon": "qalun", "qalun": "qalun", "warsh": "warsh",
          "shuba": "shuba", "douri": "douri", "duri": "douri", "sousi": "sousi", "susi": "sousi"}
PROLOGUE_SKEL = None            # يُحسب بعد تعريف skeleton


def strip_marks(w: str) -> str:
    """تجريدُ الحركاتِ وعلاماتِ الضبط فقط — يبقى الرسمُ كما هو."""
    return "".join(c for c in w
                   if not (0x64B <= ord(c) <= 0x65F or ord(c) == 0x670
                           or 0x6D6 <= ord(c) <= 0x6ED or c == "ـ"))


def skeleton(w: str) -> str:
    """هيكلُ الحروف: تُطرح الألفُ والهمزةُ بكلّ صورها، وتُوحَّد الياءُ والواوُ الصغيرتان والتاءُ المربوطة.

    ⛔ تساهلٌ في **الرسم** لا في **الكلمة**: «قران» و«قرءان» هيكلُهما واحد، و«الناس» و«الخناس» لا.
    """
    out = []
    for c in strip_marks(w):
        if c in "اءأإآؤئٱ":
            continue                          # ألفٌ وهمزةٌ بكلّ صورها
        if c in ("ى", "ے"):
            c = "ي"
        if c == "ة":
            c = "ه"
        if c in ("ۥ", "ۦ"):
            continue                          # واوٌ وياءٌ صغيرتان
        out.append(c)
    return "".join(out)


PROLOGUE_SKEL = {skeleton(w) for w in
                 ("أعوذ", "بالله", "من", "الشيطان", "الرجيم", "بسم", "الله", "الرحمن", "الرحيم")}


def load_text(riwaya: str):
    return json.loads(zlib.decompress(open(os.path.join(ASSETS, f"text_{riwaya}.jz"), "rb").read(), 47))


def seq(t: str) -> str:
    return " ".join(skeleton(w) for w in t.split() if skeleton(w))


def anchor(texts, riwaya: str, surah: int, ayah: int, text: str, span: int = 2):
    """الفهرسُ المسطّحُ للآية التي **يطابق نصُّها** نصَّ الصفّ — وإزاحتُها عن الرقم المذكور."""
    want = seq(text)
    if not want:
        return None, None
    for off in (0, 1, -1, 2, -2)[: 1 + 2 * span]:
        k = ayah - 1 + off
        if 0 <= k < COUNTS[surah - 1] and seq(texts[riwaya][OFFS[surah - 1] + k]) == want:
            return OFFS[surah - 1] + k, off
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default="tools/tasmi_phoneme/work/learner_rows.jsonl")
    ap.add_argument("--out", default="tools/tasmi_phoneme/work/learner_check.json")
    a = ap.parse_args()

    texts = {}
    rowstat, labstat, shifts, per_riwaya = Counter(), Counter(), Counter(), Counter()
    unmatched, usable, anchored = [], [], []
    total = 0

    for line in open(a.rows, encoding="utf-8"):
        x = json.loads(line)
        total += 1
        r = RIWAYA.get((x.get("riwayah") or "").strip().lower())
        try:
            s, ay = int(x.get("surah")), int(x.get("ayah"))
        except (TypeError, ValueError):
            rowstat["موضعٌ غيرُ مقروء"] += 1
            continue
        if not r:
            rowstat["روايةٌ مجهولة"] += 1
            continue
        if ay == 0:
            rowstat["آيةٌ 0 (بسملةٌ مستقلّة)"] += 1
            continue
        if not (1 <= s <= 114 and 1 <= ay <= COUNTS[s - 1]):
            rowstat["موضعٌ خارجَ المصحف"] += 1
            continue
        if r not in texts:
            texts[r] = load_text(r)
        flat, off = anchor(texts, r, s, ay, x.get("text") or "")
        if flat is None:
            rowstat["نصُّ الصفّ لا يطابق أيّ آيةٍ في ±2"] += 1
            continue
        rowstat["مثبَّتٌ بنصّه"] += 1
        shifts[off] += 1

        errs = {w: v for w, v in (x.get("errors") or {}).items() if v}
        rid = (x.get("reviewer_id") or "").strip()
        if rid in ("", "not reviewed"):
            continue
        rowstat["مثبَّتٌ ومراجَعٌ بشريّاً"] += 1
        if not errs:
            rowstat["مراجَعٌ بلا خطأ (سالبٌ موثوق)"] += 1
            anchored.append({"recording_id": x.get("recording_id"), "riwaya": r, "flat": flat,
                             "ref": f"{s}:{ay}", "shift": off, "reviewer": rid,
                             "kind": "سالب", "errors": []})
            continue
        words = {skeleton(w) for w in texts[r][flat].split()}
        hits = []
        for w, tags in errs.items():
            n = skeleton(w)
            if n in words:
                labstat["مطابقةٌ في الآية"] += 1
                per_riwaya[r] += 1
                hits.append({"word": w, "tags": tags})
            elif n in PROLOGUE_SKEL:
                labstat["مطابقةٌ في المقدّمة"] += 1
            else:
                labstat["لا مطابقة"] += 1
                if len(unmatched) < 20:
                    unmatched.append({"riwaya": r, "ref": f"{s}:{ay}", "word": w})
        if hits:
            row = {"recording_id": x.get("recording_id"), "riwaya": r, "flat": flat,
                   "ref": f"{s}:{ay}", "shift": off, "reviewer": rid,
                   "kind": "موجب", "errors": hits}
            usable.append(row)
            anchored.append(row)

    lt = sum(labstat.values())
    rate = 100.0 * labstat["مطابقةٌ في الآية"] / max(1, lt)
    res = {"rows_total": total, "rows": dict(rowstat), "anchor_shifts": {str(k): v for k, v in shifts.items()},
           "labels": dict(labstat), "in_ayah_pct": round(rate, 1),
           "in_ayah_by_riwaya": dict(per_riwaya),
           "usable_rows": len(usable), "usable": usable, "anchored": anchored, "unmatched_samples": unmatched}
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"صفوفٌ: {total}")
    for k, v in rowstat.most_common():
        print(f"  {k}: {v}")
    print(f"إزاحاتُ التثبيت (رقمُهم ⇐ رقمُنا): {dict(shifts)}")
    print(f"وسومٌ: {dict(labstat)} · نملك موضعَ **{rate:.1f}٪** منها · بحسب الرواية {dict(per_riwaya)}")
    print(f"**صفوفٌ صالحةٌ لقياس الكشف: {len(usable)}** · وسالبٌ موثوق: {rowstat['مراجَعٌ بلا خطأ (سالبٌ موثوق)']}")
    ok = rate >= 90
    print("✅ الوسمُ يُطابق نصَّنا ⇒ يصلح مسطرةً" if ok else "⛔ لا يصلح — يُفتّش قبل أيّ قياس")
    if unmatched:
        print("عيّناتٌ لا تُطابق:", json.dumps(unmatched[:6], ensure_ascii=False))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
