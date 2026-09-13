#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔒 حزمةُ تماثلٍ للوجه **المشحون** — كي لا يبقى الوجهُ العامل هو الوجهَ غيرَ المحروس (‏D-421)

**الدَّينُ الذي سلّمته D-419 نصّاً:** «`RecitationScorerParityTest` يُطفئ العلمَ بيده ⇒ يُضاف
شوطٌ ثانٍ بالعلم مفعَّلاً، وإلّا بقي الوجهُ المشحونُ غيرَ محروس». وهذا قضاؤه.

## العطبُ الذي يُغلَق
`RecitationScorerParityTest.kt` يكتب `criticalPairsUncertain = false` **بيده** قبل جسم
التماثل، وذلك **لازمٌ لا خطأ**: حزمةُ `parity_fixture.tsv` وُلّدت بمرآةٍ بلا `strict_short`،
فلو قِيست بالعلم مفعَّلاً لسقطت. ⇒ لكنّ أثرَه أنّ **الوجهَ الذي يعمل في يد المستعمِل
(‏العلمُ مفعَّلٌ منذ D-323) لا يحرسه حارسُ التماثل البتّة** — وبه سقطت 7,521 حالةً في D-416
و2.9–3.3 نقطةٍ في D-419 بلا صرخةٍ واحدة.

## الدواءُ: حزمةٌ ثانيةٌ لا تبديلُ الأولى
تُقرأ `parity_fixture.tsv` **المودَعة** (‏أعمدةُ الاسم والمرجع والمسموع والرواية)، وتُعاد
أحكامُها بمرآةٍ عليها `strict_short=True` ⇒ `parity_fixture_strict.tsv`. فالحزمتان تصفان
**المدخلاتِ نفسَها بحاكمَين**، ويحرسهما اختباران: القديمُ بالعلم مطفأً والجديدُ بالعلم مفعَّلاً.

🔑 **ولا يحتاج هذا صوتاً ولا نموذجاً**: المدخلاتُ مودَعةٌ في الحزمة الأصليّة، وهذا يُعيد
الحكمَ عليها وحدَه. (`make_parity_fixture.py` يحتاج `work/hyps_ar.json` ⇒ لا يعمل في السحابة.)

    python make_strict_parity_fixture.py            # يكتب ويطبع عددَ ما افترق
    python make_strict_parity_fixture.py --check    # لا يكتب؛ يخرج بـ1 إن تخلّفت الحزمة

⛔ **ولا يُشحن بهذا شيء:** لا `RecitationScorer.kt` ولا `scorer.py` ولا افتراضٌ واحد.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import scorer  # noqa: E402

RES = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources")
SRC = os.path.join(RES, "parity_fixture.tsv")
OUT = os.path.join(RES, "parity_fixture_strict.tsv")
CODE = {scorer.CORRECT: "C", scorer.MISSED: "M", scorer.SUBSTITUTED: "S",
        scorer.ADDED: "A", scorer.UNCERTAIN: "U"}
TAB, NL = chr(9), chr(10)


def cfg_for(riwaya):
    """مرآةُ `RiwayaProfile` كما في `make_parity_fixture`، **وعليها العلمُ المشحون**.

    `strict_short=True` هو `RecitationScorer.criticalPairsUncertain` بعينِه: تسقط رخصةُ
    الكلمة القصيرة (`n ≤ 3 && d ≤ 1`) من `matches`، ويصير الزوجُ القصيرُ `UNCERTAIN`.
    """
    rw = {"1": "warsh", "0": "hafs"}.get(riwaya, riwaya)
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=rw == "warsh",
                         sila=rw in ("warsh", "qalun"), mark_sila=True, strict_short=True)


def rows():
    out = []
    with open(SRC, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip(NL)
            if not line.strip() or line.startswith("#"):
                continue
            f = line.split(TAB)
            if len(f) < 5:
                continue
            name, ref, hyp, riwaya = f[0], f[1], f[2], f[3]
            s = scorer.score(ref.split(), hyp, cfg_for(riwaya))
            out.append((name, ref, hyp, riwaya,
                        "".join(CODE[w[1]] for w in s["words"]),
                        " ".join(s["additions"]), f[4]))
    return out


def render(data):
    lines = ["# مولّد: tools/tasmi_bench/make_strict_parity_fixture.py — لا يُحرَّر يدوياً",
             "# الوجهُ المشحون: criticalPairsUncertain=true (‏strict_short في المرآة) — D-421",
             TAB.join(["# name", "ref", "hyp", "riwaya", "verdicts", "additions"])]
    for name, ref, hyp, riwaya, verdicts, adds, _old in data:
        lines.append(TAB.join([name, ref, hyp, riwaya, verdicts, adds]))
    return NL.join(lines) + NL


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(NL)[0])
    ap.add_argument("--check", action="store_true",
                    help="لا يكتب؛ يخرج بـ1 إن تخلّفت الحزمةُ المودَعة عن المولَّد")
    args = ap.parse_args()

    data = rows()
    diff = [d for d in data if d[4] != d[6]]
    print(f"الحالات: {len(data)} · **افترق حكمُها عن الحزمة المطفأة: {len(diff)}**")
    for name, _ref, _hyp, _rw, new, _a, old in diff[:8]:
        print(f"  🔀 {name}: مطفأً {old} ⇒ مفعَّلاً {new}")
    if not diff:
        print("⚠️ **لا فرق** ⇒ الحزمةُ لا تمرّ ببابِ الأزواج الحرجة، فالحارسُ الجديدُ فارغُ الأثر.")
    text = render(data)
    if args.check:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        ok = cur == text
        print("✅ الحزمةُ مواكِبة" if ok else "🚨 الحزمةُ متخلّفة — أعِدْ توليدَها")
        return 0 if ok else 1
    with open(OUT, "w", encoding="utf-8", newline=NL) as fh:
        fh.write(text)
    print(f"✅ {len(data)} حالة → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
