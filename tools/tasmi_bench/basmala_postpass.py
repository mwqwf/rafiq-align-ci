# -*- coding: utf-8 -*-
"""تمريرة لاحقة: **قصّ البسملة المبتلعة بقصٍّ متحقَّقٍ منه** — بلا خادم.

تعمل على أي فهرس `.jz` (‏staging)، ولكل سورةٍ غير الفاتحة والتوبة:
1. تفرّغ **[بداية الآية الأولى → 6ث]** — نافذةٌ قصيرة عمداً (‏الطويلة تبتلع
   الافتتاحية القصيرة: درس 2026-09-02).
2. إن بدأ المسموع بتتابع «بسم الله الرحمن الرحيم» ⇒ تُقدَّر نهايتها بـ**أصغر
   نافذةٍ تظهر فيها تامّة**.
3. ⛔ **ثم تتحقّق قبل أن تقصّ**: تفرّغ [الحدّ الجديد → 4ث] وتشترط أن يبدأ
   بأوائل كلمات الآية من نصّ الرواية. **فإن لم يتحقّق لم تقصّ** — وتُسجّل
   السبب. (الأصل: تقدير النهاية **حدٌّ أعلى** لأنه محكومٌ بجودة التفريغ، وقصٌّ
   زائد يبتر أول الآية — وهو أسوأ من بسملةٍ باقية.)
4. تكتب فهرساً جديداً ببصمة جديدة ووسم `basmalaTrimmed`، **ولا تمسّ الأصل**،
   ومعه **جدول قبل/بعد** لكل سورة.

    python tools/tasmi_bench/basmala_postpass.py --index a.jz --urls tmpl.json \\
        --out b.jz --table t.json [--dry-run]
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
sys.path.insert(0, HERE)
from basmala_local import BAS, WORK, _eq, cut, fuzzy_seq, text_of  # noqa: E402
from common import load_index, load_text, norm, read_jz, write_jz  # noqa: E402

SKIP = {1, 9}
MIN_CUT_MS, MAX_CUT_MS = 1500, 5000
VERIFY_MS = 4000


def fetch_head(url, dst, nbytes=262144):
    """أول 256ك.ب تكفي ≥12ث — لا تُنزَّل السورة كاملة لأجل ست ثوانٍ."""
    import urllib.request
    if os.path.exists(dst):
        return dst
    req = urllib.request.Request(url, headers={"Range": f"bytes=0-{nbytes-1}"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
        f.write(r.read())
    return dst


def _exit_code(trimmed, unverified, args):
    """رمزٌ مميِّز (اقتراح 3a): 0 لا شيء يحتاج قصّاً · 1 قُصّ كل ما وجب ·
    2 بقيت حالاتٌ غير متحقَّقة — فيفرّق سير العمل بين «نجح» و«نجح جزئياً»."""
    if unverified and args.fail_on_unverified:
        return 2
    return 1 if trimmed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--url-template", required=True,
                    help="مثال: https://host/path/{s:03d}.mp3")
    ap.add_argument("--riwaya")
    ap.add_argument("--model", default=os.path.join(HERE, "work", "ggml-q8.bin"))
    ap.add_argument("--out")
    ap.add_argument("--table", default=os.path.join(HERE, "work", "basmala_table.json"))
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--surahs", help="حصرٌ للتجربة: 22,73")
    ap.add_argument("--dry-run", action="store_true")
    # ⛔ وظيفةٌ تخرج بصفرٍ دائماً تظهر خضراء، فيمرّ عيبٌ معلومٌ بإصلاحٍ غير
    # مبرهن بلا أن يراه أحد (طلب 3a، وقد أضاع فشلٌ صامت من هذا النوع ساعات).
    ap.add_argument("--fail-on-unverified", action="store_true",
                    help="رمز خروج 2 إن بقيت سورٌ فيها بسملة بلا قصّ متحقَّق")
    ap.add_argument("--summary", action="store_true",
                    help="ملخّص Markdown على stdout (لـGITHUB_STEP_SUMMARY)")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)

    ti = read_jz(args.index)
    riwaya = args.riwaya or ti.get("riwaya", "hafs")
    text = load_text(riwaya)
    idx = load_index()
    start_of = {s["n"]: s["start"] for s in idx["surahs"]}
    only = {int(x) for x in args.surahs.split(",")} if args.surahs else None

    from pywhispercpp.model import Model
    model = Model(args.model, n_threads=args.threads, language="ar",
                  print_progress=False, print_realtime=False)

    first = {int(e["ayahId"].split(":")[0]): e for e in ti["entries"]
             if e["ayahId"].endswith(":1")}
    rows, trimmed = [], 0
    for s, e in sorted(first.items()):
        if s in SKIP or e.get("startMs") is None:
            continue
        if only and s not in only:
            continue
        row = {"surah": s, "startBefore": e["startMs"]}
        mp3 = os.path.join(WORK, f"pp_{s:03d}.mp3")
        clip = os.path.join(WORK, "pp_clip.wav")
        try:
            fetch_head(args.url_template.format(s=s), mp3)
            heard = text_of(model, cut(mp3, e["startMs"], 6000, clip)).split()
            row["heard"] = " ".join(heard[:8])
            if fuzzy_seq(heard) is None:
                row["verdict"] = "لا بسملة"
                rows.append(row)
                continue
            end = None
            for d in range(MIN_CUT_MS, MAX_CUT_MS + 1, 250):
                w = text_of(model, cut(mp3, e["startMs"], d, clip)).split()
                j = fuzzy_seq(w)
                if j is not None and len(w) >= j + len(BAS):
                    end = d
                    break
            if end is None:
                row["verdict"] = "بسملة بلا نهاية مقدَّرة — لا قصّ"
                rows.append(row)
                continue
            new_start = e["startMs"] + end
            ref = norm(text[start_of[s]]).split()
            after = text_of(model, cut(mp3, new_start, VERIFY_MS, clip)).split()
            row["afterHeard"] = " ".join(after[:6])
            ok = bool(after) and any(_eq(after[k], ref[0]) for k in (0, 1)
                                     if k < len(after))
            row["startAfter"] = new_start
            row["deltaMs"] = end
            if not ok:
                row["verdict"] = "⛔ لم يتحقّق: ما بعد الحدّ الجديد لا يبدأ بأول الآية"
                rows.append(row)
                continue
            row["verdict"] = "✂️ قُصّت (متحقَّقة)"
            e["startMs"] = new_start
            e["basmalaTrimmed"] = True
            trimmed += 1
        except Exception as ex:
            row["verdict"] = f"خطأ: {str(ex)[:60]}"
        finally:
            if os.path.exists(mp3):
                os.remove(mp3)
        rows.append(row)
        print(f"  س{s:3d}: {row['verdict']} · {row.get('heard','')[:34]}", flush=True)

    hits = [r for r in rows if "قُصّت" in r.get("verdict", "")]
    print(f"\nفُحص {len(rows)} سورة · **قُصّت {trimmed}** · "
          f"بسملة بلا قصّ {sum(1 for r in rows if 'لم يتحقّق' in r.get('verdict',''))}")
    json.dump({"index": os.path.basename(args.index), "riwaya": riwaya,
               "trimmed": trimmed, "rows": rows},
              open(args.table, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"جدول قبل/بعد → {args.table}")
    for r in hits:
        print(f"   س{r['surah']:3d}: {r['startBefore']} ⇐ {r['startAfter']} "
              f"(+{r['deltaMs']}م.ث) · بعده: {r.get('afterHeard','')[:30]}")
    unverified = [r for r in rows if "لم يتحقّق" in r.get("verdict", "")
                  or "بلا نهاية" in r.get("verdict", "")]
    if args.summary:
        print(chr(10) + "## قصّ البسملة — " + os.path.basename(args.index))
        print(f"- سور فُحصت: **{len(rows)}**")
        print(f"- ✂️ قُصّت متحقَّقة: **{trimmed}**")
        print(f"- ⚠️ **بسملة بلا قصّ متحقَّق: {len(unverified)}**"
              + (" — " + "، ".join(f"س{r['surah']}" for r in unverified)
                 if unverified else ""))
        print(f"- لا بسملة: {sum(1 for r in rows if r.get('verdict') == 'لا بسملة')}")
        if hits:
            print(chr(10) + "| سورة | قبل | بعد | الفارق | ما بعد الحدّ |")
            print("|---|---|---|---|---|")
            for r in hits:
                print(f"| {r['surah']} | {r['startBefore']} | {r['startAfter']} "
                      f"| +{r['deltaMs']}م.ث | {r.get('afterHeard','')[:28]} |")
    if args.dry_run or not args.out:
        print("(بلا كتابة — الأصل لم يُمَس)")
        return _exit_code(trimmed, unverified, args)
    ti["basmalaTrim"] = {"tool": "basmala_postpass.py", "at": int(time.time()),
                         "trimmed": trimmed, "verified": True,
                         "sourceIndex": os.path.basename(args.index)}
    write_jz(args.out, ti)
    print(f"✅ {args.out} · sha256 "
          f"{hashlib.sha256(open(args.out,'rb').read()).hexdigest()[:16]}…")
    return _exit_code(trimmed, unverified, args)


if __name__ == "__main__":
    sys.exit(main() or 0)
