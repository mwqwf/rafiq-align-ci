#!/usr/bin/env python3
"""♻️ **إصلاحُ `audit.json` بصور الحاكم بلا إعادة تشغيل whisper** (‏D-292).

`label_audit.py` كان يحسب `match` بتساوٍ صارم مع صورةٍ **واحدة** للكلمة، والحاكمُ المشحون يقبل
صوراً أخرى أُضيفت لأنّ whisper يكتبها ⇒ عتبةُ `--min-match` كانت تُسقط مقاطعَ سليمةً، وبنسبٍ
غيرِ متساوية بين الروايات. أُصلح المدقِّق؛ لكنّ `audit.json` المرفوعَ إلى R2 كُتب بالصارم،
وإعادةُ توليده تكلّف شوطَ whisper كاملاً على المجموعة (ساعاتُ معالجٍ على أربع مهامّ).

ولا حاجة: المقطعُ آيةٌ كاملة، واسمُ ملفّه هو رقمُها (`2_255.flac` ⇐ 2:255 — `prep.py`)، فالنصُّ
المشكولُ الأصليُّ يُستعاد من المصحف يقيناً، وتُعاد المطابقةُ على `hyp` المحفوظ. لا صوتَ ولا نموذج.

    python tools/finetune/audit_rescore.py g0.audit.json [g1.audit.json ...] [--min-match 0.85] [--in-place]

يطبع لكلِّ ملفّ: المتوسّطَ قبل/بعد، وكم مقطعاً كانت العتبةُ تُسقطه **بالمِسطرة لا بالضجيج**،
مفصَّلاً بالرواية. و`--in-place` يكتب `match` المصحَّح (ويحفظ القديم في `match_strict`).
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tasmi_bench"))
sys.path.insert(0, os.path.join(HERE, "..", "alignment"))
import scorer                                    # noqa: E402
from common import load_text                     # noqa: E402

sys.path.insert(0, HERE)
from label_audit import norm, align, ref_forms   # noqa: E402  المدقِّقُ نفسُه (لا نسخةَ ثانية)

COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,227,93,88,69,60,
          34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,
          12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,
          3,9,5,4,7,3,6,3,5,4,5,6]
OFFS = [0]
for c in COUNTS: OFFS.append(OFFS[-1] + c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--min-match", type=float, default=0.85)
    ap.add_argument("--in-place", action="store_true")
    a = ap.parse_args()
    texts = {rw: load_text(rw) for rw in ("hafs", "qalun", "warsh")}
    for path in a.files:
        j = json.load(open(path, encoding="utf-8"))
        items = j["items"]
        by = {}
        miss_key = 0
        for it in items:
            rw = it["riwaya"]
            stem = os.path.splitext(it["id"])[0]
            try:
                s, v = map(int, stem.split("_")[:2])
                ref_text = texts[rw][OFFS[s - 1] + v - 1]
            except Exception:
                miss_key += 1
                continue
            forms = ref_forms(ref_text, rw)
            hyp = it["hyp"].split()
            # حارسٌ: النصُّ المستعادُ يجب أن يطابق `ref` المحفوظ بالصورة الصارمة، وإلا فالمقطعُ ليس آيتَه
            if " ".join(norm(ref_text)) != it["ref"]:
                miss_key += 1
                continue
            ok = align(forms, hyp)[0]
            it["match_strict"] = it.get("match_strict", it["match"])
            it["match"] = ok / max(len(forms), 1)
            b = by.setdefault(rw, [0, 0.0, 0.0, 0, 0])
            b[0] += 1; b[1] += it["match_strict"]; b[2] += it["match"]
            b[3] += it["match_strict"] < a.min_match
            b[4] += it["match"] < a.min_match
        print(f"\n📄 {os.path.basename(path)} · {len(items)} مقطعاً"
              + (f" · ⚠ تعذّر ربطُ {miss_key}" if miss_key else ""))
        print(f"   {'الرواية':8} {'ن':>6} {'متوسّطٌ صارم':>12} {'بصور الحاكم':>12} "
              f"{'يسقط صارماً':>12} {'يسقط بعدُ':>10} {'أُنقذ':>7}")
        tot = [0, 0, 0]
        for rw, (n, ss, sj, ds, dj) in sorted(by.items()):
            print(f"   {rw:8} {n:6d} {ss/n:12.4f} {sj/n:12.4f} "
                  f"{ds:7d} ({100*ds/n:4.1f}٪) {dj:5d} ({100*dj/n:4.1f}٪) {ds-dj:7d}")
            tot[0] += n; tot[1] += ds; tot[2] += dj
        if tot[0]:
            print(f"   {'الكلّ':8} {tot[0]:6d} {'':12} {'':12} "
                  f"{tot[1]:7d} ({100*tot[1]/tot[0]:4.1f}٪) {tot[2]:5d} ({100*tot[2]/tot[0]:4.1f}٪) {tot[1]-tot[2]:7d}")
        if a.in_place:
            m = [it["match"] for it in items if "match_strict" in it]
            if m:
                j["summary"]["mean"] = sum(m) / len(m)
                j["summary"]["below_0.85"] = sum(x < 0.85 for x in m) / len(m)
                j["summary"]["rescored_by"] = "audit_rescore.py (D-292)"
            json.dump(j, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"   ✍ كُتب في مكانه (‏`match` بصور الحاكم · `match_strict` القديم محفوظ)")


if __name__ == "__main__":
    main()
