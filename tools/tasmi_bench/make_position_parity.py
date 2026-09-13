# -*- coding: utf-8 -*-
"""⚖️📍 **حزمةُ تماثلٍ لمواضع الزوائد** — كي لا ينحرف المحركُ عن مرآته صامتاً (‏D-366 ⇒ D-372).

⛔ **لِمَ وُجدت:** كلُّ أرقام بابِ الزوائد (‏التوطينُ 100٪ · الضجّةُ 7.0٪ · ميزانُ التهدئة)
مُنتَجةٌ بمرآة `scorer.py`، **والمعروضُ للمستخدم يُنتجه المحرك**. فإن اختلفت المحاذاتان في
**موضعِ** زائدةٍ واحدةٍ صار كلُّ ذلك يصف محركاً غيرَ المحرك — وهو أسوأُ من لا قياس.
وحارسُ التماثل القائم (`parity_fixture.tsv`) يطابق **الأحكامَ ونصوصَ الزوائد** ولا يطابق
**مواضعَها** — فهذه الحزمةُ تُكمل الثغرة.

⭐ **وتُبنى بلا صوتٍ ولا شبكة:** الحالاتُ **مشتقّةٌ من نصوص العيّنة** بتحويلاتٍ حتميّة (دسُّ
كلمةٍ غريبةٍ في موضعٍ · في الصدر · في العجز · تكرارُ كلمة · زائدتان)، فتُولَّد في أيّ بيئةٍ
**ولو كان الدلوُ محجوباً** — وهو حالُ الوكيل السحابيّ.

    python tools/tasmi_bench/make_position_parity.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import scorer  # noqa: E402

OUT = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources", "position_parity.tsv")

# ⛔ **كلماتٌ غريبةٌ عن القرآن كلِّه** (كي لا تُحسب «إعادةً» بقاعدة D-267): أسماءٌ حديثةٌ لا ترد
#    في المصحف. وتُختار **قصيرةً وطويلةً** كي تُغطّى قاعدةُ الطول أيضاً.
ALIEN = ("كتاب", "مسجد", "حاسوب", "في")


def mutate(words):
    """(اسمُ الحالة، الكلماتُ المسموعة) — تحويلاتٌ حتميّةٌ تُغطّي مواضعَ الزيادة كلَّها."""
    n = len(words)
    mid = max(1, n // 2)
    yield "ins_mid", words[:mid] + [ALIEN[0]] + words[mid:]
    yield "ins_head", [ALIEN[1]] + list(words)
    yield "ins_tail", list(words) + [ALIEN[2]]
    yield "ins_short_mid", words[:mid] + [ALIEN[3]] + words[mid:]
    yield "dup_first", [words[0]] + list(words)
    if n >= 4:
        yield "ins_two", [ALIEN[0]] + words[:mid] + [ALIEN[1]] + words[mid:]
    yield "clean", list(words)


def main():
    sample = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))
    rows, seen = [], set()
    for it in sample["items"]:
        ref = it["refText"]
        w = [scorer.norm(x) for x in ref.split()]
        if len(w) < 4 or len(rows) >= 240:
            continue
        for name, hyp_words in mutate(w):
            key = (it["id"], name)
            if key in seen:
                continue
            seen.add(key)
            # ⛔ **والإعدادُ هو عينُ ما يُبنى في حارس التماثل القائم** (`make_parity_fixture.py`)
            # كي يطابق `RiwayaProfile.of(riwaya)` في المحرك حرفاً — ⛔ ولا `learner_tolerant`
            # (‏المحركُ لا يعرفه، وتفعيلُه يُرخّص الإقحامَ فيُغيّر المواضعَ).
            rw = it["riwaya"]
            c = scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=rw == "warsh",
                              sila=rw in ("warsh", "qalun"), mark_sila=True)
            r = scorer.score(ref.split(), " ".join(hyp_words), c)
            # 📍 الموضعُ مع النصّ — وعلمُ «الدخيلة» بقاعدة D-267 عينِها (صورُ الحاكم نفسِه)
            forms = [scorer._riwaya_forms(scorer.variants(x, c), c) for x in ref.split()]
            loc = []
            for t, at in r.get("located", []):
                foreign = not any(scorer._matches(f, t, c) for f in forms)
                loc.append(f"{t}:{at}:{1 if foreign else 0}")
            rows.append([f"{it['id']}_{name}", ref, " ".join(hyp_words), it["riwaya"],
                         " ".join(loc), "1" if r.get("collapsed") else "0"])
    # 🕌 **وحالاتٌ مصنوعةٌ تُكمل التغطيةَ** — فعيّنةُ المقعد **حفصيّةٌ كلُّها** وبلا انهيار:
    #    (١) ورشٌ وقالون بصورِ النقل والصلة (‏نظيرُ الحالات في `make_parity_fixture.py`) — فالتطبيعُ
    #        يختلف بالرواية، **والموضعُ يُحسب بعد التطبيع** فلا يُقاس على حفصٍ وحدَها.
    #    (٢) حالةُ انهيارِ تعرّفٍ مع زائدة — بها وحدَها تُختبر التهدئةُ المقيسة (‏D-372).
    EXTRA = [
        ("synth_warsh_ins", "اَ۬لَايْكَةِ لَظَٰلِمِينَ لَقَدْ كَانَ", "ليكه كتاب لظالمين لقد كان", "warsh"),
        ("synth_qalun_ins", "عَلَيْهِمُۥ اَ۬لَارْضُ وَمَا كَانَ", "عليهمو لرض مسجد وما كان", "qalun"),
        ("synth_warsh_dup", "اَ۬لَايْكَةِ لَظَٰلِمِينَ لَقَدْ كَانَ", "ليكه ليكه لظالمين لقد كان", "warsh"),
        # ⛔ انهيارٌ: اثنتا عشرةَ مرجعيّةً وثلاثَ عشرةَ دخيلةً ⇒ الحارسُ يُطلق ومعه زائدة
        ("synth_collapse_ins",
         "خُلِقَ مِن مَّآءٍۢ دَافِقٍۢ فَجَعَلَهُۥ نَسَبࣰا وَصِهْرࣰا وَكَانَ رَبُّكَ قَدِيرࣰا وَهُوَ ٱلَّذِى",
         "كتاب مسجد حاسوب ورقه شجره نهر جبل بحر سماء ارض ريح غيم مطر", "hafs"),
    ]
    for name, ref, hyp, rw in EXTRA:
        c = scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=rw == "warsh",
                          sila=rw in ("warsh", "qalun"), mark_sila=True)
        r = scorer.score(ref.split(), hyp, c)
        forms = [scorer._riwaya_forms(scorer.variants(x, c), c) for x in ref.split()]
        loc = []
        for t, at in r.get("located", []):
            foreign = not any(scorer._matches(f, t, c) for f in forms)
            loc.append(f"{t}:{at}:{1 if foreign else 0}")
        rows.append([name, ref, hyp, rw, " ".join(loc), "1" if r.get("collapsed") else "0"])

    # ⛔ **ولا تُكتب حزمةٌ هزيلةٌ صامتةً:** عيّنةٌ صغيرةٌ تعطي حارساً يمرّ دائماً — وهو أسوأُ من لا حارس.
    if len(rows) < 200:
        raise SystemExit(f"⛔ {len(rows)} حالةً فقط — حارسٌ بهذا العدد يمرّ على انحرافٍ حقيقيّ")
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("# حزمةُ تماثلِ **مواضع** الزوائد — مولَّدةٌ بـmake_position_parity.py · لا تُحرَّر بيد\n")
        f.write("# name\tref\thyp\triwaya\tlocated(نص:موضع:دخيلة)\tcollapsed\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    pos = sum(1 for r in rows if r[4])
    coll = sum(1 for r in rows if r[5] == "1")
    riw = sorted({r[3] for r in rows})
    print(f"✅ {len(rows)} حالةً ⇒ {OUT}")
    print(f"   فيها **{pos}** حالةً بزائدةٍ · و{len(rows)-pos} نظيفةً (ضابطٌ سالب) · "
          f"وانهيارٌ في {coll} · والرواياتُ {riw}")
    # ⛔ **وتغطيةٌ ناقصةٌ تُقال لا تُكتَم:** حارسٌ بلا انهيارٍ لا يحرس التهدئة، وبلا ورشٍ لا يحرس التطبيع.
    if coll == 0 or len(riw) < 2:
        raise SystemExit("⛔ تغطيةٌ ناقصة: لا بدّ من حالة انهيارٍ ومن أكثرَ من رواية")
    return 0


if __name__ == "__main__":
    sys.exit(main())
