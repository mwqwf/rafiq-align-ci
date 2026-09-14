# -*- coding: utf-8 -*-
"""قياس المحاكي: يحوّل مخرج مسبار `RafiqBatch` إلى hyps ويقيسه بالمقياس نفسه.

القيمة: هذا **مسار المحرك الحقيقي** (‏LongAudioTranscriber → whisper.cpp عبر
JNI على أندرويد)، لا مرآته على الخادم. فهو يجيب سؤالين: هل الدقة على الجهاز
كالخادم؟ وكم زمن الاستجابة الفعلي للمستخدم؟

الزمن يُشتق من **طوابع logcat**: الفارق بين سطر البند وسطر ما قبله = زمن
تفريغه (والسطر الأول من `start`). فيه تحميل النموذج مرة واحدة (سطر start
← أول بند) فيُستبعد من الوسيط ويُذكر وحده.

    adb logcat -d -s RafiqBatch > work/emu_batch.txt
    python tools/tasmi_bench/emu_score.py
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from score import aggregate, by_key, load_sample, run  # noqa: E402

LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\d+\s+\d+\s+I RafiqBatch: (.*)$")


def parse(path):
    """يعيد (hyps, loadMs) — hyps بصيغة ملفات الخادم نفسها."""
    hyps, prev, load_ms = {}, None, None
    for raw in open(path, encoding="utf-8", errors="replace"):
        m = LINE.match(raw.rstrip("\n"))
        if not m:
            continue
        t = dt.datetime.strptime("2026-" + m.group(1), "%Y-%m-%d %H:%M:%S.%f")
        body = m.group(2)
        if body.startswith("start "):
            prev = t
            continue
        if body.startswith("done"):
            break
        if "\t" not in body:
            continue
        name, text = body.split("\t", 1)
        ms = int((t - prev).total_seconds() * 1000) if prev else None
        if load_ms is None:
            load_ms, ms = ms, None      # أول بند يحمل زمن تحميل النموذج معه
        prev = t
        hyps[name[:-4]] = {"text": text.strip(), "ms": ms}
    return hyps, load_ms


def anomalies(hyps):
    """يعيد قائمةَ ما **يُفسد الزمنَ** في مخرَجٍ مقروء — تُطبع ولا تُبتلع.

    ⛔ **ثلاثُ حالاتٍ مقيسةٌ في هذا الملفّ نفسِه (2026-09-14 · D-434)، كلُّها تُخرج رقماً
    يُقرأ ولا تُخرج خطأً يُوقف:**
    1. **زمنٌ سالب** — الطوابعُ بلا سنة، والسنةُ تُلصق ثابتةً (`"2026-"`) ⇒ شوطٌ يعبر رأسَ
       السنة (12-31 ⇒ 01-01) يعطي **‎−31,535,998,000م.ث** لبندٍ واحدٍ فيسحب الوسيطَ معه.
    2. **بندان بلا زمنٍ لا بندٌ واحد** — علامةُ **غياب سطر `start`**: فيبتلع «تحميلُ
       النموذج» زمنَ البند الثاني، ويُقرأ **زمنُ تفريغٍ** على أنّه زمنُ تحميل.
    3. **لا بندَ أصلاً** — لا خضرةَ بلا شهادة: صفرُ بنودٍ يُقال ولا يُقرأ «مطابقةٌ تامّة».
    ⭐ **ولا يُصلَح الرقمُ هنا** (‏الإصلاحُ يغيّر معنى مخرَجٍ يقرؤه غيري) — **يُعلَن**.
    """
    out = []
    neg = sorted(k for k, v in hyps.items() if (v.get("ms") or 0) < 0)
    if neg:
        out.append(f"⛔ زمنٌ سالبٌ في {len(neg)} بنداً (‏{neg[0]}…) — طابعٌ عبَر رأسَ السنة؟ "
                   "⇒ **لا يُقرأ وسيطُ الزمن**")
    blank = [k for k, v in hyps.items() if v.get("ms") is None]
    if len(blank) > 1:
        out.append(f"⛔ {len(blank)} بنداً بلا زمنٍ (والسويُّ واحدٌ) — سطرُ `start` مفقودٌ؟ "
                   "⇒ **زمنُ التحميل ليس زمنَ تحميل**")
    if not hyps:
        out.append("⛔ صفرُ بنودٍ في الأثر — لا يُقرأ هذا نجاحاً")
    return out


# ---- 🧪 اختبارٌ ذاتيٌّ (أُضيف 2026-09-14 · مناوبةُ :13) ----
# ⛔ **لِمَ:** من `parse` يخرج **كلُّ رقمِ زمنٍ على المحرك الحقيقيّ** (‏الجهازُ لا المرآة)،
# وقواعدُه **ضمنيّةٌ تُقرأ خطأً**: البندُ الأوّلُ يتبرّع بزمنه لتحميل النموذج · والفارقُ من
# الطابع السابق لا من بدايةٍ ثابتة · و`done` يقطع · والمكرَّرُ يغلب الأوّلَ صامتاً.
# ⭐ والقيمُ أدناه **مقيسةٌ من الدالّة نفسِها** قبل كتابتها لا مفترَضة.
def _log(lines):
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "emu.txt")
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return p


def _ln(ts, body):
    return f"{ts}  1234  1234 I RafiqBatch: {body}"


def selftest():
    bad = 0

    def ok(name, got, want):
        nonlocal bad
        good = got == want
        print(f"  {'✅' if good else '⛔'} {name}: {got} · المتوقَّع {want}")
        bad += 0 if good else 1

    h, load = parse(_log([
        _ln("09-14 01:00:00.000", "start 3"),
        _ln("09-14 01:00:02.500", "a_001001.wav\tالحمد لله"),
        _ln("09-14 01:00:03.000", "b_001002.wav\tمالك يوم الدين"),
        _ln("09-14 01:00:03.750", "c_001003.wav\tإياك نعبد"),
        _ln("09-14 01:00:04.000", "done"),
    ]))
    ok("الاسمُ يُقشَر من `.wav`", sorted(h), ["a_001001", "b_001002", "c_001003"])
    # ⭐ **الأوّلُ يتبرّع بزمنه:** فيه تحميلُ النموذج ⇒ يخرج من الوسيط ويُذكر وحدَه.
    ok("زمنُ التحميل من البند الأوّل وزمنُه يُلغى", (load, h["a_001001"]["ms"]), (2500, None))
    ok("والزمنُ فارقٌ عن سابقه لا عن البداية",
       (h["b_001002"]["ms"], h["c_001003"]["ms"]), (500, 750))
    ok("والنصُّ يُقلَّم", h["b_001002"]["text"], "مالك يوم الدين")
    ok("وسويٌّ ⇒ لا منبِّه", anomalies(h), [])

    # ⛔ **بلا `start`:** بندان يفقدان زمنَهما و«التحميلُ» يصير زمنَ تفريغٍ حقيقيّ.
    h2, load2 = parse(_log([
        _ln("09-14 01:00:02.500", "a_001001.wav\tنصٌّ"),
        _ln("09-14 01:00:03.000", "b_001002.wav\tنصٌّ"),
        _ln("09-14 01:00:03.500", "c_001003.wav\tنصٌّ"),
    ]))
    ok("بلا `start` ⇒ بندان بلا زمنٍ و«تحميلٌ» كاذب",
       (h2["a_001001"]["ms"], h2["b_001002"]["ms"], h2["c_001003"]["ms"], load2),
       (None, None, 500, 500))
    ok("والمنبِّهُ يمسكها", len(anomalies(h2)), 1)

    # ⛔ **ورأسُ السنة**: السنةُ ملصقةٌ ثابتةً ⇒ فارقٌ سالبٌ بمقدار سنة.
    h3, _ = parse(_log([
        _ln("12-31 23:59:58.000", "start 2"),
        _ln("12-31 23:59:59.000", "a_001001.wav\tقبل"),
        _ln("01-01 00:00:01.000", "b_001002.wav\tبعد"),
    ]))
    ok("عبورُ رأس السنة ⇒ زمنٌ سالبٌ مقيس", h3["b_001002"]["ms"], -31535998000)
    # ⚠️ ومنبِّهٌ **واحدٌ** لا اثنان: البندُ الأوّلُ بلا زمنٍ **سويٌّ** (تبرّع به للتحميل)،
    #    فلا يُعَدّ «بلا زمن» — قِيس فصُحّح توقُّعي قبل أن يُكتب.
    ok("والمنبِّهُ يمسكه وحدَه", (len(anomalies(h3)), anomalies(h3)[0][:12]), (1, "⛔ زمنٌ سالبٌ"))
    ok("وصفرُ بنودٍ يُقال", anomalies({}), ["⛔ صفرُ بنودٍ في الأثر — لا يُقرأ هذا نجاحاً"])

    h4, _ = parse(_log([
        _ln("09-14 01:00:00.000", "start 2"),
        _ln("09-14 01:00:01.000", "a_001001.wav\tأوّل"),
        _ln("09-14 01:00:01.500", "done"),
        _ln("09-14 01:00:02.000", "b_001002.wav\tبعد done"),
    ]))
    ok("و`done` يقطع ما بعده", sorted(h4), ["a_001001"])

    # ⚠️ **والمكرَّرُ يغلب الأوّلَ صامتاً** — يُثبَّت كي يُعلم، فإعادةُ بندٍ تعني آخرَ قراءةٍ له.
    h5, _ = parse(_log([
        _ln("09-14 01:00:00.000", "start 2"),
        _ln("09-14 01:00:01.000", "a_001001.wav\tالأوّل"),
        _ln("09-14 01:00:02.000", "a_001001.wav\tالثاني"),
    ]))
    ok("ومعرّفٌ مكرَّرٌ ⇒ الأخيرُ يغلب", (len(h5), h5["a_001001"]["text"]), (1, "الثاني"))

    h6, _ = parse(_log([
        _ln("09-14 01:00:00.000", "start 1"),
        "09-14 01:00:01.000  1 1 I Other: سطرُ وسمٍ آخر",
        _ln("09-14 01:00:01.500", "سطرٌ بلا جدولة"),
        _ln("09-14 01:00:02.000", "a_001001.wav\tنصٌّ"),
    ]))
    ok("وسطرٌ لوسمٍ آخرَ أو بلا جدولةٍ لا يُزحزح الطابع", h6["a_001001"]["ms"], None)

    print("✅ القارئُ سليمٌ على حالاته" if not bad else f"⛔ القارئُ نفسُه معطوبٌ في {bad} حالة")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="يختبر قارئَ الأثر على حالاتٍ مقيسة")
    ap.add_argument("--log", default=os.path.join(HERE, "work", "emu_batch.txt"))
    ap.add_argument("--server", default=os.path.join(HERE, "work", "hyps_ar_win.json"))
    ap.add_argument("--cfg", default="proposed", choices=["shipped", "proposed"])
    args = ap.parse_args()
    if args.selftest:
        raise SystemExit(selftest())

    hyps, load_ms = parse(args.log)
    for w in anomalies(hyps):        # ⛔ ما يُفسد الزمنَ يُعلَن قبل أن يُقرأ الرقم
        print(w)
    sample = load_sample()
    subset = [i for i in sample["items"] if i["id"] in hyps]
    # مدة الصوت تُستعار من تشغيل الخادم (الملف الصوتي نفسه بالبصمة نفسها)
    srv = json.load(open(args.server, encoding="utf-8"))["hyps"]
    for it in subset:
        hyps[it["id"]]["audioMs"] = srv[it["id"]].get("audioMs")

    res = run(subset, hyps, args.cfg)
    a = aggregate(res)
    print(f"══ المحاكي (مسار المحرك) · {args.cfg} · {len(subset)} آية حفص ══")
    print(f"  الدقة: {a['accuracy']*100:.2f}% [{a['ci95'][0]*100:.2f}–{a['ci95'][1]*100:.2f}]"
          f" · {a['correct']}/{a['words']} كلمة")
    lat = sorted(r["ms"] for r in res if r["ok"] and r.get("ms"))
    print(f"  زمن الاستجابة: وسيط {lat[len(lat)//2]}م.ث · أدنى {lat[0]} · أعلى {lat[-1]}"
          f" · p90 {lat[int(0.9*len(lat))-1]}")
    print(f"  RTF وسيط {a['rtfMedian']:.3f} · تحميل النموذج مرة واحدة ≈{load_ms}م.ث")
    # مقارنة بالخادم على البنود نفسها
    res_srv = run(subset, srv, args.cfg)
    b = aggregate(res_srv)
    print(f"  الخادم على البنود نفسها: {b['accuracy']*100:.2f}%"
          f" · وسيط {b['latencyMsMedian']}م.ث")
    same = sum(1 for x, y in zip(res, res_srv) if x["ok"] and y["ok"] and x["hyp"] == y["hyp"])
    print(f"  تطابق نصّ التفريغ حرفياً بين الجهاز والخادم: {same}/{len(subset)}")
    print(f"  حسب الطبقة: " + " · ".join(f"{k} {v['accuracy']*100:.1f}% ({v['items']})"
                                         for k, v in sorted(by_key(res, "stratum").items())))


if __name__ == "__main__":
    main()
