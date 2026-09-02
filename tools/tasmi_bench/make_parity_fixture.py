# -*- coding: utf-8 -*-
"""يولّد حزمة تماثل بين حاكم القياس (بايثون) وحاكم الجهاز (Kotlin).

المخرج `engine/recitation/src/test/resources/parity_fixture.tsv`: لكل حالة
نصّ مرجعي ونصّ مسموع وأحكام بايثون؛ ويعيد اختبار `RecitationScorerParityTest`
تشغيل الحاكم الحقيقي عليها ويطابق حرفاً بحرف. فلا ينحرف أحدهما عن الآخر صامتاً
— وكل رقم في REPORT.md مسنودٌ بأن المقياس هو المحرك نفسه.

تشمل الحزمة الحالات الحقيقية من العيّنة **وحالات خطأ مصنوعة** (كلمة محذوفة،
كلمة زائدة، كلمة مُبدلة، إدغام كلمتين) كي تُغطّى كل الأحكام لا CORRECT وحده.

    python tools/tasmi_bench/make_parity_fixture.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import scorer  # noqa: E402

OUT = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources", "parity_fixture.tsv")
CODE = {scorer.CORRECT: "C", scorer.MISSED: "M", scorer.SUBSTITUTED: "S"}


def cases():
    sample = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))
    hyps = json.load(open(os.path.join(HERE, "work", "hyps_ar.json"), encoding="utf-8"))["hyps"]
    out = []
    for it in sample["items"]:
        h = hyps.get(it["id"])
        if h and h.get("text"):
            out.append({"name": it["id"], "ref": it["refText"], "hyp": h["text"],
                        "naql": it["riwaya"] != "hafs"})
    # حالات مصنوعة: تلاوة ناقصة/زائدة/مُبدلة/مدغمة على آية معلومة
    ref = next((c["ref"] for c in out if len(c["ref"].split()) >= 4), "بسم الله الرحمن الرحيم")
    w = ref.split()
    if len(w) >= 4:
        plain = " ".join(scorer.norm(x) for x in w)
        out += [
            {"name": "synth_naql_alif", "ref": "اَ۬لَايْكَةِ لَظَٰلِمِينَ", "hyp": "ليكه لظالمين", "naql": True},
            {"name": "synth_naql_off_for_hafs", "ref": "اَ۬لَايْكَةِ لَظَٰلِمِينَ", "hyp": "ليكه لظالمين", "naql": False},
            {"name": "synth_missing_word", "ref": ref,
             "hyp": " ".join(scorer.norm(x) for x in w[:-1])},
            {"name": "synth_extra_word", "ref": ref, "hyp": plain + " ثم"},
            {"name": "synth_substitution", "ref": ref,
             "hyp": " ".join(["كلمه"] + [scorer.norm(x) for x in w[1:]])},
            {"name": "synth_merge", "ref": ref,
             "hyp": " ".join([scorer.norm(w[0]) + scorer.norm(w[1])] + [scorer.norm(x) for x in w[2:]])},
            {"name": "synth_empty", "ref": ref, "hyp": ""},
        ]
    return out


def main():
    data = []
    for c in cases():
        cfg = scorer.Config(strip_yeh_barree=True, dagger_optional=True,
                            naql=bool(c.get("naql")))
        s = scorer.score(c["ref"].split(), c["hyp"], cfg)
        data.append({**c, "verdicts": "".join(CODE[v[1]] for v in s["words"]),
                     "additions": s["additions"]})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # TSV لا JSON: اختبارات الوحدة على Android لا تملك محلّل JSON حقيقياً
    # (‏org.json مُجوّف)، والحزمة لا تحتمل تبعية لأجل ملف حالات.
    with open(OUT, "w", encoding="utf-8", newline=chr(10)) as f:
        f.write("# مولّد: tools/tasmi_bench/make_parity_fixture.py — لا يُحرَّر يدوياً" + chr(10))
        f.write(chr(9).join(["# name", "ref", "hyp", "naql", "verdicts", "additions"]) + chr(10))
        for d in data:
            f.write(chr(9).join([d["name"], d["ref"], d["hyp"],
                                 "1" if d.get("naql") else "0", d["verdicts"],
                                 " ".join(d["additions"])]) + chr(10))
    print(f"✅ {len(data)} حالة → {OUT}")


if __name__ == "__main__":
    main()
