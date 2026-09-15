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
import io
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


def selftest():
    """🧪 **حارسُ ذراع الرمز على المحرك** (‏D-604) — وهي **أقوى أداةٍ في العدّة حجّةً**:
    تقيس المشحونَ بعينِه **بلا ترقيعٍ ولا نسخةِ عمل** (‏مدخلان لحاكمٍ واحدٍ غيرِ مُعدَّل).
    وشوطُها ثقيلٌ (يبني الكوتلن ويجري المصحف) فلا يُشعَل في الدفعة اليوميّة.

    ⭐⭐ **وأثمنُ ما يُثبَّت أنّ حجّتَها لم تنكسر**: لو تسلّل إليها ترقيعٌ يوماً لصارت تقيس
      محركاً لم يُشحن **وهي تدّعي أنّها تقيس المشحون** — وذلك أسوأُ من رقمٍ خاطئ.
    ⭐⭐ **وأنّ الذراعين لا تفترقان إلّا في إسقاط الفارغات** — لو اختلف المسموعُ بينهما
      لصار الفرقُ فرقَ مدخلَين لا فرقَ دواء.
    ⭐ **وأنّ فجوةَ `strict_short` قائمةٌ فعلاً** (‏`detect_score.cfg_for` لا يضعه والمحركُ
      يشحنه مفعَّلاً · D-323) — فهي **علّةُ وجود** ضابط المرآة، ولو زالت لصار الضابطُ زينة.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()

    # ①⭐⭐ لا ترقيعَ البتّة — لا `SHORT_CAP` ولا كتابةَ في مصدر المحرك
    # ⚠️ ويُفتَّش عن **الاستعمال** لا عن الاسم: متنُ الملفّ يذكر `SHORT_CAP` ليقارن به،
    #    وحارسٌ يطابق نصَّ نفسِه حارسٌ ساقطٌ دائماً (‏درسُ D-509).
    # ⭐ والإبرةُ **تُركَّب وقتَ التشغيل** فلا يحويها الملفُّ حرفيّاً — وهو العلاجُ الآليُّ
    #    لدرس D-509 («حارسُ مصدرٍ يطابق نصَّ نفسِه ساقطٌ دائماً»): وقعتُ فيه ثلاثَ مرّات.
    needles = ["SHORT_" + "CAP=", "src_" + "cap", "en" + "v=", "os." + "environ"]
    hits = [x for x in needles if x in src]
    say(not hits,
        "⭐⭐ لا ترقيعَ في **الاستعمال**: لا سقفَ يُمرَّر ولا بيئةَ ولا نسخةَ عمل (‏%s)"
        % (hits or "نظيف"))
    say("لا يُمَسّ ملفُّ المحرك بحرف" in src and "يقيس المشحونَ بعينِه" in src,
        "⛔ ودعوى «المشحونُ بعينه» مكتوبةٌ في المتن — فهي تُحاسَب عليها")
    say("يُقاس ولا يُشحن" in src, "وشرطُ الشحن باقٍ: يُقاس ولا يُشحن")

    # ②⭐⭐ الذراعان مدخلان لحاكمٍ واحد: المسموعُ **واحد**، والمرجعُ يفترق بالفارغات وحدَها
    cfg, rows, meta = gen_cases("hafs", upto=14)
    pairs = {}
    for r in rows:
        name, ref, hyp, riw = r.split("\t")
        pairs.setdefault(name[:-2], {})[name[-1]] = (ref, hyp, riw)
    bad_hyp = [k for k, v in pairs.items() if v["b"][1] != v["a"][1]]
    bad_ref = []
    for k, v in pairs.items():
        keep = [w for w in v["b"][0].split() if scorer.norm(w, cfg)]
        if keep != v["a"][0].split():
            bad_ref.append(k)
    say(pairs and not bad_hyp,
        "⭐⭐ المسموعُ **واحدٌ** في الذراعين (‏%d زوجاً · شواذ %d)" % (len(pairs), len(bad_hyp)))
    say(not bad_ref,
        "⭐⭐ والمرجعُ في «بعدُ» = مرجعُ «قبلُ` بلا الفارغات لا غير (‏شواذ %d)" % len(bad_ref))
    say(all(len(v) == 2 for v in pairs.values()) and len(rows) == 2 * len(meta),
        "ولكلِّ حالةٍ سطران لا غير: %d سطراً لـ%d حالة" % (len(rows), len(meta)))

    # ③ ولا تُولَّد حالةٌ لآيةٍ بلا رمز — وإلّا انتفخ المقام بما لا يخصّ الباب
    say(all(any(_blank_flags(ref, cfg)) for _n, _f, _k, ref, _t in meta),
        "ولا حالةَ إلّا في آيةٍ فيها رمزٌ فارغ")

    # ④⭐ العدّاداتُ الثلاثةُ بتعريفها — بحاكمٍ مصطنعٍ في الذاكرة
    ref = ["ذالك", "ۛ", "الكتاب"]
    flags = [False, True, False]
    keep = [0, 2]
    m = [("t", flags, keep, ref, "ذالك الكتاب")]
    got = {"t|b": "CMC", "t|a": "CC"}          # الرمزُ متّهَمٌ قبلُ · ولا شيءَ بعدُ
    say(tally(m, got)[:4] == (1, 1, 0, 0), "⭐ يُنقذ رمزاً: %s" % (tally(m, got)[:4],))
    got = {"t|b": "SMC", "t|a": "CC"}          # وكلمةٌ حقيقيّةٌ زالت تهمتُها
    say(tally(m, got)[:4] == (1, 1, 1, 0), "⭐ ويُنقذ كلمةً قرآنيّةً: %s" % (tally(m, got)[:4],))
    got = {"t|b": "CMC", "t|a": "SC"}          # 🚨 الكلفة: تهمةٌ **جديدةٌ** بعدُ
    say(tally(m, got)[:4] == (1, 1, 0, 1), "🚨 والكلفةُ تُعَدّ: %s" % (tally(m, got)[:4],))
    got = {"t|b": "CMC"}                       # جوابٌ ناقصٌ من المحرك
    say(tally(m, got)[0] == 0 and tally(m, got)[4] == 1,
        "⛔ وما نقص جوابُه **يُعَدّ مفقوداً لا صفراً**: %s" % (tally(m, got)[:5],))

    # ⑤⭐⭐ فجوةُ `strict_short` قائمةٌ — وهي علّةُ وجود ضابط المرآة
    say(detect_score.cfg_for("hafs").strict_short is False
        and mirror_cfg("hafs", True).strict_short is True
        and mirror_cfg("hafs", False).strict_short is False,
        "⭐⭐ `cfg_for` لا يضع `strict_short` والمرآةُ تضعه بالوجهين — فالضابطُ يُجرى بهما")
    say("criticalPairsUncertain" in src and "D-323" in src,
        "وسببُ الفجوة مكتوبٌ باسمه (‏`criticalPairsUncertain` · D-323)")

    # ⑥ والمقارنةُ حرفاً بحرفٍ على الذراعين معاً — لا على واحدةٍ منهما
    say('for suffix, kp in (("|b", None), ("|a", keep)):' in src,
        "⛔ وضابطُ المرآة يقارن **الذراعين معاً** لا الأولى وحدَها")

    print("\n%s" % ("✅ حارسُ ذراع الرمز على المحرك: تمّ" if ok else "❌ حارسُ الذراع: أخفق"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثوانٍ · بلا كوتلن)")
    ap.add_argument("--riwaya", action="append", choices=RIWAYAT)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--upto", type=int, default=0, help="قصُّ مدخل المسح عند هذا العدد من الآيات")
    ap.add_argument("--control", type=int, default=0,
                    metavar="N", help="اجعل المسحَ على أوّل N آية وطابقِ المرآةَ بالمحرك")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

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
