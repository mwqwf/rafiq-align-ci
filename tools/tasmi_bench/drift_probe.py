# -*- coding: utf-8 -*-
"""🌊 **هل يجرف الخطأُ ما بعده؟** — قياسُ الانتشار في التلاوة الطويلة من فرضيّاتٍ محفوظة.

## السؤالُ ومن أين جاء
D-335 وصفت العطبَ الأكبرَ (‏الضجيجُ يُسقط الطويلَ 35.9 نقطةً مقابل 11.6 للآية المفردة) وعلّلته
**نصّاً**: «الفكُّ ذاتيُّ الانحدار في نوافذَ ثلاثينيّة، فاختلالٌ واحدٌ **يجرف بقيّةَ النافذة**».
⇒ وهذا **تعليلٌ لم يُقَس**. وقياسُه يغيّر الطريق: إن كان الجرفُ حقيقيّاً فالعلاجُ **تقصيرُ
المجموعة أو إعادةُ الإرساء**، وإن كانت الأخطاءُ مستقلّةً فالعلاجُ **في السمع** لا في التقطيع.

⭐ **وقراءةُ الشفرة ضيّقت السؤالَ قبل القياس:** `LongAudioTranscriber` **يفرّغ كلَّ مجموعةٍ
وحدَها** (`transcribeTimed(part)` لكلِّ مجموعةٍ ≤ نافذة) ⇒ **لا سياقَ يُحمَل بين المجموعات**،
فالجرفُ — إن وُجد — **داخلَ المجموعة** لا بينها. (‏فلا يُقترح «إلغاءُ حملِ السياق»: ليس قائماً.)

## المسطرة — **شرطيّةٌ مقابل هامشيّة**
- **الهامشيّةُ** p: نسبةُ الكلمات المحكوم عليها بخطإٍ من كلِّ كلمات البنود.
- **الشرطيّةُ** q: نسبةُ الخطأ في الكلمة التي **سابقتُها خطأ**.
- q ≈ p ⇒ **أخطاءٌ مستقلّةٌ** (لا جرف) · q ≫ p ⇒ **جرفٌ** بقدر (q − p).
⚠️ **وحدُّ المسطرة مكتوب:** هذا يقيس **تجاورَ الأخطاء** لا سببَها؛ فتلاوةٌ صعبةُ الموضع
(‏آيةٌ ثقيلةٌ في الوسط) تُعطي تجاوراً بلا انحدارٍ ذاتيّ. ⇒ **دليلٌ مُرجِّحٌ لا برهان**،
والفصلُ التامُّ يحتاج ذراعاً تقصُّ المجموعةَ (مفتاحٌ غيرُ موجودٍ اليومَ في المسبار).

    python drift_probe.py --dirs "work:" --arms "shipped-P nogate-P" --sets "g4n g4"
    python drift_probe.py --selftest
"""
import argparse
import glob
import json
import os
import random
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))


def drift_stats(seqs, seed=7, boot=2000):
    """[seqs] = قوائمُ منطقيّةٍ (خطأٌ = True) لكلِّ بند ⇒ p · q · فرقُهما ومجالُه (عنقودٌ = بند).

    ⛔ **والكلمةُ الأولى لا سابقةَ لها** فلا تدخل في الشرطيّة — وإلّا حُسبت مع مَن لا شرطَ له.
    """
    def agg(pick):
        tot = err = prev_err = prev_err_and_err = 0
        for s in pick:
            tot += len(s)
            err += sum(1 for x in s if x)
            for i in range(1, len(s)):
                if s[i - 1]:
                    prev_err += 1
                    if s[i]:
                        prev_err_and_err += 1
        p = err / tot if tot else 0.0
        q = prev_err_and_err / prev_err if prev_err else 0.0
        return p, q, prev_err
    p, q, npairs = agg(seqs)
    rng = random.Random(seed)
    diffs = []
    for _ in range(boot):
        pick = [seqs[rng.randrange(len(seqs))] for _ in range(len(seqs))] if seqs else []
        p2, q2, n2 = agg(pick)
        if n2:
            diffs.append(q2 - p2)
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))] if diffs else 0.0
    hi = diffs[int(0.975 * len(diffs)) - 1] if diffs else 0.0
    errs = sum(1 for s in seqs for x in s if x)
    hits = sum(1 for s in seqs for i in range(1, len(s)) if s[i - 1] and s[i])
    return {"words": sum(len(s) for s in seqs), "items": len(seqs), "pairs": npairs,
            "errs": errs, "hits": hits, "p": p, "q": q, "diff": q - p, "ci": (lo, hi)}


def statuses(items, hyps, scorer, cfg_of):
    """‏[بندٌ] ⇒ قائمةُ «أخطأ؟» بترتيب كلمات المرجع — بالحاكم نفسِه لا بمسطرةٍ أخرى."""
    BAD = {scorer.MISSED, scorer.SUBSTITUTED}
    out = []
    for it in items:
        h = hyps.get(it["id"]) or {}
        if h.get("text") is None or "error" in h:
            continue
        sc = scorer.score(it["refText"].split(), h["text"], cfg_of(it))
        ws = [w for w in sc.get("words", []) if w]
        if len(ws) >= 4:                      # بندٌ أقصرُ من ذلك لا شرطيّةَ فيه تُقرأ
            out.append([w[1] in BAD for w in ws])
    return out


def run(dirs, arms, sets):
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
    import scorer as SCR
    import v2_gate as G
    import score as SC

    # ⛔ **بإعداد الحاكم نفسِه الذي يحكم به الشوط** (`score.config_for("proposed", riwaya)`)
    #    لا بإعدادٍ افتراضيّ: `scorer.DEFAULT` **ليس المشحون** (‏درسُ D-276) ⇒ قياسٌ بمسطرةٍ
    #    غيرِ مسطرة المحرك يعطي رقماً معقولاً وخاطئاً.
    def cfg_of(it):
        return SC.config_for("proposed", it.get("riwaya"))
    print("# 🌊 جرفُ الخطأ في التلاوة الطويلة — **شرطيّةٌ مقابل هامشيّة**\n")
    # ⛔ **وتُطبع الأعدادُ الخامّةُ لا النسبُ وحدَها** (‏درسٌ من أوّل قراءةٍ 22:56Z): جاءت
    #    الشرطيّةُ **متساويةً إلى أربعة أرقامٍ** في الذراعَين (50.12٪) فاشتبه أنّ ملفّاً واحداً
    #    قُرئ مرّتَين — ولا يُنشر رقمٌ مشتبَهٌ. ⇒ العددُ يفصل: أعدادٌ مختلفةٌ بنسبةٍ واحدةٍ
    #    **مصادفةٌ**، وأعدادٌ متطابقةٌ **عطبٌ**.
    print("| المجموعة | الذراع | بنودٌ | كلماتٌ | أخطاءٌ | أزواجٌ (سابقُها خطأ) | منها خطأٌ | "
          "p (هامشيّة) | **q (شرطيّة)** | الفرق | مجال 95٪ |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    any_row = False
    for d in dirs:
        G.WORK = d
        pool = G.pool_items()
        for st in sets:
            for arm in arms:
                hyps = G.load_hyps(st if st.startswith(("g1", "g4")) else st.replace("-", ":", 1), arm)
                if not hyps:
                    continue
                items = [it for it in pool if it["id"] in hyps]
                if not items:
                    print(f"| `{st}` | `{arm}` | — | — | — | — | — | — | — | ⛔ بلا مرجع | — |")
                    continue
                seqs = statuses(items, hyps, SCR, cfg_of)
                if not seqs:
                    print(f"| `{st}` | `{arm}` | 0 | — | — | — | — | — | — | ⛔ لا بندَ صالحاً | — |")
                    continue
                s = drift_stats(seqs)
                any_row = True
                print(f"| `{st}` | `{arm}` | {s['items']} | {s['words']} | {s['errs']} | "
                      f"{s['pairs']} | {s['hits']} | {s['p']*100:.2f}٪ | "
                      f"**{s['q']*100:.2f}٪** | **{s['diff']*100:+.2f}** | "
                      f"[{s['ci'][0]*100:+.2f} .. {s['ci'][1]*100:+.2f}] |")
    if not any_row:
        print("| — | — | — | — | — | — | — | — | — | ⛔ لا فرضيّاتٍ تُقرأ | — |")
        return 1
    print("\n⭐ **كيف يُقرأ:** q ≈ p ⇒ **أخطاءٌ مستقلّةٌ** فالعلاجُ في السمع · q ≫ p ⇒ **جرفٌ** "
          "فالعلاجُ في التقطيع أو إعادة الإرساء. ⚠️ **وهذا تجاورٌ لا سببيّة**: موضعٌ صعبٌ "
          "يُعطي تجاوراً بلا انحدارٍ ذاتيّ ⇒ **مُرجِّحٌ لا برهان**.")
    print("⭐ **ولا سياقَ يُحمَل بين المجموعات أصلاً** (‏`LongAudioTranscriber` يفرّغ كلَّ مجموعةٍ "
          "وحدَها) ⇒ الجرفُ — إن وُجد — **داخلَ المجموعة**، ولا يُقترح إلغاءُ حملٍ غيرِ قائم.")
    return 0


def selftest():
    """⛔ المسطرةُ تُختبر بحالاتٍ **تُعرف أجوبتُها** قبل أن يُقاس بها شيء."""
    n = 40
    # ① أخطاءٌ مستقلّةٌ باحتمالٍ 0.3 ⇒ q ≈ p
    rng = random.Random(3)
    ind = [[rng.random() < 0.3 for _ in range(30)] for _ in range(n)]
    a = drift_stats(ind)
    assert abs(a["diff"]) < 0.08, a
    # ② جرفٌ صريح: أوّلُ خطإٍ ثمّ كلُّ ما بعده خطأ ⇒ q ≈ 1 وp ≈ 0.5
    dr = []
    for _ in range(n):
        k = rng.randrange(5, 25)
        dr.append([False] * k + [True] * (30 - k))
    b = drift_stats(dr)
    assert b["q"] > 0.95 and b["diff"] > 0.4 and b["ci"][0] > 0.3, b
    # ③ تناوبٌ صارم (خطأٌ ثمّ صوابٌ) ⇒ **شرطيّةٌ صفرٌ** وهي أقلُّ من الهامشيّة (نقيضُ الجرف)
    alt = [[i % 2 == 0 for i in range(30)] for _ in range(n)]
    c = drift_stats(alt)
    assert c["q"] == 0.0 and c["diff"] < -0.4, c
    # ④ بلا أخطاءٍ البتّة ⇒ لا أزواجَ ولا انفجار
    z = drift_stats([[False] * 10 for _ in range(5)])
    assert z["pairs"] == 0 and z["q"] == 0.0, z
    print(f"✅ اختبارٌ ذاتيّ: مستقلٌّ (فرق {a['diff']*100:+.1f}) · جرفٌ ({b['diff']*100:+.1f}) · "
          f"تناوبٌ ({c['diff']*100:+.1f}) · وخالٍ من الأخطاء (بلا أزواج)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", default="work:", help="مجلداتُ الفرضيّات (‏`work:` كصيغة التشريح)")
    ap.add_argument("--arms", default="")
    ap.add_argument("--sets", default="g4n g4")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    dirs = [p.split(":", 1)[0] for p in a.dirs.split()] or ["work"]
    dirs = [d if os.path.isabs(d) else os.path.join(HERE, d) for d in dirs]
    arms = a.arms.split()
    if not arms:
        raise SystemExit("⛔ يلزم `--arms` — ولا يُقاس جرفٌ بلا ذراعٍ تُقرأ")
    return run(dirs, arms, a.sets.split())


if __name__ == "__main__":
    sys.exit(main())
