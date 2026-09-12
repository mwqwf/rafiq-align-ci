# -*- coding: utf-8 -*-
"""📍 بنشمارك محدّد الموضع (QuranLocator) — 2026-09-06.

السؤال المقيس: **هل تكفي آيةٌ واحدة كاملة لمعرفة موضعها؟** (شكوى المالك: تلا آية نادرة
كاملة فقيل له «اقرأ أكثر»). يُشغَّل على تفريغات whisper الحقيقية للعيّنة (202 آية، 3 روايات،
7 قرّاء، `work/hyps_ar_win.json`) وعلى التلاوات المُخطئة المحقونة (`work/inj_hyps.json`) وعلى
حالاتٍ مركّبة من التفريغات نفسها:

  single      آية واحدة كما فُرِّغت
  basmala     البسملة قبلها (كما يبدأ كثيرون)
  half        النصف الأول من كلمات التفريغ (آية مقطوعة)
  pair        آيتان متتاليتان (تفريغ الآية + نصّ التالية مطبَّعاً — مركّب يُعلَن مركّباً)
  injected    تلاوة مُخطئة محقونة (حذف/إبدال/تبديل/زيادة) — يجب أن يبقى الموضع معروفاً
  noise       كلامٌ غير قرآني — يجب أن يُردّ null (إنذار كاذب إن حُدّد موضع)

المقياس: **إصابة** = startFlat == الآية (أو تشمل الآية داخل المدى بلا زيادة أكثر من آية)،
**null** = لم يُعرف، **خطأ** = حُدّد موضعٌ آخر (أسوأ من null).
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from common import load_text  # noqa: E402

import scorer  # noqa: E402
from locator import Locator  # noqa: E402

BASMALA = "بسم الله الرحمن الرحيم"
NOISE = [
    "صباح الخير كيف حالك اليوم يا صديقي",
    "أريد أن أذهب إلى السوق لأشتري الخبز والحليب",
    "الجو اليوم جميل جدا والشمس مشرقة",
    "هذا التطبيق يساعدني على الحفظ كل يوم",
    "اتصل بي غدا في الصباح الباكر من فضلك",
    "ذهب الولد إلى المدرسة ثم عاد إلى البيت",
    "الله أكبر الله أكبر لا إله إلا الله",
    "سبحان الله والحمد لله ولا إله إلا الله والله أكبر",
    "اللهم صل على محمد وعلى آل محمد كما صليت على إبراهيم",
    "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى",
    "أستغفر الله العظيم وأتوب إليه",
    "اللهم إني أسألك العفو والعافية في الدنيا والآخرة",
    "رضيت بالله ربا وبالإسلام دينا وبمحمد نبيا",
    "من كان يؤمن بالله واليوم الآخر فليقل خيرا أو ليصمت",
    "اللهم اغفر لي ولوالدي وللمؤمنين يوم يقوم الحساب",
    "أعوذ بالله من الشيطان الرجيم",
    "بسم الله الرحمن الرحيم",
    "الحمد لله رب العالمين والصلاة والسلام على أشرف المرسلين",
    "لا حول ولا قوة إلا بالله العلي العظيم",
    "سبحان الله وبحمده سبحان الله العظيم",
    "اللهم بارك لنا فيما رزقتنا وقنا عذاب النار",
    "الطالب يذهب إلى الجامعة كل صباح ويعود مساء",
    "اشتريت سيارة جديدة الأسبوع الماضي من المعرض",
]


def cfg_for(riwaya):
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=riwaya != "hafs")


def judge(res, flat, allow_extra=1):
    if res is None:
        return "null"
    s, e = res["start"], res["end"]
    if s == flat:
        return "hit"
    # متشابهٌ تامّ: الآيةُ الحقيقية بين البدائل المعلَنة — إصابةٌ (يُخبَر المستخدم لا يُخمَّن له)
    if flat in res.get("alternatives", []):
        return "hit"
    if s <= flat <= e and (e - s) <= allow_extra:
        return "hit"
    return "wrong"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="both", choices=["legacy", "current", "both"])
    ap.add_argument("--hyps", default=os.path.join(HERE, "work", "hyps_ar_win.json"))
    ap.add_argument("--inj", default=os.path.join(HERE, "work", "inj_hyps.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(HERE, "work", "locator_bench.json"))
    args = ap.parse_args()

    sample = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))["items"]
    hyps = json.load(open(args.hyps, encoding="utf-8"))["hyps"]
    inj = json.load(open(args.inj, encoding="utf-8"))["hyps"] if os.path.exists(args.inj) else {}
    mis = set()
    mp = os.path.join(HERE, "work", "misaligned.json")
    if os.path.exists(mp):
        mis = set(json.load(open(mp, encoding="utf-8")).get("exclude", []))
    items = [it for it in sample if it["id"] in hyps and it["id"] not in mis]
    if args.limit:
        items = items[:args.limit]

    texts = {}
    words = {}
    for r in ("hafs", "warsh", "qalun"):
        texts[r] = load_text(r)
        words[r] = [t.split(" ") for t in texts[r]]

    modes = ["legacy", "current"] if args.mode == "both" else [args.mode]
    report = {}
    for mode in modes:
        locs = {r: Locator(words[r], cfg_for(r), mode) for r in words}
        stats = defaultdict(lambda: defaultdict(int))
        details = []
        t0 = time.time()
        for it in items:
            r = it["riwaya"]
            flat = it["globalIndex"]
            hyp = hyps[it["id"]]["text"]
            cases = {"single": hyp, "basmala": BASMALA + " " + hyp}
            ws = hyp.split()
            if len(ws) >= 6:
                cases["half"] = " ".join(ws[: len(ws) // 2])
            if flat + 1 < len(texts[r]):
                cases["pair"] = hyp + " " + texts[r][flat + 1]
            for case, text in cases.items():
                res = locs[r].locate(text)
                v = judge(res, flat, allow_extra=1 if case != "pair" else 1)
                if case == "pair" and res is not None and res["start"] == flat and res["end"] == flat + 1:
                    v = "hit"
                stats[case][v] += 1
                stats[case + "/" + r][v] += 1
                stats[case + "/" + it["stratum"]][v] += 1
                details.append({"id": it["id"], "case": case, "verdict": v,
                                "got": None if res is None else [res["start"], res["end"]], "flat": flat})
        # المحقونة (خطة الحقن تحمل الموضع الحقيقي)
        plan = {}
        pp = os.path.join(HERE, "inject_plan.json")
        if os.path.exists(pp):
            plan = {it["id"]: it for it in json.load(open(pp, encoding="utf-8"))["items"]}
        for k, v in inj.items():
            it = plan.get(k)
            if it is None or not v.get("text"):
                continue
            res = locs[it["riwaya"]].locate(v["text"])
            vv = judge(res, it["globalIndex"])
            stats["injected"][vv] += 1
            stats["injected/" + it["op"].lower()][vv] += 1
            details.append({"id": k, "case": "injected", "verdict": vv,
                            "got": None if res is None else [res["start"], res["end"]], "flat": it["globalIndex"]})
        for n in NOISE:
            res = locs["hafs"].locate(n)
            stats["noise"]["null" if res is None else "false_alarm"] += 1
        dt = time.time() - t0
        report[mode] = {"stats": {k: dict(v) for k, v in stats.items()}, "seconds": round(dt, 1), "details": details}

        print(f"\n=== {mode} ({dt:.0f}s, {len(items)} آية) ===")
        for case in sorted(stats):
            d = stats[case]
            tot = sum(d.values())
            hit = d.get("hit", 0)
            print(f"{case:22s} n={tot:4d}  hit={hit:4d} ({100*hit/max(1,tot):5.1f}%)  null={d.get('null',0):3d}  wrong={d.get('wrong',0):3d}  fa={d.get('false_alarm',0)}")
    json.dump(report, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print("→", args.out)


if __name__ == "__main__":
    main()
