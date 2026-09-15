# -*- coding: utf-8 -*-
"""يولّد حزمة تماثل بين حاكم القياس (بايثون) وحاكم الجهاز (Kotlin).

المخرج `engine/recitation/src/test/resources/parity_fixture.tsv`: لكل حالة
نصّ مرجعي ونصّ مسموع وأحكام بايثون؛ ويعيد اختبار `RecitationScorerParityTest`
تشغيل الحاكم الحقيقي عليها ويطابق حرفاً بحرف. فلا ينحرف أحدهما عن الآخر صامتاً
— وكل رقم في REPORT.md مسنودٌ بأن المقياس هو المحرك نفسه.

تشمل الحزمة الحالات الحقيقية من العيّنة **وحالات خطأ مصنوعة** (كلمة محذوفة،
كلمة زائدة، كلمة مُبدلة، إدغام كلمتين) كي تُغطّى كل الأحكام لا CORRECT وحده.

    python tools/tasmi_bench/make_parity_fixture.py
    python tools/tasmi_bench/make_parity_fixture.py --refresh-verdicts   # بلا شبكة

⭐ **وطَورُ التحديث (`--refresh-verdicts`) — لِمَ وُجد:** التوليدُ الكاملُ يحتاج
`work/hyps_ar.json` وهي فرضيّاتٌ محفوظةٌ في R2، فلا يعمل حيث تُحجب الشبكة (المناوبةُ
السحابية). و`fixture_audit.py` **يكشف** الانحرافَ هناك بلا شبكة — لكنّه لا **يُصلحه**،
فكان أيُّ تغييرٍ مقصودٍ في `norm` يقف عند مدقّقٍ أحمرَ لا سبيلَ إلى تخضيره.

والمفتاحُ أنّ **مُدخَلَ الحاكم محفوظٌ في الحزمة نفسِها**: عمودا `ref` و`hyp` هما ما
كان يأتي من الفرضيّات. ⇒ فيُعاد حسابُ **عمودَي الحكم والزوائد** من صفوفها بلا شبكة.

⛔ **وحدُّه المكتوبُ صراحةً:** لا يُضيف صفّاً ولا يحذفه — **اختيارُ الصفوف** يبقى
موقوفاً على الفرضيّات كما وصفَ `fixture_audit.py`. فهذا تحديثُ أحكامٍ لا توليدُ حزمة.
وهو يطبع **كلَّ صفٍّ تغيّر حكمُه** ليكون التغييرُ فعلاً مقصوداً يُقرأ في الفرق، لا
تخضيراً صامتاً لمدقّقٍ أحمر.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import scorer  # noqa: E402

OUT = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources", "parity_fixture.tsv")
CODE = {scorer.CORRECT: "C", scorer.MISSED: "M", scorer.SUBSTITUTED: "S", scorer.UNCERTAIN: "U"}


def rows_of(path):
    """صفوفُ الحزمة المُودَعة — **مُدخَلُ الحاكم محفوظٌ فيها** (‏المرجعُ والمسموعُ والرواية).

    وهي القراءةُ نفسُها التي يعتمدها `fixture_audit.py` حين يعيد حسابَ الأحكام بلا شبكة.
    """
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) < 4:
                raise SystemExit(f"⛔ صفٌّ ناقصُ الأعمدة في {path}: {p[:1]}")
            out.append({"name": p[0], "ref": p[1], "hyp": p[2], "riwaya": p[3],
                        "old_verdicts": p[4] if len(p) > 4 else ""})
    return out


def cases():
    sample = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))
    hyps = json.load(open(os.path.join(HERE, "work", "hyps_ar.json"), encoding="utf-8"))["hyps"]
    out = []
    for it in sample["items"]:
        h = hyps.get(it["id"])
        if h and h.get("text"):
            # D-248: العمود الرابع صار معرّفَ الرواية (ملفّها في RiwayaProfile) لا علماً منطقياً.
            out.append({"name": it["id"], "ref": it["refText"], "hyp": h["text"],
                        "riwaya": it["riwaya"]})
    # حالات مصنوعة: تلاوة ناقصة/زائدة/مُبدلة/مدغمة على آية معلومة
    ref = next((c["ref"] for c in out if len(c["ref"].split()) >= 4), "بسم الله الرحمن الرحيم")
    w = ref.split()
    if len(w) >= 4:
        plain = " ".join(scorer.norm(x) for x in w)
        out += [
            {"name": "synth_naql_alif", "ref": "اَ۬لَايْكَةِ لَظَٰلِمِينَ", "hyp": "ليكه لظالمين", "riwaya": "warsh"},
            {"name": "synth_naql_off_for_hafs", "ref": "اَ۬لَايْكَةِ لَظَٰلِمِينَ", "hyp": "ليكه لظالمين", "riwaya": "hafs"},
            # D-248: قالون يصل الميم ولا ينقل؛ وصلة ۦ/ۥ للجميع
            {"name": "synth_qalun_sila_no_naql", "ref": "عَلَيْهِمُۥ اَ۬لَارْضُ", "hyp": "عليهمو لرض", "riwaya": "qalun"},
            {"name": "synth_warsh_sila_and_naql", "ref": "عَلَيْهِمُۥ اَ۬لَارْضُ", "hyp": "عليهمو لرض", "riwaya": "warsh"},
            {"name": "synth_hafs_ha_sila", "ref": "فَإِنَّهُۥ بِهِۦ", "hyp": "فانهو بهي", "riwaya": "hafs"},
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


def cfg_for(rw):
    """إعدادُ المرآة لهذه الحزمة — **مصدرٌ واحدٌ** يقرؤه المولّدُ ومدقّقُ الحزمة معاً.

    ⛔ ولِمَ يُفرَد؟ لأنّ `fixture_audit.py` يعيد حسابَ الأحكام من صفوف الحزمة نفسِها،
    فلو نسخ الإعدادَ نسخاً ثانياً لأصبح **مِسطرتان** ينحرف إحداهما صامتةً عن الأخرى.
    """
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=rw == "warsh",
                         sila=rw in ("warsh", "qalun"), mark_sila=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh-verdicts", action="store_true",
                    help="يُعيد حسابَ الأحكام من صفوف الحزمة المُودَعة — بلا شبكة، ولا يُضيف صفّاً ولا يحذفه")
    args = ap.parse_args()

    if args.refresh_verdicts:
        if not os.path.exists(OUT):
            raise SystemExit(f"⛔ لا حزمةَ لتُحدَّث: {OUT} غيرُ موجودة ⇒ يلزم التوليدُ الكاملُ بالفرضيّات.")
        src = rows_of(OUT)
        print(f"🔁 طَورُ التحديث — {len(src)} صفّاً من الحزمة المُودَعة (‏بلا شبكةٍ ولا فرضيّات)")
    else:
        src = cases()

    data, changed = [], []
    for c in src:
        rw = c.get("riwaya", "hafs")
        cfg = cfg_for(rw)
        s = scorer.score(c["ref"].split(), c["hyp"], cfg)
        v = "".join(CODE[x[1]] for x in s["words"])
        if c.get("old_verdicts") and c["old_verdicts"] != v:
            changed.append((c["name"], c["old_verdicts"], v))
        data.append({**c, "verdicts": v, "additions": s["additions"]})

    if args.refresh_verdicts:
        # ⭐ كلُّ صفٍّ تغيّر يُطبع: التخضيرُ الصامتُ لمدقّقٍ أحمرَ هو الخطرُ الوحيدُ في هذا الطَور.
        if changed:
            print(f"\n⚠️ **تغيّر حكمُ {len(changed)} صفّاً** — اقرأ الفرقَ وتأكّد أنّ التغييرَ مقصود:")
            for name, old, new in changed:
                print(f"   {name}: {old} ⇒ {new}")
        else:
            print("✅ لا حكمَ تغيّر — الحزمةُ كانت مطابقةً للمرآة أصلاً (‏التحديثُ لا-عمليّ).")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # TSV لا JSON: اختبارات الوحدة على Android لا تملك محلّل JSON حقيقياً
    # (‏org.json مُجوّف)، والحزمة لا تحتمل تبعية لأجل ملف حالات.
    with open(OUT, "w", encoding="utf-8", newline=chr(10)) as f:
        f.write("# مولّد: tools/tasmi_bench/make_parity_fixture.py — لا يُحرَّر يدوياً" + chr(10))
        f.write(chr(9).join(["# name", "ref", "hyp", "riwaya", "verdicts", "additions"]) + chr(10))
        for d in data:
            f.write(chr(9).join([d["name"], d["ref"], d["hyp"],
                                 d.get("riwaya", "hafs"), d["verdicts"],
                                 " ".join(d["additions"])]) + chr(10))
    print(f"✅ {len(data)} حالة → {OUT}")


if __name__ == "__main__":
    main()
