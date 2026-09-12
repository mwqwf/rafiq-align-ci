# -*- coding: utf-8 -*-
"""🧾 **تصديقُ مرآة الحاكم على مخرَج المحرك الحقيقيّ** — لا على مدخلاتٍ مصنوعة.

كلُّ رقمٍ في `docs/qa/TASMI_SCOREBOARD.md` يُحكم به على نموذجٍ أو مفتاحٍ **يمرّ بمرآةٍ بايثونية**
(`scorer.py`) تحاكي `RecitationScorer` في المحرك. ويحرسها `RecitationScorerParityTest` — لكنّه
يُقاس على **مدخلاتٍ مصنوعة**. وحين صار مسبارُ `whisperBatch` يُخرج سطرَ `RafiqJudge` (أحكامَ
الحاكم الحقيقيّ لكلّ كلمة) صار بالإمكان تصديقُها على **200 بندٍ حقيقيٍّ من مخرَج المحرك نفسِه**.

    python tools/tasmi_bench/judge_parity.py --set g1 --arm shipped

⛔ **وأيُّ انحرافٍ هنا أخطرُ من أيِّ رقمٍ في اللوحة**: يعني أنّ ما نقيسه ليس ما يحكم به التطبيق.
صيغةُ السطر (جلسةُ التطبيق): `<file>\tflat=<n>\t<C,M,…>\tadditions=<k>\tcritical=<bool>`
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score  # noqa: E402
import scorer  # noqa: E402
import v2_gate as G  # noqa: E402

# حرفُ الحكم في سطر المحرك ⇒ اسمُ الحكم في المرآة
LETTER = {"C": "CORRECT", "M": "MISSED", "S": "SUBSTITUTED", "U": "UNCERTAIN"}


def parse_judge(line):
    """يعيد (أحكامٌ كقائمةِ حروف، زيادات، حرجٌ، روايةُ المحرك) من سطر `RafiqJudge`."""
    verdicts, adds, crit, rw = [], None, None, None
    for part in line.split("\t"):
        part = part.strip()
        if part.startswith("flat="):
            continue
        if part.startswith("riwaya="):
            # ⚠️ الحاكمُ يتصرّف بحسب `RiwayaProfile` (النقلُ لورشٍ · الصلةُ لورشٍ وقالون) ⇒ خلافُ إعدادٍ
            # يظهر كخلافِ حكمٍ لو لم يُقارَن. والمصدرُ عندنا واحدٌ (بادئةُ اسم الملفّ) فالتطابقُ متوقَّع.
            rw = part.split("=", 1)[1]
            continue
        if part.startswith("additions="):
            try:
                adds = int(part.split("=", 1)[1])
            except ValueError:
                pass
        elif part.startswith("critical="):
            crit = part.split("=", 1)[1].lower() == "true"
        elif part and all(c in "CMSU," for c in part):
            verdicts = [c for c in part.split(",") if c]
    return verdicts, adds, crit, rw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="g1")
    ap.add_argument("--arm", default="shipped")
    ap.add_argument("--pattern", default="work/hyps_emu_{tag}_cap_{arm}.json")
    ap.add_argument("--cfg", default="proposed")
    a = ap.parse_args()
    G.PATTERN = a.pattern
    G.CMP = (a.arm, a.arm)
    h = G.load_hyps(a.set, a.arm)
    with_judge = {k: v for k, v in h.items() if v.get("judge")}
    if not with_judge:
        sys.exit(f"⛔ لا سطرَ `RafiqJudge` في {a.set}/{a.arm} — يلزم APK يُخرجه (م٢-٥)")
    sample = score.load_sample()
    items = [it for it in sample["items"] if it["id"] in with_judge]
    res = score.run(items, h, a.cfg)

    words = agree = 0
    rw_diff = []
    conf = collections.Counter()          # (محرك، مرآة)
    bad_items, add_diff = [], []
    for r, it in zip(res, items):
        if not r["ok"]:
            continue
        eng, adds, _, rw = parse_judge(with_judge[it["id"]]["judge"])
        if rw and rw != it["riwaya"]:
            rw_diff.append((it["id"], rw, it["riwaya"]))
        mir = [w[1] for w in r["words"]]
        if len(eng) != len(mir):          # طولٌ مختلفٌ = خللٌ بنيويّ لا خلافُ حكم
            bad_items.append((it["id"], f"طولٌ مختلف: محرك {len(eng)} · مرآة {len(mir)}"))
            continue
        for e, m in zip(eng, mir):
            words += 1
            em = LETTER.get(e, e)
            conf[(em, m)] += 1
            if em == m:
                agree += 1
        if adds is not None and adds != len(r["additions"]):
            add_diff.append((it["id"], adds, len(r["additions"])))

    print(f"## 🧾 تصديقُ المرآة على المحرك — {a.set} · ذراع {a.arm}\n")
    print(f"بنودٌ بأحكامٍ من المحرك: **{len(with_judge)}** · كلماتٌ مقارَنة: **{words}**")
    print(f"**اتّفاقُ الحكم كلمةً بكلمة: {agree}/{words} = {agree/max(words,1)*100:.3f}٪**")
    if bad_items:
        print(f"\n⛔ بنودٌ بطولٍ مختلف ({len(bad_items)}):")
        for i, why in bad_items[:6]:
            print(f"  {i}: {why}")
    dis = {k: v for k, v in conf.items() if k[0] != k[1]}
    if dis:
        print("\nمواضعُ الخلاف (محرك ⇒ مرآة):")
        for (e, m), n in sorted(dis.items(), key=lambda kv: -kv[1]):
            print(f"  {n:4d}  {e} ⇒ {m}")
    if rw_diff:
        print(f"\n⛔ خلافٌ في الرواية ({len(rw_diff)} بنداً) — الحاكمان بإعدادَين مختلفَين فالمقارنةُ باطلة:")
        for i, e, m in rw_diff[:6]:
            print(f"  {i}: محرك {e} · عيّنة {m}")
    if add_diff:
        print(f"\n⚠️ خلافٌ في عدد الزيادات ({len(add_diff)} بنداً):")
        for i, e, m in add_diff[:6]:
            print(f"  {i}: محرك {e} · مرآة {m}")
    if not dis and not bad_items and not add_diff and not rw_diff:
        print("\n✅ **صفرُ انحراف** — المرآةُ تحكم كما يحكم المحرك على هذه البنود.")


if __name__ == "__main__":
    main()
