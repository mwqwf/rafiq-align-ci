#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧱 أرضيّةُ المِسطرة — هل يتّهم الحاكمُ قارئاً **تامّاً** بلا صوتٍ ولا نموذج؟

يقيس ثلاثَ أرضيّاتٍ على المصحف كلِّه (‏37,416 آية · الرواياتُ الستّ) بلا شبكةٍ ولا عتاد:

  ١) **الأرضيّةُ البنيويّة** — المسموعُ هو تطبيعُ المرجع نفسِه. أيُّ كلمةٍ تسقط هنا
     فعطبٌ في المحاذاة لا في التطبيع: أشهرُ مصدرٍ لها **الرموزُ المنفصلة** (‏ۖ ۚ ۗ ۞ ۩)
     فهي كلماتٌ مرجعيّةٌ تُطبَّع إلى فراغٍ ولا يقابلها مسموع، فتُبتلَع بقاعدة «مرجعيّتان =
     مسموعة» (‏op 4). وهي في 2,719 آيةً من حفص وحدَه ⇒ لو انكسرت القاعدة لانهار الرقم.

  ٢) **أرضيّةُ الرُّخَص** — المسموعُ هو **الصورةُ البديلةُ** التي رخّصها الحاكمُ نفسُه
     (‏D-276 الخنجريّة · D-248 النقل · D-231 صلةُ الميم). الرخصةُ تُختبر عادةً كلمةً كلمةً؛
     وهذا يختبرها **داخلَ الآية**: قد تُقبل الصورةُ منفردةً ثمّ تضيع في المحاذاة إن التبست
     بجارتها أو زاحمت قاعدةَ الدمج.

  ٣) **أرضيّةُ فصل النداء** (‏D-408) — وهي الوحيدةُ التي تقيس المِسطرةَ على **ما يكتبه
     الإملاءُ الحديثُ فعلاً** لا على نفسِها: ياءُ النداء موصولةٌ في الرسم (`يَٰقَوْمِ`)
     ومفصولةٌ عند كلِّ كاتب («يا قوم»). وهي 349 موضعاً في كلِّ روايةٍ (‏2,095 في الستّ)،
     كلُّها معلَّقةٌ بقاعدة «مسموعتان = مرجعيّة» (‏op 3) وحدَها.
     ⚠️ والأرضيّتان الأوليان **لا تقيسان هذا الباب أصلاً**: مسموعُهما مشتقٌّ من المرجع
     بالتطبيع نفسِه، فلا فصلَ فيه ولا وصل.

كلُّها يجب أن تبقى **0.000٪**. أيُّ ارتفاعٍ انحدارٌ يُلاحَق قبل أيِّ قياسٍ بالصوت،
لأنّه يُنقص الرقمَ الرسميّ في كلِّ عيّنةٍ دفعةً واحدة.

📌 **والوجهُ المقلوبُ في ملفٍّ آخرَ — `merge_floor.py` (‏D-409):** هذه الأرضيّاتُ تقيس
**الفصلَ** (`op 3`: مسموعتان = مرجعيّة)، وذاك يقيس **الدمجَ** (`op 4`: مرجعيّتان = مسموعة)
حيث يصل الإملاءُ ما يفصله الرسمُ (`أَن لَّا` ⇒ «ألّا»). ولا يُجزئ أحدُهما عن الآخر: خضرةُ
أرضيّةِ الفصل هنا **لم تكشف** أنّ قاعدةَ الدمج عمياءُ عن كلِّ التحامٍ يُدغم.

    python ruler_floor.py                # المصحفُ كلُّه (‏≈10 دقائق · ستُّ روايات)
    python ruler_floor.py --sample 300   # فحصٌ سريعٌ (‏ثوانٍ) للاستعمال في دورةٍ مضغوطة
    python ruler_floor.py --riwaya hafs
    python ruler_floor.py --prove        # الضابطُ الموجب: يجب أن **تسقط** أرضيّةُ الفصل
"""
import argparse
import collections
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../alignment")

import scorer  # noqa: E402
import detect_score  # noqa: E402
from common import load_text  # noqa: E402

# ⛔ **D-408 (مناوبةٌ سحابية 2026-09-13):** كانت الأرضيّةُ ثلاثَ رواياتٍ وحدَها منذ D-296،
# وبعدَها أُضيفت إلى `norm` ثلاثُ قواعدَ **مقرُّها في الروايات الثلاث غيرِ المحروسة**:
# D-402 (‏ألفُ الإمالة `ۭيٰ` — الدوريُّ والسوسيُّ وحدَهما · 859 موضعاً) و D-403 و D-404.
# فكان الحارسُ يحرس ما لم يتغيّر ويترك ما تغيّر — وهو بعينِه درسُ `detect_score.cfg_for`:
# «فرعٌ لا تمرّ به عيّنتُك لا يُحرسه اختبارُك». ⇒ صارت الستَّ كلَّها.
# وملفُّ الرواية للثلاث المضافة مرآةُ `RiwayaProfile.kt` حرفاً بحرف: شعبةُ والدوريُّ
# والسوسيُّ **لا نقلَ ولا صلة** — فلا إعدادَ اختُرع هنا، `cfg_for` هو هو.
RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")


def _hyp_structural(ref, cfg):
    """المسموعُ = تطبيعُ المرجع، والفراغاتُ تسقط كما يسقطها `score` من المسموع."""
    return " ".join(x for x in (scorer.norm(w, cfg) for w in ref) if x)


def _hyp_licensed(ref, cfg):
    """المسموعُ = آخرُ صورةٍ رخّصها الحاكم (‏أبعدُها عن الرسم الصارم) حيث وُجدت."""
    out, used = [], 0
    for w in ref:
        forms = scorer._riwaya_forms(scorer.variants(w, cfg), cfg)
        pick = forms[-1] if len(forms) > 1 else forms[0]
        if len(forms) > 1:
            used += 1
        if pick:
            out.append(pick)
    return " ".join(out), used


# ياءُ النداء ذاتُ الخنجرية، ملتصقةً بمناداها في الرسم: `يَٰٓأَيُّهَا` · `يَٰقَوْمِ` · `يَٰمُوسَىٰ`.
_VOCATIVE = re.compile("^ي[ً-ْ]*ٰ")


def _hyp_split_vocative(ref, cfg, pieces=2):
    """المسموعُ = تطبيعُ المرجع، إلّا ياءَ النداء **فتُفصل كما يكتبها الإملاءُ الحديث**.

    المِسطرةُ تُخرج `ياايها` · `ياقوم` كلمةً واحدةً لأنّ الرسمَ يصلها، و**لا أحدَ يكتبها
    موصولةً**: whisper يكتب «يا أيها» · «يا قوم» كلمتين. فكلُّ موضعٍ من هذه المواضع
    معلَّقٌ بقاعدةِ الفصل وحدَها (`op 3`: مسموعتان = مرجعيّة)، ولو انكسرت لصارت
    اتّهاماً كاذباً مضموناً في أشهر نداءات القرآن.

    `pieces=3` **ضابطٌ موجب** لا قياس: يقطع الكلمةَ ثلاثاً، و`op 3` لا يتعدّى اثنتين
    ⇒ يجب أن **تسقط** الأرضيّة. أرضيّةٌ خضراءُ بلا ضابطٍ يُسقطها ليست شهادةَ سلامة.
    """
    out, used = [], 0
    for w in ref:
        n = scorer.norm(w, cfg)
        if not n:
            continue
        if _VOCATIVE.match(w) and n.startswith("يا") and len(n) > pieces:
            used += 1
            out += ["يا", n[2:3], n[3:]] if pieces == 3 else ["يا", n[2:]]
        else:
            out.append(n)
    return " ".join(out), used


def run(riwaya, sample=0, pieces=2):
    cfg = detect_score.cfg_for(riwaya)
    text = load_text(riwaya)
    if sample:
        step = max(1, len(text) // sample)
        text = text[::step][:sample]
    res = {}
    for name in ("بنيويّة", "رُخَص", "فصلُ النداء"):
        bad = collections.Counter()
        ex = {}
        totw = badw = badv = used = seen = 0
        for i, ayah in enumerate(text):
            ref = ayah.split()
            if not ref:
                continue
            if name == "بنيويّة":
                hyp = _hyp_structural(ref, cfg)
            elif name == "رُخَص":
                hyp, u = _hyp_licensed(ref, cfg)
                used += u
            else:
                hyp, u = _hyp_split_vocative(ref, cfg, pieces)
                # ⚠️ آيةٌ بلا نداءٍ تكرّر الأرضيّةَ البنيويّة حرفاً بحرف ⇒ تُسقَط كي لا
                # يُميَّع الرقمُ بـ6,236 آيةً خضراءَ مجّاناً: المقيسُ 349 موضعاً لا 82,008.
                if not u:
                    continue
                used += u
            seen += 1
            s = scorer.score(ref, hyp, cfg)
            totw += s["total"]
            miss = [w for w in s["words"] if w[1] != scorer.CORRECT]
            if miss:
                badv += 1
                badw += len(miss)
                for w in miss:
                    k = (scorer.norm(ref[w[0]], cfg), w[1])
                    bad[k] += 1
                    ex.setdefault(k, (i, ref[w[0]], w[2]))
        res[name] = dict(verses=seen, bad_verses=badv, words=totw,
                         bad_words=badw, used=used, top=bad.most_common(8), ex=ex)
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--riwaya", choices=RIWAYAT + ("all",), default="all")
    p.add_argument("--sample", type=int, default=0, help="آياتٌ مأخوذةٌ بالتباعد (0 = الكلّ)")
    p.add_argument("--prove", action="store_true",
                   help="ضابطٌ موجب: يقطع ياءَ النداء **ثلاثاً** — يجب أن تسقط أرضيّةُ الفصل")
    a = p.parse_args()
    riwayat = RIWAYAT if a.riwaya == "all" else (a.riwaya,)
    fail = 0
    for riw in riwayat:
        res = run(riw, a.sample, pieces=3 if a.prove else 2)
        for name, r in res.items():
            pct = 100 * r["bad_words"] / max(r["words"], 1)
            extra = f" · صورٌ بديلةٌ استُعملت {r['used']}" if r["used"] else ""
            mark = "✅" if r["bad_words"] == 0 else "🚨"
            print(f"{mark} {riw} · أرضيّةٌ {name}: كلماتٌ متّهمةٌ ظلماً "
                  f"{r['bad_words']}/{r['words']} = {pct:.3f}٪ · "
                  f"آياتٌ تخسر {r['bad_verses']}/{r['verses']}{extra}")
            for k, c in r["top"]:
                i, raw, heard = r["ex"][k]
                print(f"     ✗ {k[0]!r} حُكم {k[1]} ×{c} — الآية {i} {raw!r} ⇜ {heard!r}")
            # ⚠️ في وضع الضابط الموجب يُعكس الحكم: الأرضيّةُ الخضراءُ هنا **فشلُ الضابط**
            # (‏قطعٌ ثلاثيٌّ لم يكشفه الحاكم) لا سلامةَ مِسطرة.
            if not (a.prove and name == "فصلُ النداء"):
                fail += r["bad_words"]
            elif r["bad_words"] == 0:
                print("     🚨 الضابطُ الموجب لم يُسقط شيئاً ⇒ الأرضيّةُ لا تقيس")
                fail += 1
        sys.stdout.flush()
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
