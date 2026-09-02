# -*- coding: utf-8 -*-
"""طبقة البرهان الثانية: عينة حدود MED **حقيقية** قبل/بعد الصقل للمسح السماعي.

الضم المُحكم يعطي حقيقة أرضية مضبوطة لكنه متفائل (كل آية سُجّلت منفردة بنبرة ختام
واضحة، والتلاوة المتصلة يسيل فيها الأداء عبر الحد). فالحكم النهائي أذن بشرية على
تلاوة متصلة حقيقية.

**لا نعيد فهرسة شيء:** نأخذ حدود الفهرس الإنتاجي `husary_qalun` كما هي (قراءة فقط)
ونصقل منها الحدود الموسومة MED. فالصقل لا يحتاج المقاطع أصلاً — نافذته تتمركز على
الحد المقدَّر، وغياب المقاطع يعني نافذة مركزية خالصة. كلفة الطبقة كلها عشرات
النوافذ لا آلاف المقاطع.

python export_real_sample.py --surah 19 --surah 20 --surah 23 --per-surah 7
"""
import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from common import ffprobe_duration_ms, load_index, load_text, surah_slice, to_wav16k  # noqa: E402
from validate import band  # noqa: E402

from gt import W2  # noqa: E402
from refine import refine_surah  # noqa: E402

QALUN_URL = "https://server13.mp3quran.net/husr/Rewayat-Qalon-A-n-Nafi/{surah:03d}.mp3"
PROD_INDEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "alignment", "work", "batch_husary_qalun")
CLIP_WINDOW_MS = 4000   # نافذة السماع ±4ث حول الحد (بروتوكول QA_BOUNDARIES)


def load_prod(surah_no, riwaya="qalun"):
    """حدود الفهرس الإنتاجي كما هي (قراءة فقط) + الصوت المحلي."""
    with open(os.path.join(PROD_INDEX, f"s{surah_no:03d}.json"), encoding="utf-8") as f:
        prod = json.load(f)
    index = load_index()
    a, b, _s = surah_slice(index, surah_no)
    audio = os.path.join(W2, f"husary_qalun_s{surah_no:03d}.mp3")
    if not os.path.exists(audio):
        raise SystemExit(f"الصوت غير منزَّل: {audio}")
    return {"surah": surah_no, "riwaya": riwaya, "audio": audio,
            "wav": to_wav16k(audio), "totalMs": ffprobe_duration_ms(audio),
            "segments": [],                      # لا مقاطع ⇒ نافذة مركزية خالصة
            "entries": prod["entries"], "refAyahs": load_text(riwaya)[a:b]}


def pick_sample(before, after, n):
    """عينة عمياء متعمَّدة: إزاحات كبيرة + إزاحات صغيرة + شواهد سالبة بلا صقل."""
    refined = [(b, a) for b, a in zip(before, after)
               if a.get("refined") and a["startMs"] is not None]
    refined.sort(key=lambda p: -abs(p[1]["startMs"] - p[0]["startMs"]))
    untouched = [(b, a) for b, a in zip(before, after)
                 if not a.get("refined") and b["startMs"] is not None
                 and band(b["conf"]) == "MED"]
    n_neg = max(1, n // 4)
    n_ref = n - n_neg
    take = refined[: (n_ref + 1) // 2]                       # الأكبر إزاحة
    take += [p for p in refined[-(n_ref // 2):] if p not in take] if n_ref // 2 else []
    take += untouched[:n_neg]
    return take[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--surah", type=int, action="append", required=True)
    ap.add_argument("--per-surah", type=int, default=7)
    ap.add_argument("--candidates", type=int, default=10,
                    help="كم حدَّ MED يُصقل فعلاً في كل سورة (توزيع منتظم)")
    args = ap.parse_args()
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(outdir, exist_ok=True)
    samples = []
    for sn in args.surah:
        d = load_prod(sn)
        # الأهداف: حدود MED وحدها (HIGH مسنودة أصلاً ولا يمسّها الصقل)، ومنها
        # عيّنة موزّعة على طول السورة لا كتلة متجاورة — وحدها تُصقل، كي تبقى كلفة
        # هذه الطبقة عشرات النوافذ لا مئاتها.
        med = [i for i, e in enumerate(d["entries"])
               if e.get("startMs") is not None and band(e["conf"]) == "MED" and i > 0]
        step = max(1, len(med) // max(args.candidates, 1))
        chosen = set(med[::step][:args.candidates])
        for i, e in enumerate(d["entries"]):
            e["snapped"] = i not in chosen
        print(f"  س{sn}: {len(med)} حداً MED ← {len(chosen)} مرشحاً للصقل", flush=True)
        before = copy.deepcopy(d["entries"])
        refine_surah(d, log=lambda m: print(f"  س{sn}: {m}", flush=True))
        after = d["entries"]
        for b, a in pick_sample(before, after, args.per_surah):
            t = a["startMs"]
            src = {"token-snap": "TOKEN_SNAP", "token-mid": "TOKEN_MID"}.get(
                a.get("refineSrc", ""), "UNCHANGED")
            samples.append({
                "ayahId": f"{sn}:{a['ayahIdx'] + 1}",
                "boundary": "START",
                "beforeMs": b["startMs"],
                "afterMs": t,
                "shiftMs": t - b["startMs"],
                "refineSource": src,
                "confBefore": b["conf"],
                "clipUrl": QALUN_URL.format(surah=sn),
                "clipFromMs": max(0, t - CLIP_WINDOW_MS),
                "clipToMs": min(d["totalMs"], t + CLIP_WINDOW_MS),
            })
    out = os.path.join(outdir, "REAL_SAMPLE_qalun.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"reciterId": "husary_qalun", "riwaya": "qalun", "samples": samples},
                  f, ensure_ascii=False, indent=1)
    print(f"كُتب {len(samples)} حداً في {out}")


if __name__ == "__main__":
    main()
