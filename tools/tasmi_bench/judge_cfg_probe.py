# -*- coding: utf-8 -*-
"""⚖️ **أيُّ مسطرةٍ حكمت أرقامَ البوّابة؟ وهل في الاتّهام فضلةٌ تُنفَق على الكشف؟**

سؤالان يُجابان على **نصوصِ المحرك نفسِها** (‏`hyps_emu_*.json`) بلا شوطٍ جديد — فالحكمُ دالّةٌ
صرفةٌ من (مرجعٍ · مسموعٍ · إعداد)، والمرآةُ متماثلةٌ مع `RecitationScorer` بنسبة **100.000٪**
(‏`judge_parity.py` بعد D-348).

**(١) سؤالُ المسطرة:** `detect_score.cfg_for` **لا يضع** `strict_short`، أي أنّ أرقامَ D-349
حُسبت بمسطرةٍ **دون** `criticalPairsUncertain` المشحون (‏D-323). فهل يتغيّر الحكمُ بتغيّرها؟
⛔ **ولا يُفترض الجوابُ**: «أثرُه 0.00 على الاتّهام» قِيست على مجموعةٍ أخرى، وفرعٌ لا تمرّ به
عيّنتُك لا يحرسه اختبارُك (‏درسُ `detect_score` نفسِه 2026-09-08).

**(٢) سؤالُ الفضلة:** `criticalPairsUncertain` **مقايضةٌ**: يشتري اتّهاماً بكشف. وقد اشتُريت
معايرتُها على النموذج **الصغير**. فإن كان الأكبرُ يتّهم أقلَّ بـ2.33 نقطة فله **فضلةٌ** — فهل
إطفاؤها له يستردّ الكشفَ **ويبقى الحدُّ الأعلى للاتّهام دون الصفر**؟ فإن كان: **ثمنُ الكشفِ
‎−1.3 يسقط من قائمة الأثمان بلا مسٍّ للبوّابة**.

    python tools/tasmi_bench/judge_cfg_probe.py --pairs work/_bg/emu-0:B work/_br/emu-2:B2
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorer  # noqa: E402

CONF = {scorer.MISSED, scorer.SUBSTITUTED}
COLLAPSE = 0.60
PLAN = os.path.join(HERE, "inject_plan_riwaya.json")


def cfg(riwaya, strict):
    """مرآةُ `RiwayaProfile` — و`strict` هو `criticalPairsUncertain` (‏D-323)."""
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=riwaya == "warsh",
                         sila=riwaya in ("warsh", "qalun"), mark_sila=True, strict_short=strict)


def judge(plan, hyps, strict):
    """(كشفٌ · اتّهامٌ · ن · لكلِّ بندٍ (اتّهام، كلٌّ، كُشف)) — الطريقةُ المعتمدةُ في `v2_gate.judge_arm`."""
    det = n = 0
    per = {}
    for it in plan:
        h = hyps.get(it["id"])
        if not h or "error" in h or not h.get("text"):
            continue
        n += 1
        ws = scorer.score(it["refText"].split(), h["text"], cfg(it.get("riwaya"), strict))["words"]
        if sum(1 for w in ws if w[1] in CONF) / max(len(ws), 1) > COLLAPSE:
            per[it["id"]] = (0, 0, 0)          # يكبحه حارسُ الانهيار: لا اتّهامَ ولا كشف
            continue
        d = 1 if any(w[1] in CONF for w in ws if abs(w[0] - it["wordIndex"]) <= 1) else 0
        o = [w for w in ws if abs(w[0] - it["wordIndex"]) > 1]
        per[it["id"]] = (sum(1 for w in o if w[1] in CONF), len(o), d)
        det += d
    fa = sum(v[0] for v in per.values()) / max(sum(v[1] for v in per.values()), 1)
    return det / max(n, 1), fa, n, per


def boot_diff(pairs, seed=7, boot=4000):
    """عنقودُ الإعادة = **الآية** لا الكلمة (كلماتُ الآية مرتبطة) · الفرقُ نسبتان لا متوسّطُ نسب."""
    rng = random.Random(seed)
    d = []
    for _ in range(boot):
        p = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
        a = sum(x[0] for x in p) / max(sum(x[1] for x in p), 1)
        b = sum(x[2] for x in p) / max(sum(x[3] for x in p), 1)
        d.append((b - a) * 100)
    d.sort()
    return d[int(0.025 * len(d))], d[int(0.975 * len(d))], sum(1 for x in d if x > 0) / len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", required=True, help="مجلد:لاحقة — مثل work/_bg/emu-0:B")
    ap.add_argument("--cand", default="base-ar")
    ap.add_argument("--base", default="shipped")
    a = ap.parse_args()

    plan_all = json.load(open(PLAN, encoding="utf-8"))["items"]
    # 🧺 **تُضمّ المجموعتان بنداً بنداً** (لا يُتوسَّط رقمان): العيّنةُ الأكبرُ هي علاجُ
    # اتّساعِ المجال، وقد وُعد بها في D-349 قبل أن تُقاس.
    acc = {}
    for spec in a.pairs:
        d, suf = spec.rsplit(":", 1)
        d = d if os.path.isabs(d) else os.path.join(HERE, d)
        for f in sorted(os.listdir(d)):
            if not (f.startswith("hyps_emu_g3r") and f.endswith(".json")):
                continue
            arm = f[:-5].split("_cap_", 1)[1]
            if arm.endswith("-" + suf):
                arm = arm[: -len(suf) - 1]
            # ⛔ **المعرّفُ يُنسَب إلى مجموعته:** `g3r:noisy` و`g3r:clean` بندَان **بالمعرّفات عينِها**
            # (خطّةُ الحقن واحدةٌ والشرطُ الصوتيُّ مختلف) ⇒ `update` المجرّدُ **يكتب أحدَهما فوق
            # الآخر** فتعود 319 بنداً إلى 160 **بصمتٍ وبرقمٍ معقول**. والنسبةُ تمنع ذلك.
            tag = f[:-5].split("hyps_emu_", 1)[1].split("_cap_", 1)[0]
            h = json.load(open(os.path.join(d, f), encoding="utf-8")).get("hyps", {})
            acc.setdefault(arm, {}).update({tag + "/" + k: v for k, v in h.items()
                                            if v.get("text") is not None and "error" not in v})
    ha, hb = acc.get(a.base, {}), acc.get(a.cand, {})
    common = set(ha) & set(hb)
    if len(common) < 50:
        raise SystemExit(f"⛔ تقاطعٌ هزيل ({len(common)}) — الأذرعُ الموجودة: {sorted(acc)} · لا يُقرأ الصفرُ نتيجةً")
    by_id = {}
    for it in plan_all:
        by_id.setdefault(it["id"], it)
    plan = [{**by_id[k.split("/", 1)[1]], "id": k} for k in sorted(common) if k.split("/", 1)[1] in by_id]
    print(f"‏ن = **{len(plan)}** بنداً مضمومةً · الذراعان `{a.base}` ⇒ `{a.cand}`\n")

    print("| المسطرة | الذراع | الكشف | الاتّهامُ الكاذب |")
    print("|---|---|---:|---:|")
    R = {}
    for strict, label in ((True, "**المشحونة** (`criticalPairsUncertain`)"), (False, "بلا `criticalPairsUncertain`")):
        for arm, h in ((a.base, ha), (a.cand, hb)):
            R[(strict, arm)] = judge(plan, h, strict)
            print(f"| {label} | `{arm}` | {R[(strict, arm)][0]*100:.1f}٪ | {R[(strict, arm)][1]*100:.2f}٪ |")

    print("\n### ‏(١) أتتغيّر أرقامُ البوّابة بتغيّر المسطرة؟\n")
    for arm in (a.base, a.cand):
        dd = (R[(False, arm)][0] - R[(True, arm)][0]) * 100
        df = (R[(False, arm)][1] - R[(True, arm)][1]) * 100
        print(f"‏`{arm}`: بإطفائها الكشفُ **{dd:+.1f}** والاتّهامُ **{df:+.2f}** نقطة.")

    print("\n### ‏(٢) أفي الاتّهام فضلةٌ تُنفَق على الكشف؟\n")
    print("| المرشَّحُ يُحكم بـ | الكشف مقابل المشحون | الاتّهام | المجال 95٪ | احتمالُ الارتفاع | البوّابة |")
    print("|---|---:|---:|---:|---:|:-:|")
    base_det, base_fa, _, pa = R[(True, a.base)]
    for strict, label in ((True, "المسطرةِ المشحونة"), (False, "مسطرةٍ **أصرمَ** (بلا الاحتمال)")):
        det, fa, _, pb = R[(strict, a.cand)]
        pairs = [(pa[i][0], pa[i][1], pb[i][0], pb[i][1]) for i in pa if i in pb]
        lo, hi, p = boot_diff(pairs)
        ok = "✅" if hi <= 0 else "⛔"
        print(f"| {label} | {(det-base_det)*100:+.1f} ({base_det*100:.1f} ⇒ **{det*100:.1f}**) | "
              f"{(fa-base_fa)*100:+.2f} ({base_fa*100:.2f} ⇒ **{fa*100:.2f}**) | "
              f"[{lo:+.2f} .. **{hi:+.2f}**] | {p*100:.1f}٪ | {ok} |")


if __name__ == "__main__":
    sys.exit(main())
