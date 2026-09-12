#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧱 أرضيّةُ المِسطرة — هل يتّهم الحاكمُ قارئاً **تامّاً** بلا صوتٍ ولا نموذج؟

يقيس أرضيّتين على المصحف كلِّه (‏18,708 آية · ثلاثُ روايات) بلا شبكةٍ ولا عتاد:

  ١) **الأرضيّةُ البنيويّة** — المسموعُ هو تطبيعُ المرجع نفسِه. أيُّ كلمةٍ تسقط هنا
     فعطبٌ في المحاذاة لا في التطبيع: أشهرُ مصدرٍ لها **الرموزُ المنفصلة** (‏ۖ ۚ ۗ ۞ ۩)
     فهي كلماتٌ مرجعيّةٌ تُطبَّع إلى فراغٍ ولا يقابلها مسموع، فتُبتلَع بقاعدة «مرجعيّتان =
     مسموعة» (‏op 4). وهي في 2,719 آيةً من حفص وحدَه ⇒ لو انكسرت القاعدة لانهار الرقم.

  ٢) **أرضيّةُ الرُّخَص** — المسموعُ هو **الصورةُ البديلةُ** التي رخّصها الحاكمُ نفسُه
     (‏D-276 الخنجريّة · D-248 النقل · D-231 صلةُ الميم). الرخصةُ تُختبر عادةً كلمةً كلمةً؛
     وهذا يختبرها **داخلَ الآية**: قد تُقبل الصورةُ منفردةً ثمّ تضيع في المحاذاة إن التبست
     بجارتها أو زاحمت قاعدةَ الدمج.

كلتاهما يجب أن تبقيا **0.000٪**. أيُّ ارتفاعٍ انحدارٌ يُلاحَق قبل أيِّ قياسٍ بالصوت،
لأنّه يُنقص الرقمَ الرسميّ في كلِّ عيّنةٍ دفعةً واحدة.

    python ruler_floor.py                # المصحفُ كلُّه (‏≈5 دقائق)
    python ruler_floor.py --sample 300   # فحصٌ سريعٌ (‏ثوانٍ) للاستعمال في دورةٍ مضغوطة
    python ruler_floor.py --riwaya hafs
"""
import argparse
import collections
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../alignment")

import scorer  # noqa: E402
import detect_score  # noqa: E402
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun")


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


def run(riwaya, sample=0):
    cfg = detect_score.cfg_for(riwaya)
    text = load_text(riwaya)
    if sample:
        step = max(1, len(text) // sample)
        text = text[::step][:sample]
    res = {}
    for name in ("بنيويّة", "رُخَص"):
        bad = collections.Counter()
        ex = {}
        totw = badw = badv = used = 0
        for i, ayah in enumerate(text):
            ref = ayah.split()
            if not ref:
                continue
            if name == "بنيويّة":
                hyp = _hyp_structural(ref, cfg)
            else:
                hyp, u = _hyp_licensed(ref, cfg)
                used += u
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
        res[name] = dict(verses=len(text), bad_verses=badv, words=totw,
                         bad_words=badw, used=used, top=bad.most_common(8), ex=ex)
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--riwaya", choices=RIWAYAT + ("all",), default="all")
    p.add_argument("--sample", type=int, default=0, help="آياتٌ مأخوذةٌ بالتباعد (0 = الكلّ)")
    a = p.parse_args()
    riwayat = RIWAYAT if a.riwaya == "all" else (a.riwaya,)
    fail = 0
    for riw in riwayat:
        res = run(riw, a.sample)
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
            fail += r["bad_words"]
        sys.stdout.flush()
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
