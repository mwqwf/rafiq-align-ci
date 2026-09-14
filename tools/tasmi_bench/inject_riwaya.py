# -*- coding: utf-8 -*-
"""🔪 **مجموعةُ حقنٍ لورشٍ وقالون** — نظيرةُ `inject.py` الحفصيّة.

⚠️ **لِمَ وُجدت:** `inject_plan.json` الحفصيّة **حفصٌ خالصٌ كلُّها** (‏160 بنداً، صفرُ ورشٍ
وقالون). فكانت بوّابةُ الإنذار الكاذب **عمياءَ عن الروايتين** اللتين ضُبط لهما النموذجُ الثاني،
فحُكم عليه بما لم يُقَس فيه. (‏2026-09-08 — وهو نظيرُ الدرس: لا يُحكم بعيّنةٍ جزئية.)

**المصدر:** فهارسُ توقيتات الكلمات من جلسة الفهرسة `github-17`:
`wordtimings/<riwaya>/husary_<riwaya>.jz` على R2.

⭐ **والقارئُ واحدٌ في الروايات الثلاث** (الحصريّ) — وهو أيضاً صاحبُ `segments_husary.jz`
الحفصيّة. ⇒ **الصوتُ ثابتٌ والروايةُ وحدَها تتغيّر**، فأيُّ فارقٍ يظهر يُنسب إليها لا إلى
اختلاف القارئ. (ضبطُ متغيّرٍ نبّهت إليه جلسةُ الفهرسة ولم أطلبه.)

⛔ **ثلاثةُ قيودٍ من ترويسة الفهرس، وإهمالُ أوّلِها يُفسد القياس كلَّه:**

1. **`endsPolicy: contiguous`** — `startMs` **ليس بدايةً مقيسة** بل نهايةَ الكلمة السابقة،
   والنهاياتُ ملصوقةٌ عمداً. ⇒ **لا حشوةَ في الأمام أبداً**: حشوةٌ عند القطع تسحب ذيلَ الجارة
   إلى المقطع، **فتقيس البوّابةُ إنذاراً كاذباً سببُه السكّينُ لا النموذج**.
2. **`fullEvidence: true` شرطٌ لازم** — وإلا فبعضُ الحدود مستنتَجٌ لا مقيس.
3. **التغطيةُ جزئية** — جزءُ 30 أوثقُها (‏449/463 ورشاً · 524/527 قالوناً)، والكهفُ صفرٌ في
   ورش. ⇒ تُؤخذ السورُ 78 فما فوق، وهي أيضاً **ملفّاتٌ صغيرة** فلا تُثقل شبكةَ المالك.

    python tools/tasmi_bench/inject_riwaya.py            # يبني الخطّة
"""
import argparse
import gzip
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
from common import load_index, load_text  # noqa: E402

SEED = 1446
PER_OP = 20                 # لكل رواية ⇒ 4 عمليات × 20 × روايتان = 160 بنداً
MIN_WORDS, MAX_WORDS = 5, 20
MIN_WORD_MS = 200           # مقطعٌ أقصر ملتبسُ الحدّ
FIRST_SURAH = 78            # جزءُ 30 — أوثقُ تغطيةً وأخفُّ تنزيلاً

R2 = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/"
AUDIO = {
    "warsh": "https://server13.mp3quran.net/husr/Rewayat-Warsh-A-n-Nafi/",
    "qalun": "https://server13.mp3quran.net/husr/Rewayat-Qalon-A-n-Nafi/",
}


def load_timings(riwaya, work):
    """ينزّل فهرسَ التوقيتات مرّةً واحدة ويكيشه (شبكةُ المالك موردٌ شحيح)."""
    name = f"husary_{riwaya}.jz"
    dst = os.path.join(work, name)
    if not os.path.isfile(dst):
        import urllib.request
        op = urllib.request.build_opener()
        op.addheaders = [("User-Agent", "Mozilla/5.0 (QuranRafiq tools)")]
        os.makedirs(work, exist_ok=True)
        with op.open(R2 + f"wordtimings/{riwaya}/{name}", timeout=180) as r, open(dst, "wb") as o:
            o.write(r.read())
    d = json.loads(gzip.open(dst, "rt", encoding="utf-8").read())
    assert d["endsPolicy"] == "contiguous", d["endsPolicy"]  # ⛔ حارسُ الافتراض
    return d


def bounds(words):
    """حدودُ كل كلمةٍ بترتيبها. ⛔ بلا حشوة — النهاياتُ ملصوقة (`contiguous`)."""
    out = {}
    for w in words:
        i = int(w["wordId"].split(":")[2]) - 1
        a, b = w["startMs"], w["endMs"]
        if i in out:                      # كلمةٌ ذاتُ مقاطع (`subIndex`)
            a, b = min(a, out[i][0]), max(b, out[i][1])
        out[i] = (a, b)
    return [out[i] for i in sorted(out)]


def eligible(d, text, start, first_surah):
    """المسبحُ المؤهَّل لنطاقِ سورٍ — **بالشروط الثلاثة نفسِها** التي يبني بها البانّي.

    ⛔ **ولا تُليَّن شرطاً لتكبيره**: `fullEvidence` حدُّ صدقِ التوقيت، ومطابقةُ عدد الكلمات
    حدُّ صدقِ الاقتران بالنصّ، و‎5..20 كلمةً حدُّ البند المقيس. تكبيرُ المسبح **بنطاقٍ أوسعَ**
    وحدَه — وذلك ثمنُه تنزيلُ ملفّاتِ سورٍ أكبرَ لا تليينُ شرط.
    """
    pool = []
    for e in d["entries"]:
        if not e["evidence"].get("fullEvidence"):
            continue
        s, a = map(int, e["ayahId"].split(":"))
        if s < first_surah:
            continue
        ref = text[start[s] + a - 1].split()
        wb = bounds(e["words"])
        if len(wb) != len(ref) or not (MIN_WORDS <= len(ref) <= MAX_WORDS):
            continue
        pool.append((s, a, ref, wb))
    return pool


def audit(work):
    """🗺️ **قياسُ التغطية قبل التوسيع** — كم يزيد المسبحُ لو وُسِّع النطاقُ تحت جزء 30، وبأيّ ثمن؟

    ⛔ **لِمَ وُجد:** سقفُ خطّة الحقن **256 بنداً** في جزء 30 (‏ورشٌ 128 · قالونُ 146)، وكُتب في
    دفتر المناوبة أنّ ما فوقَه **يحتاج نطاقَ سورٍ أوسعَ بقياس تغطيةٍ أوّلاً**. وهذا هو القياس:
    ⭐ **لا يُوسَّع نطاقٌ بالظنّ** — فترويسةُ الفهرس تقول إنّ التغطية **جزئيّةٌ** وإنّ الكهفَ
    **صفرٌ في ورش**، فالسورةُ قد تكون في الفهرس ولا بندَ فيها البتّة.
    ⚠️ **وهذا كشفٌ لا شحنٌ:** مخرَجُه جدولٌ يُقرأ، ولا يكتب خطّةً ولا يبدّل `FIRST_SURAH`.
    """
    index = load_index()
    start = {s["n"]: s["start"] for s in index["surahs"]}
    scopes = [(78, "جزء 30 (المقيسُ اليومَ)"), (67, "جزءا 29–30"), (50, "الأجزاء 26–30"),
              (36, "الأجزاء 23–30"), (1, "المصحفُ كلُّه")]
    pools, per_surah, cover = {}, {}, {}
    for riwaya in ("warsh", "qalun"):
        d = load_timings(riwaya, work)
        text = load_text(riwaya)
        full = sum(1 for e in d["entries"] if e["evidence"].get("fullEvidence"))
        cover[riwaya] = (full, len(d["entries"]))
        pools[riwaya] = eligible(d, text, start, 1)
        for s, a, ref, wb in pools[riwaya]:
            per_surah.setdefault(s, {"warsh": 0, "qalun": 0})[riwaya] += 1

    print("## 🗺️ سقفُ مسبحِ الحقن الروائيّ بحسب نطاق السور — **قياسٌ لا ظنّ**\n")
    for r, (f, n) in cover.items():
        print(f"- `{r}`: **{f}** آيةً كاملةَ الأدلّة من **{n}** في الفهرس كلِّه "
              f"(‏{100.0*f/max(n,1):.1f}٪) · والمؤهَّلُ منها بشروط البند **{len(pools[r])}**.")
    print("\n| النطاق | ورش | قالون | المجموع | ⬆️ فوق المقيس | 📥 ملفّاتُ سورٍ تُنزَّل |")
    print("|---|---:|---:|---:|---:|---:|")
    base = None
    for first, name in scopes:
        w = sum(1 for p in pools["warsh"] if p[0] >= first)
        q = sum(1 for p in pools["qalun"] if p[0] >= first)
        files = len({p[0] for p in pools["warsh"] if p[0] >= first}) + \
                len({p[0] for p in pools["qalun"] if p[0] >= first})
        base = base if base is not None else w + q
        print(f"| {name} (‏س≥{first}) | {w} | {q} | **{w + q}** | {w + q - base:+d} | {files} |")
    print("\n⚠️ **والمسبحُ ليس بنوداً**: البندُ يستهلك آيةً كاملةً (‏آيتان في آيةٍ واحدةٍ ليستا "
          "شاهدَين مستقلَّين)، ويسقط منه ما كانت كلمتُه الداخليّةُ أقصرَ من "
          f"{MIN_WORD_MS} م.ث أو لم يُوجد له مانحٌ ⇒ **السقفُ أعلى من المُنتَج دائماً**.")
    print("⛔ **والثمنُ يُقرأ في العمود الأخير**: كلُّ ملفِّ سورةٍ تنزيلٌ في كلِّ شوطٍ يبني "
          "المجموعات، وسورُ أوائل المصحف **أثقلُ** من قِصار جزء 30 بمراتب.\n")
    rows = [(s, v["warsh"], v["qalun"]) for s, v in per_surah.items() if s < 78]
    rows.sort(key=lambda r: -(r[1] + r[2]))
    print("### وأغنى السور تحت جزء 30 (‏أوّلُ 15) — ⭐ **والفارغةُ منها لا تُدخَل بالظنّ**\n")
    print("| السورة | ورش | قالون |")
    print("|---:|---:|---:|")
    for s, w, q in rows[:15]:
        print(f"| {s} | {w} | {q} |")
    zero = [s for s, v in per_surah.items() if (v["warsh"] == 0) != (v["qalun"] == 0)]
    if zero:
        print(f"\n⛔ و**{len(zero)}** سورةً مؤهَّلةٌ في روايةٍ وصفرٌ في الأخرى "
              f"(‏أوّلُها: {' · '.join(str(s) for s in sorted(zero)[:8])}) ⇒ **نطاقٌ يُدخَل "
              "لا يعني بندَين متوازيَين** — والتوازنُ بين الروايتين يُقاس لا يُفترض.")
    return 0


def selftest():
    """🧪 **حارسُ صانع مادّة القياس** — بلا شبكةٍ ولا فهارسَ ولا صوت (‏D-498).

    ⛔⛔ **ولماذا يلزم قبل غيره:** هذا الملفُّ **يصنع البنودَ** التي تُقاس عليها بوّابةُ
    الاتّهام الكاذب في ورشٍ وقالون. فخطؤه **لا يُرى في شوطٍ أحمر**: خطّةٌ فيها حشوةٌ عند
    القطع، أو كلمةٌ طرفيّةٌ بدل داخليّة، أو بندان في آيةٍ واحدة — **تعطي أرقاماً تبدو سليمةً
    وهي تقيس السكّينَ لا النموذج**. ⇒ تُثبَّت القيودُ المكتوبةُ في رأس الملفّ **سلوكاً**.
    """
    import tempfile
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ① `bounds`: الكلمةُ ذاتُ المقاطع تُجمع (أدنى بدايةٍ وأقصى نهاية) وتُرتَّب بالفهرس
    ws = [{"wordId": "78:5:2", "startMs": 900, "endMs": 1400},
          {"wordId": "78:5:1", "startMs": 100, "endMs": 500},
          {"wordId": "78:5:2", "startMs": 1400, "endMs": 1900}]   # مقطعٌ ثانٍ للكلمة 2
    say(bounds(ws) == [(100, 500), (900, 1900)],
        f"حدودُ الكلمات: المقاطعُ تُجمع وتُرتَّب بالفهرس ⇒ {bounds(ws)}")

    # ② `eligible`: الشروطُ الثلاثةُ تردّ كلٌّ على حدة — **ولا يُليَّن شرطٌ لتكبير المسبح**
    text = ["كلمةٌ " * 0] * 0
    fake_text = [" ".join(f"w{a}_{k}" for k in range(8)) for a in range(1, 6)]
    start = {78: 0}

    def entry(ayah, nwords=8, full=True, surah=78):
        return {"ayahId": f"{surah}:{ayah}", "evidence": {"fullEvidence": full},
                "words": [{"wordId": f"{surah}:{ayah}:{k+1}", "startMs": k * 500,
                           "endMs": (k + 1) * 500} for k in range(nwords)]}

    say(len(eligible({"entries": [entry(1)]}, fake_text, start, 78)) == 1, "البندُ السويُّ يدخل المسبح")
    say(eligible({"entries": [entry(1, full=False)]}, fake_text, start, 78) == [],
        "⛔ و`fullEvidence: false` يُردّ — فبعضُ الحدود مستنتَجٌ لا مقيس")
    say(eligible({"entries": [entry(1)]}, fake_text, start, 79) == [],
        "⛔ وما دون نطاق السور يُردّ (‏التغطيةُ جزئيّة)")
    say(eligible({"entries": [entry(1, nwords=7)]}, fake_text, start, 78) == [],
        "⛔ واختلافُ عدد الكلمات عن النصّ يُردّ — وهو حدُّ صدقِ الاقتران بالنصّ")
    short = [" ".join(f"w{k}" for k in range(4))]
    say(eligible({"entries": [entry(1, nwords=4)]}, short, start, 78) == [],
        f"⛔ وأقصرُ من {MIN_WORDS} كلماتٍ يُردّ — وحدُّ البند المقيس لا يُليَّن")

    # ③ بناءُ خطّةٍ كاملةٍ على مصحفٍ مصنوعٍ — بلا شبكةٍ ولا صوت
    global load_timings, load_index, load_text
    old = (load_timings, load_index, load_text)
    AY = 40
    body = [" ".join(f"w{a}_{k}" for k in range(8)) for a in range(1, AY + 1)]
    try:
        load_timings = lambda _r, _w: {"entries": [entry(a) for a in range(1, AY + 1)]}   # noqa: E731
        load_index = lambda: {"surahs": [{"n": 78, "start": 0}]}                          # noqa: E731
        load_text = lambda _r: list(body)                                                 # noqa: E731
        import contextlib, io
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "plan1.json")

            def build(out, extra=()):
                argv = sys.argv
                sys.argv = ["x", "--out", out, "--work", td, "--per-op", "2", *extra]
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        rc = main()
                finally:
                    sys.argv = argv
                return rc, json.load(open(out, encoding="utf-8"))

            rc, plan = build(p1)
            items = plan["items"]
            say(rc == 0 and len(items) == 16,
                f"خطّةٌ مبنيّةٌ: {len(items)} بنداً (‏روايتان × أربعُ عملياتٍ × 2)")
            say(plan.get("pad") == 0 and plan.get("endsPolicy") == "contiguous",
                "والترويسةُ تقول ما فعلت: `pad=0` و`contiguous`")
            # ⛔⛔ **بلا حشوةٍ البتّة**: القطعُ يساوي حدَّ الكلمة حرفاً
            bad_pad = [i for i in items if i["cutMs"] != [i["wordIndex"] * 500, (i["wordIndex"] + 1) * 500]]
            say(not bad_pad,
                "⛔ والقطعُ **بلا حشوة**: يساوي حدَّ الكلمة تماماً — والحشوةُ تسحب ذيلَ الجارة فتقيس السكّين")
            say(all(0 < i["wordIndex"] < i["wordCount"] - 1 for i in items),
                "والكلمةُ المحقونةُ **داخليّةٌ دائماً**: لا أولى ولا أخيرة")
            say(len({i["id"] for i in items}) == len(items), "والمعرّفاتُ فريدة")
            say(len({(i["riwaya"], i["surah"], i["ayah"]) for i in items}) == len(items),
                "⛔ ولا آيتان في بندَين — فبندان في آيةٍ يتشاركان الصوتَ فلا يستقلّان شاهدَين")
            ops = {}
            for i in items:
                ops[(i["riwaya"], i["op"])] = ops.get((i["riwaya"], i["op"]), 0) + 1
            say(set(ops.values()) == {2} and len(ops) == 8, f"والنصيبُ متساوٍ لكلّ عمليةٍ ورواية: {sorted(set(ops.values()))}")
            say(all("donor" in i for i in items if i["op"] in ("SUBSTITUTE", "INSERT")),
                "والمانحُ حاضرٌ في كلّ إبدالٍ وإقحام — وإلّا أُسقط البند")
            say(all(i["donor"]["word"] != i["targetWord"] for i in items if "donor" in i),
                "⛔ والمانحُ **كلمةٌ أخرى** لا نظيرةُ الهدف")

            # ④ الحتميّة: البذرةُ ثابتةٌ ⇒ الخطّةُ نفسُها حرفاً
            p2 = os.path.join(td, "plan2.json")
            _, plan2 = build(p2)
            say(plan2["items"] == items, "والبذرةُ الثابتةُ تعطي الخطّةَ نفسَها حرفاً (حتميّةٌ لا حظّ)")

            # ⑤⭐ التوسيعُ **فائقٌ**: القائمُ يبقى بنصّه وترتيبه، ولا تُعاد آيةٌ استُعملت
            p3 = os.path.join(td, "plan3.json")
            argv = sys.argv
            sys.argv = ["x", "--out", p3, "--work", td, "--per-op", "3", "--extend", p1]
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc3 = main()
            finally:
                sys.argv = argv
            plan3 = json.load(open(p3, encoding="utf-8"))
            say(rc3 == 0 and plan3["items"][:16] == items,
                "⭐ التوسيعُ فائق: البنودُ القائمةُ **أوّلاً وبنصّها** فتُقارن العيّنتان")
            say(len(plan3["items"]) == 24, f"والمجموعُ {len(plan3['items'])} (‏2 ⇐ 3 لكلّ عمليةٍ ورواية)")
            say(len({(i["riwaya"], i["surah"], i["ayah"]) for i in plan3["items"]}) == len(plan3["items"]),
                "ولا آيةَ استُعملت تُؤخذ ثانيةً في التوسيع")

            # ⑥⛔ أصلٌ فيه معرّفٌ مكرَّرٌ لا يُبنى عليه
            bad = os.path.join(td, "bad.json")
            json.dump({"items": items + [items[0]]}, open(bad, "w", encoding="utf-8"), ensure_ascii=False)
            argv = sys.argv
            sys.argv = ["x", "--out", os.path.join(td, "p4.json"), "--work", td, "--extend", bad]
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    main()
                say(False, "أصلٌ مكرَّرُ المعرّف لم يُرفض")
            except SystemExit:
                say(True, "⛔ وأصلٌ فيه معرّفٌ مكرَّرٌ يُرفض — لا يُبنى على أصلٍ مشتبَه")
            finally:
                sys.argv = argv
    finally:
        load_timings, load_index, load_text = old

    print("\n" + ("✅ صانعُ المادّة يفعل ما يدّعي — بلا حشوةٍ ولا كلمةٍ طرفيّةٍ ولا آيةٍ مكرّرة"
                  if ok else "❌ صانعُ المادّة لا يفعل ما يدّعي"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="حارسٌ بلا شبكةٍ ولا فهارس")
    ap.add_argument("--audit", action="store_true",
                    help="🗺️ يقيس سقفَ المسبح بحسب نطاق السور ولا يكتب خطّةً البتّة")
    ap.add_argument("--out", default=os.path.join(HERE, "inject_plan_riwaya.json"))
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    ap.add_argument("--per-op", type=int, default=PER_OP,
                    help="عددُ البنود لكلِّ عمليةٍ في كلِّ رواية (الافتراضُ المقيسُ 20)")
    # ⛔⛔ **ولِمَ `--extend` ولا يُكتفى برفع `--per-op`** (‏درسُ D-415): المسبحُ يُمشى فيه
    # **بالترتيب** (‏`used` يتقدّم ولا يعود)، فرفعُ `PER_OP` يُطيل نصيبَ `OMIT` فيتزحزح
    # مبدأُ `SUBSTITUTE` ومَن بعده ⇒ **البنودُ القديمةُ نفسُها تتغيّر**، فلا تُقارن العيّنةُ
    # الكبرى بالصغرى ولا يُقال «العيّنةُ نفسُها موسَّعة». ⇒ **التوسيعُ فائقٌ (superset) أو لا يكون:**
    # تُحفظ البنودُ القائمةُ حرفاً وتُضاف إليها آياتٌ **لم تُستعمل** من المسبح عينِه.
    ap.add_argument("--extend", default="",
                    help="مسارُ خطّةٍ قائمةٍ تُحفظ بنودُها كما هي ويُبنى عليها (توسيعٌ فائق)")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.audit:
        return audit(args.work)

    keep, kept_ayat, kept_count = [], set(), {}
    if args.extend:
        old = json.load(open(args.extend, encoding="utf-8"))
        keep = old["items"]
        ids = [i["id"] for i in keep]
        if len(set(ids)) != len(ids):
            raise SystemExit("⛔ الخطّةُ القائمةُ فيها معرّفٌ مكرَّر — لا يُبنى على أصلٍ مشتبَه")
        for i in keep:
            kept_ayat.add((i["riwaya"], i["surah"], i["ayah"]))
            kept_count[(i["riwaya"], i["op"])] = kept_count.get((i["riwaya"], i["op"]), 0) + 1
        print(f"🧩 توسيعٌ فائقٌ فوق {len(keep)} بنداً قائماً ⇒ الهدفُ {args.per_op} لكلِّ عملية")

    index = load_index()
    start = {s["n"]: s["start"] for s in index["surahs"]}
    rng = random.Random(SEED)
    items = []
    census, deficit = {}, []

    for riwaya in ("warsh", "qalun"):
        d = load_timings(riwaya, args.work)
        text = load_text(riwaya)
        # ⛔ **المسبحُ من دالّةٍ واحدةٍ** (‏`eligible`) يتقاسمها البانّي والقياسُ (`--audit`):
        #    مسبحان بشرطَين متفرّقَين يجعلان السقفَ المُعلَن غيرَ السقف المبنيّ **بلا صراخ**.
        pool = eligible(d, text, start, FIRST_SURAH)
        rng.shuffle(pool)
        census[riwaya] = {"مسبحٌ مؤهَّل": len(pool),
                          "مستعمَلٌ سابقاً": sum(1 for p in pool if (riwaya, p[0], p[1]) in kept_ayat)}

        used = 0
        for op in ("OMIT", "SUBSTITUTE", "SWAP", "INSERT"):
            picked = kept_count.get((riwaya, op), 0)         # المحفوظُ يُحسب من النصيب
            target = max(args.per_op, picked)                 # ⛔ ولا يُنقَص محفوظٌ بحال
            while picked < target and used < len(pool):
                s, a, ref, wb = pool[used]
                used += 1
                # ⛔ آيةٌ في الخطّة القائمة **لا تُؤخذ ثانيةً**: بندان في آيةٍ واحدةٍ يتشاركان
                # الصوتَ نفسَه فلا يكونان شاهدَين مستقلَّين.
                if (riwaya, s, a) in kept_ayat:
                    continue
                wi = rng.randrange(1, len(ref) - 1)          # داخليّة: لا أولى ولا أخيرة
                a0, b0 = wb[wi]
                if b0 - a0 < MIN_WORD_MS:
                    continue
                it = {
                    "id": f"inj_{riwaya}_{op.lower()}_{s:03d}{a:03d}",
                    "op": op, "surah": s, "ayah": a, "wordIndex": wi,
                    "riwaya": riwaya, "reciter": f"husary_{riwaya}",
                    "refText": " ".join(ref), "wordCount": len(ref),
                    "targetWord": ref[wi],
                    "url": AUDIO[riwaya] + f"{s:03d}.mp3",
                    "ayahMs": [wb[0][0], wb[-1][1]],          # مدى الآية داخل ملفّ السورة
                    "cutMs": [a0, b0],                        # ⛔ بلا حشوة
                }
                if op == "SWAP":
                    if wi + 1 >= len(ref):
                        continue
                    a1, b1 = wb[wi + 1]
                    if b1 - a1 < MIN_WORD_MS:
                        continue
                    it["swapMs"] = [a1, b1]
                    it["targetWord"] = ref[wi] + " ↔ " + ref[wi + 1]
                if op in ("SUBSTITUTE", "INSERT"):
                    for _ in range(60):
                        sj, aj, refj, wbj = pool[rng.randrange(len(pool))]
                        j = rng.randrange(len(refj))
                        aj0, bj0 = wbj[j]
                        if refj[j] != ref[wi] and bj0 - aj0 >= MIN_WORD_MS:
                            it["donor"] = {
                                "url": AUDIO[riwaya] + f"{sj:03d}.mp3",
                                "cutMs": [aj0, bj0], "word": refj[j], "ayah": f"{sj}:{aj}",
                            }
                            break
                    if "donor" not in it:
                        continue
                items.append(it)
                picked += 1
            if picked < target:
                # ⛔ **والنقصُ يُسمّى برقمه:** «وُسِّعت الخطّة» وهي ناقصةٌ في صنفٍ حكمٌ كاذب،
                # والمسبحُ سقفٌ مقيسٌ لا يُتجاوز بتليينِ شرطٍ من شروط البند.
                deficit.append(f"{riwaya}/{op}: {picked} من {target}")

    out = keep + items
    ids = [i["id"] for i in out]
    if len(set(ids)) != len(ids):
        raise SystemExit("⛔ معرّفٌ مكرَّرٌ في الخطّة المبنيّة — لا تُكتب")
    # ⛔ **حارسُ التوسيع الفائق:** البنودُ القائمةُ **أوّلاً وبنصّها** — فإن تزحزحت واحدةٌ
    # فالعيّنتان مختلفتان ولا يُقارن رقمٌ برقم.
    if keep and out[:len(keep)] != keep:
        raise SystemExit("⛔ التوسيعُ ليس فائقاً: بندٌ قائمٌ تغيّر ⇒ لا تُكتب الخطّة")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"seed": SEED, "endsPolicy": "contiguous", "pad": 0,
                   "note": "⛔ بلا حشوةٍ عند القطع — النهاياتُ ملصوقة، والحشوةُ تسحب ذيلَ الجارة",
                   "items": out}, f, ensure_ascii=False, indent=1)
    print(f"✅ {len(out)} بنداً ({len(keep)} محفوظاً + {len(items)} جديداً) ⇒ {args.out}")
    import collections
    print("  الروايات:", dict(collections.Counter(i["riwaya"] for i in out)))
    print("  العمليات:", dict(collections.Counter(i["op"] for i in out)))
    print("  السور:", len({(i['riwaya'], i['surah']) for i in out}), "ملفَّ سورةٍ للتنزيل")
    print("  المسبح:", json.dumps(census, ensure_ascii=False))
    if deficit:
        print("⛔ نقصٌ عن المطلوب (سقفُ المسبح): " + " · ".join(deficit))
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
