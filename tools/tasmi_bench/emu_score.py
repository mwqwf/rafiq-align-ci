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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=os.path.join(HERE, "work", "emu_batch.txt"))
    ap.add_argument("--server", default=os.path.join(HERE, "work", "hyps_ar_win.json"))
    ap.add_argument("--cfg", default="proposed", choices=["shipped", "proposed"])
    args = ap.parse_args()

    hyps, load_ms = parse(args.log)
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
