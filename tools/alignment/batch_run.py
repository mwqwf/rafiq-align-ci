# -*- coding: utf-8 -*-
"""مشغّل دفعي مستأنف: يفهرس قارئاً كاملاً (ملفات سور) وينتج TimingIndex .jz.

python batch_run.py --reciter husary_qalun --riwaya qalun \
    --base "https://archive.org/download/husari_qalun/{surah:03d}.mp3" [--surahs 1-114]

لكل سورة ملف json في work/batch_{reciter}/ — الموجود لا يُعاد. المخرج النهائي:
work/timings_{riwaya}_{reciter}.jz بصيغة 4.2 + تقرير نطاقات الثقة.
"""
import argparse
import json
import os
import time

from common import WORK, fetch_retry, load_index, write_jz
from pipeline import run_surah
from validate import make_timing_index, sha256_file


def parse_range(s, max_n=114):
    out = set()
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(x for x in out if 1 <= x <= max_n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--riwaya", required=True, choices=["hafs", "warsh", "qalun"])
    ap.add_argument("--base", required=True, help="قالب URL فيه {surah:03d}")
    ap.add_argument("--surahs", default="1-114")
    ap.add_argument("--counting", default=None, help="KUFI/MADANI (الافتراضي: فهرس التطبيق الكوفي)")
    args = ap.parse_args()

    d = os.path.join(WORK, f"batch_{args.reciter}")
    os.makedirs(d, exist_ok=True)
    index = load_index()
    surahs = parse_range(args.surahs)
    per_surah, fails = {}, []

    def sweep(todo, label=""):
        """تمريرة على قائمة سور؛ ترجع ما فشل منها. الملف الموجود لا يُعاد."""
        failed = []
        for sn in todo:
            err = one_surah(sn)
            if err is not None:
                failed.append((sn, err))
        return failed

    def one_surah(sn):
        # حارس القرص (درس 09-01): الفهرسة على قرص خانق تنتج ملفات مبتورة صامتة
        while True:
            free_mb = __import__("shutil").disk_usage(d).free // (1 << 20)
            if free_mb >= 250:
                break
            print(f"⏸ القرص {free_mb}م.ب فقط — انتظار 60ث لتحرر مساحة", flush=True)
            time.sleep(60)
        out_json = os.path.join(d, f"s{sn:03d}.json")
        if os.path.exists(out_json):
            with open(out_json, encoding="utf-8") as f:
                per_surah[sn] = json.load(f)
            return None
        url = args.base.format(surah=sn)
        audio = os.path.join(d, f"{sn:03d}.mp3")
        try:
            if not os.path.exists(audio) or os.path.getsize(audio) < 10_000:
                fetch_retry(url, audio)
            t0 = time.time()
            result = run_surah(audio, sn, args.riwaya, log=lambda *a: None)
            rec = {"fileRef": url, "sha256": sha256_file(audio),
                   "entries": result["entries"], "issues": result["issues"],
                   "bands": result["bands"], "totalMs": result["totalMs"]}
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False)
            per_surah[sn] = rec
            print(f"سورة {sn:3d}: {result['bands']} "
                  f"{'⚠️ ' + str(len(result['issues'])) + ' مخالفة' if result['issues'] else '✅'} "
                  f"({time.time()-t0:.0f}ث)", flush=True)
            # نظافة: احذف الوسائط المؤقتة الكبيرة، أبق mp3 للاستئناف السريع؟ لا — احذفه أيضاً
            for ext in (".16k.wav",):
                p = audio + ext
                if os.path.exists(p):
                    os.remove(p)
            os.remove(audio)
            return None
        except Exception as ex:
            print(f"سورة {sn:3d}: ❌ {ex}", flush=True)
            return str(ex)

    # ⚠️ درس 2026-09-02: السورة التي تفشل مرةً كانت تُسقط من الفهرس نهائياً،
    # فينقص القارئ صامتاً ويُرفض عند الرفع فيُعاد **كاملاً** — 114 سورة ثمناً
    # لواحدة. وأكثر الفشل عابر (خنق الخادم البعيد، نافذة whisper، ffmpeg).
    # فتمريرةٌ ثانية على الفاشل وحده قبل بناء الفهرس، بمهلة تهدأ فيها المصادر.
    fails = sweep(surahs)
    if fails:
        print(f"↻ إعادة {len(fails)} سورة فشلت: {[s for s, _ in fails]} — بعد 30ث",
              flush=True)
        time.sleep(30)
        fails = sweep([s for s, _ in fails])

    ti = make_timing_index(args.riwaya, args.reciter, "SURAH_FILES",
                           args.counting or "KUFI", per_surah)
    out = os.path.join(WORK, f"timings_{args.riwaya}_{args.reciter}.jz")
    write_jz(out, ti)
    bands = {}
    for e in ti["entries"]:
        bands[e["confBand"]] = bands.get(e["confBand"], 0) + 1
    total_issues = sum(len(v.get("issues", [])) for v in per_surah.values())
    print(f"\n=== TimingIndex: {out} ({os.path.getsize(out)//1024}ك.ب) ===")
    print(f"آيات مفهرسة: {len(ti['entries'])} · نطاقات: {bands} · مخالفات: {total_issues} · فشل سور: {fails}")


if __name__ == "__main__":
    main()
