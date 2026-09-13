# -*- coding: utf-8 -*-
"""🧹 **الزوائدُ الكاذبة** — كم زائدةً يُعرَض للقارئ **وهو لم يزد شيئاً**؟ (‏D-366 ⇒ قبل أيّ عرض)

⛔ **ثغرةٌ في المسطرة لا في المحرك:** «الاتّهامُ الكاذب» المنشورُ في اللوحة يعدّ **أحكامَ الكلمات**
(‏فائتةٌ أو مُبدلة) **ولا يعدّ الزوائد أصلاً**. فلو عُرضت الزوائدُ في مواضعها للمستخدم — وقد صار
المحركُ قادراً على ذلك (`locatedAdditions`) — **لظهرت له ضجّةٌ لا يقيسها أحد**.

⇒ فهذه الأداةُ تقيس القناةَ المنسيّة: **زائدةٌ غريبةٌ بعيدةٌ عن موضع الحقن** (‏أكثرَ من كلمةٍ)
لم يزدها القارئُ بل سمعها النموذجُ من عنده.

⭐ **والحدُّ المحافظ:** ما قرُب من موضع الحقن (‏±1) **لا يُحسب كاذباً** ولو كان غريباً — فقد يكون
أثراً جانبيّاً للحقن نفسِه. فالرقمُ الخارجُ **أدنى ما يمكن**، والحقيقةُ لا تقلّ عنه.

    python tools/tasmi_bench/extras_noise_probe.py --dirs work: --arms shipped-T base-vs-tiny-ar-T
    python tools/tasmi_bench/extras_noise_probe.py --dirs work: --arms … --clean   # g1 النظيفة
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import scorer  # noqa: E402
import judge_cfg_probe as J  # noqa: E402
import restore_probe as R  # noqa: E402
import v2_gate as G  # noqa: E402
from detect_anatomy import boot  # noqa: E402


def noise_extras(it, hyp, tol=1):
    """(عددُ الزوائد الكاذبة، عددُ كلمات المرجع) — الكاذبةُ: **غريبةٌ** وبعيدةٌ عن موضع الحقن.

    ⭐ **وعلى تلاوةٍ نظيفةٍ** (بلا `wordIndex`) **كلُّ غريبةٍ كاذبةٌ** — فلا موضعَ حقنٍ يُستثنى،
    والقارئُ لم يزد شيئاً أصلاً. وهي **الحالةُ الغالبةُ للمستخدم**.
    """
    c = J.cfg(it.get("riwaya"), True)
    ref = it["refText"].split()
    s = scorer.score(ref, hyp["text"], c)
    w = None if it.get("wordIndex") in (None, "") else int(it["wordIndex"])
    # ⛔ **وصورُ الكلمات تُبنى كما يبنيها الحاكمُ نفسُه** لا بتقريبٍ منها: `variants` ثمّ
    # `_riwaya_forms` — وإلّا صار «غريبٌ» في الأداة غيرَ «غريبٍ» في المحرك، وهو انحرافُ مسطرةٍ صامت.
    forms = [scorer._riwaya_forms(scorer.variants(x, c), c) for x in ref]
    n = 0
    for text, at in s.get("located", []):
        # غريبةٌ: لا تطابق كلمةً من الآية (‏قاعدةُ D-267 — الإعادةُ ليست زيادة)
        if any(scorer._matches(f, text, c) for f in forms):
            continue
        if w is None or abs(at - w) > tol:
            n += 1
    return n, len(ref)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--clean", action="store_true",
                    help="مجموعةٌ نظيفةٌ غيرُ محقونة (‏`g1`): المرجعُ من عيّنة المقعد، وكلُّ غريبةٍ كاذبة")
    ap.add_argument("--prefix", default="", help="بادئةُ ملفّات الفرضيّات (‏الافتراضُ g3r · أو hyps_emu_g1)")
    a = ap.parse_args()

    prefix = a.prefix or ("hyps_emu_g1" if a.clean else "hyps_emu_g3r")
    if a.clean:
        # 📌 عيّنةُ الآية الواحدة + خطّةُ التلاوة الطويلة — تحمل `refText` و`riwaya` بلا حقن.
        plan_all = {it["id"]: it for it in G.pool_items()}
    else:
        plan_all = {it["id"]: it for it in json.load(open(J.PLAN, encoding="utf-8"))["items"]}
    acc = R.load(a.dirs, prefix=prefix)
    arms = R.arms_or_die(acc, a.arms)

    kind = "**تلاوةٌ نظيفةٌ غيرُ محقونة**" if a.clean else "عيّنةُ الحقن `g3r`"
    print(f"# 🧹 الزوائدُ الكاذبة ({kind}) — قناةٌ لا يعدّها «الاتّهامُ الكاذب» المنشور\n")
    print("**التعريف:** زائدةٌ **غريبةٌ** (لا تطابق كلمةً من الآية · D-267) **وبعيدةٌ عن موضع "
          "الحقن أكثرَ من كلمة** ⇒ لم يزدها القارئُ. والحدُّ محافظ: ما قرُب لا يُحسب كاذباً.\n")
    print("| الذراع | ن | آياتٌ فيها زائدةٌ كاذبةٌ واحدةٌ على الأقلّ | لكلِّ 100 كلمةٍ | مجال 95٪ للنسبة |")
    print("|---|---:|---:|---:|---:|")
    rows = {}
    for name, h in zip(a.arms, arms):
        items = [{**plan_all[k.split("/", 1)[1]], "id": k} for k in sorted(h) if k.split("/", 1)[1] in plan_all]
        if len(items) < 50:
            raise SystemExit(f"⛔ {len(items)} بنداً فقط في {name} — لا يُقرأ الصفرُ نتيجةً")
        per = [noise_extras(it, h[it["id"]]) for it in items]
        hit = sum(1 for n, _ in per if n)
        words = sum(w for _, w in per)
        extras = sum(n for n, _ in per)
        lo, hi = boot([(0, 1 if n else 0) for n, _ in per])
        rows[name] = (len(items), hit / len(items) * 100, extras / words * 100)
        print(f"| `{name}` | {len(items)} | **{hit/len(items)*100:.1f}٪** ({hit}/{len(items)}) | "
              f"**{extras/words*100:.2f}** | [{lo:+.1f} .. {hi:+.1f}] |")

    if len(a.arms) == 2:
        (n1, p1, r1), (n2, p2, r2) = rows[a.arms[0]], rows[a.arms[1]]
        print(f"\n**والفرقُ بين الذراعَين:** نسبةُ الآيات {p2-p1:+.1f} نقطة · والكثافةُ {r2-r1:+.2f} "
              "لكلِّ 100 كلمة.")
    print("\n⛔ **وما يُقرأ من هذا الجدول:** إن كانت النسبةُ عاليةً فـ**عرضُ الزوائد في مواضعها "
          "يُدخل ضجّةً على المستخدم** ولو كان الموضعُ صحيحاً (‏ودقّتُه 100٪ · D-366) ⇒ فالعرضُ "
          "يحتاج عتبةً أو تهدئةً، لا مجرّد حقلٍ جديد. وإن كانت منخفضةً فالبابُ مفتوح.")
    if a.clean:
        print("✅ **وهذه هي الحالةُ الغالبةُ للمستخدم** — تلاوةٌ صحيحةٌ بلا حقن: فكلُّ زائدةٍ "
              "غريبةٍ هنا **ضجّةٌ محضة**، ولا موضعَ حقنٍ يُستثنى.")
    else:
        print("⚠️ **وحدٌّ يُقال:** العيّنةُ **محقونةٌ عمداً** (`g3r`) فهي أصعبُ من تلاوةٍ طبيعيّة؛ "
              "والرقمُ على النظيفة يُقاس بـ`--clean` على `g1`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
