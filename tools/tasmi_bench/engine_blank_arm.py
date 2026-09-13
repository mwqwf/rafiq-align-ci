#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⚖️🩻 دواءُ الرمز الفارغ **على حاكم المحرك نفسِه** لا على المرآة (‏D-414)

**الدَّينُ الذي سلّمته D-412/D-413 نصّاً:** «الشرطُ تحقّق … ويبقى قياسٌ على الصوت ومرآتُه في
`RecitationScorer.kt`». والصوتُ ممنوعٌ في السحابة — **أمّا المحركُ فليس ممنوعاً**: فـ
`engine_judge/build_and_run.sh` يبني `RecitationScorer.kt` و`RiwayaProfile.kt` على JVM
بمترجمِ كوتلن من ميفن المركزيّ (مسموح). ⇒ فكلُّ عدّة D-412 تُعاد هنا **على الملفّ المشحون**.

## 🔑 ولماذا لا يُمَسّ كوتلن بحرف
الدواءُ في `blank_symbol_probe._score_dropblank` ليس تغييراً في المحاذاة، بل **ترشيحٌ قبلها**:
`ref` تُنقّى من الكلمات الفارغة ثمّ تُنادى المِسطرةُ نفسُها، وتُعاد الأحكامُ إلى فهارسها.
⇒ فالذراعان مدخلان اثنان لحاكمٍ **واحدٍ غيرِ مُعدَّل**:

    الذراعُ «قبل» · ref = كلماتُ الآية كلُّها (‏والرمزُ فيها كلمةٌ صورتُها "")
    الذراعُ «بعد» · ref = كلماتُ الآية **بلا الفارغات**

⇒ **لا ترقيعَ ولا نسخةَ عمل**: ما يُقاس هنا هو `RecitationScorer.kt` كما هو على القرص.
📌 وهذا أقوى من ترقيع `SHORT_CAP` في `build_and_run.sh`: ذاك يقيس محركاً لم يُشحن، وهذا
يقيس المشحونَ بعينِه.

## ما يُقاس (‏المصحفُ كلُّه · الرواياتُ الستّ · بلا شبكةٍ ولا صوت)
الحالاتُ **هي حالاتُ `blank_symbol_probe.fix` حرفاً**: في كلِّ آيةٍ فيها رمز، يُلحَم كلُّ زوجٍ
مسموعٍ متجاورٍ على حدة (‏`op 4` موجودٌ بعينِه ليغفر «مرجعيّتان = مسموعة» ⇒ سقوطُه عطبُ مِسطرة).
والعدّاداتُ الثلاثةُ بتعريفها هناك: **يُنقذ رمزاً** · **يُنقذ كلمةً قرآنيّة** · 🚨 **الكلفة**.

## 🧪 والضابطُ أوّلاً (‏قاعدةُ D-279)
`--control N` يُجري **المرآةَ البايثونيّةَ** على حالات أوّلِ `N` آيةٍ نفسِها ويطابق سلسلةَ
الأحكام حرفاً بحرف مع المحرك. فإن افترقا فالخبرُ **انحرافُ المرآة** لا رقمُ الدواء — وهو
أخطرُ من أيِّ رقمٍ في اللوحة، إذ يعني أنّ ما تقيسه اللوحةُ ليس ما يحكم به التطبيق.

    python engine_blank_arm.py --control 400 --riwaya hafs
    python engine_blank_arm.py --riwaya hafs
    python engine_blank_arm.py --all

⛔ **يُقاس ولا يُشحن**: قرارُ الشحن للجلسة المحلّية بعد قياسٍ على الصوت.
"""
import argparse
import collections
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
import detect_score  # noqa: E402
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
WORK = os.path.join(HERE, "work")
CODE = {scorer.CORRECT: "C", scorer.MISSED: "M", scorer.SUBSTITUTED: "S",
        scorer.ADDED: "A", scorer.UNCERTAIN: "U"}


def _blank_flags(ref, cfg):
    return [scorer.norm(w, cfg) == "" for w in ref]


def _structural_hyp(ref, cfg):
    """المسموعُ المثاليّ: تطبيعُ المرجع، والفراغاتُ تسقط كما يُسقطها الحاكمُ من المسموع."""
    return [x for x in (scorer.norm(w, cfg) for w in ref) if x]


def gen_cases(riw, upto=0):
    """يولّد حالاتِ الالتحام — **بالترتيب نفسِه** الذي يمشي به `blank_symbol_probe.fix`.

    لكلِّ حالةٍ سطران: `…|b` (‏قبلُ: المرجعُ كاملاً) و`…|a` (‏بعدُ: بلا الفارغات).
    ويُعاد معها وصفُها (‏فهارسُ الفارغات وفهارسُ المُبقاة) كي تُحسب العدّاداتُ بلا إعادةِ توليد.
    """
    cfg = detect_score.cfg_for(riw)
    text = load_text(riw)
    rows, meta = [], []
    for n, a in enumerate(text):
        if upto and n >= upto:
            break
        ref = a.split()
        if not ref:
            continue
        flags = _blank_flags(ref, cfg)
        if not any(flags):
            continue
        hyp = _structural_hyp(ref, cfg)
        keep = [i for i, f in enumerate(flags) if not f]
        ref_b = " ".join(ref)
        ref_a = " ".join(ref[i] for i in keep)
        for k in range(len(hyp) - 1):
            t = " ".join(hyp[:k] + [hyp[k] + hyp[k + 1]] + hyp[k + 2:])
            name = f"{riw}:{n}:{k}"
            rows.append(f"{name}|b\t{ref_b}\t{t}\t{riw}")
            rows.append(f"{name}|a\t{ref_a}\t{t}\t{riw}")
            meta.append((name, flags, keep, ref, t))
    return cfg, rows, meta


def run_engine(rows, tag):
    """يبني حاكمَ المحرك ويشغّله على الحالات — لا يُمَسّ ملفُّ المحرك بحرف."""
    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(WORK, f"blankarm_{tag}_cases.tsv")
    out = os.path.join(WORK, f"blankarm_{tag}_out.tsv")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows) + "\n")
    sh = os.path.join(HERE, "engine_judge", "build_and_run.sh")
    t0 = time.time()
    subprocess.run(["bash", sh, src, out], check=True)
    got = {}
    with open(out, encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2:
                got[f[0]] = f[1]
    return got, time.time() - t0


def tally(meta, got):
    """العدّاداتُ الثلاثةُ بتعريف `blank_symbol_probe.fix` حرفاً — لكن من أحكام المحرك."""
    gain_b = gain_r = loss = cases = 0
    missing = 0
    ex_loss = []
    for name, flags, keep, ref, t in meta:
        vb, va = got.get(name + "|b"), got.get(name + "|a")
        if vb is None or va is None or len(vb) != len(ref) or len(va) != len(keep):
            missing += 1
            continue
        cases += 1
        ob = [i for i, f in enumerate(flags) if f and vb[i] != "C"]
        orr = [i for i, f in enumerate(flags) if not f and vb[i] != "C"]
        # الذراعُ «بعد»: الفارغةُ غيرُ محكومةٍ بالبناء ⇒ `nb` فارغةٌ دائماً، والحقيقيّةُ
        # تُقرأ من موضعها في المرجع المنقّى.
        nr = [i for pos, i in enumerate(keep) if va[pos] != "C"]
        if ob:
            gain_b += 1
        if len(orr) > len(nr):
            gain_r += 1
        if len(nr) > len(orr):
            loss += 1
            if len(ex_loss) < 5:
                ex_loss.append((name, [ref[i] for i in nr], [ref[i] for i in orr]))
    return cases, gain_b, gain_r, loss, missing, ex_loss


def mirror_cfg(riw, strict):
    """مرآةُ `RiwayaProfile` — و`strict` هو `criticalPairsUncertain` (‏D-323).

    ⚠️ `detect_score.cfg_for` **لا يضعه**، والمحركُ يشحنه **مفعَّلاً** منذ D-323
    (`RecitationScorer.criticalPairsUncertain = true`، و`MainActivity` لا يكتبه إلّا إن
    وُجد مُعطى التنقيح). ⇒ فالضابطُ يُجرى بالوجهين، والفرقُ بينهما هو الخبر.
    """
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=riw == "warsh",
                         sila=riw in ("warsh", "qalun"), mark_sila=True, strict_short=strict)


def mirror_codes(ref, t, cfg, keep=None):
    """سلسلةُ أحكام المرآة على الحالة نفسِها — للضابط وحدَه."""
    r = ref if keep is None else [ref[i] for i in keep]
    return "".join(CODE[w[1]] for w in scorer.score(r, t, cfg)["words"])


def control(riw, upto, meta, got, cfg):
    """🧪 المرآةُ مقابلَ المحرك على الحالات نفسِها — حرفاً بحرف، على الذراعَين معاً."""
    ok = bad = 0
    ex = []
    for name, flags, keep, ref, t in meta:
        for suffix, kp in (("|b", None), ("|a", keep)):
            eng = got.get(name + suffix)
            mir = mirror_codes(ref, t, cfg, kp)
            if eng == mir:
                ok += 1
            else:
                bad += 1
                if len(ex) < 5:
                    ex.append((name + suffix, mir, eng))
    return ok, bad, ex


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--riwaya", action="append", choices=RIWAYAT)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--upto", type=int, default=0, help="قصُّ مدخل المسح عند هذا العدد من الآيات")
    ap.add_argument("--control", type=int, default=0,
                    metavar="N", help="اجعل المسحَ على أوّل N آية وطابقِ المرآةَ بالمحرك")
    args = ap.parse_args()

    riwayat = RIWAYAT if args.all else tuple(args.riwaya or ("hafs",))
    upto = args.control or args.upto

    for riw in riwayat:
        t0 = time.time()
        cfg, rows, meta = gen_cases(riw, upto=upto)
        if not meta:
            print(f"  {riw}: لا حالات (‏upto={upto})")
            continue
        got, dt = run_engine(rows, riw)
        cases, gain_b, gain_r, loss, missing, ex_loss = tally(meta, got)
        print(f"\n  **{riw}** · حالاتُ الالتحام {cases} (‏{2 * len(meta)} حكماً على المحرك "
              f"في {dt:.0f}ث) · مفقودٌ {missing} {'✅' if missing == 0 else '🚨'}")
        print(f"     يُنقذ رمزاً {gain_b} · يُنقذ كلمةً قرآنيّةً {gain_r} · "
              f"🚨 **الكلفة {loss}** {'✅' if loss == 0 else '🚨'}")
        print(f"ENGARM\t{riw}\t{cases}\t{gain_b}\t{gain_r}\t{loss}\t{missing}")
        for e in ex_loss:
            print(f"     مثالُ كلفة: {e}")
        if args.control:
            for label, strict in (("مرآةُ اللوحة (`cfg_for` · بلا strict_short)", False),
                                  ("المرآةُ بـ`strict_short=True` (‏= المشحون)", True)):
                ok, bad, ex = control(riw, upto, meta, got, mirror_cfg(riw, strict))
                print(f"     🧪 الضابط · {label} ⇔ المحرك على {ok + bad} سلسلةَ حكم: "
                      f"**{ok} متطابقة · {bad} منحرفة** {'✅' if bad == 0 else '🚨'}")
                print(f"CTRL\t{riw}\t{int(strict)}\t{ok}\t{bad}")
                for e in ex:
                    print(f"        انحراف: {e[0]}  المرآة={e[1]}  المحرك={e[2]}")
        print(f"     (‏زمنُ الرواية {time.time() - t0:.0f}ث)")


if __name__ == "__main__":
    main()
