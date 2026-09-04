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
from basmala_local import BAS, WORK, _edit, _eq, cut, fuzzy_seq, text_of  # noqa: E402
from common import load_index, load_text, norm, read_jz, write_jz  # noqa: E402

SKIP = {1, 9}
MIN_CUT_MS, MAX_CUT_MS = 1500, 5000
VERIFY_MS = 4000
# ⛔ نافذةُ **الرأس** أقصرُ عمداً: أربعُ ثوانٍ تبتلع ذيلَ البسملة فتُخفيه،
#    و1200م.ث تكفي لكلمةٍ أو كلمتين فتكشفه. **والقِصَرُ هنا ميزةٌ لا نقص.**
HEAD_MS = int(os.environ.get("BASMALA_HEAD_MS", "1200"))
# كلماتُ البسملة كما يلفظها التعرّفُ مشوّهةً — وهي ما يجب ألّا يبدأ به المطلع.
# ⛔ «اسم» أُسقطت: تطابق «الم» بحرفٍ واحد فتردّ مطلعاً صحيحاً.
BASMALA_WORDS = ("بسم", "الله", "الرحمن", "الرحيم", "رحمن", "رحيم")
# ⛔ المدخل لا يحمل `durationMs`: المدة **مشتقّة** من `endMs - startMs`، والحارس
# في tools/index_qa/run.py يُسقط الفهرس كلّه بـ«مداخل بمدة غير صالحة» عند
# `endMs <= startMs`. وهذه الأداة كانت تُزيح البداية وحدها بلا نظرٍ إلى النهاية،
# فإن كانت نهاية الآية الأولى مقدَّرةً قصيرةً (‏kyat 55:1 نهايتها 1913 والبسملة
# 2250) صارت المدة سالبة ورُفض المشتقّ كلّه رغم نظافة حكمه الصوتي.
# فالقصّ يُرفض إذا لم يبقَ للآية بقيّةٌ معقولة بعد الحدّ الجديد.
MIN_REMAIN_MS = 500
# ⛔ سُلَّم الكشف: نافذة 6ث وحدها أسقطت 33 حالة ثبتت لاحقاً بنوافذ أقصر
# (‏قياس 2026-09-02: التوزيع 1000×1 · 1500×1 · 2000×22 · 3000×7 · 4000×1 · 6000×1).
# فالكشف يمرّ بالسُّلَّم كلّه، والدرجة التي تظهر فيها البسملة تامّةً **هي**
# تقدير نهايتها — فلا حاجة لمسحٍ ثانٍ.
LADDER = (1000, 1500, 2000, 3000, 4000, 6000)


def fetch_head(url, dst, nbytes=262144):
    """أول 256ك.ب تكفي ≥12ث — لا تُنزَّل السورة كاملة لأجل ست ثوانٍ."""
    import urllib.request
    if os.path.exists(dst):
        return dst
    # ⛔ الخادم يقطع الاتصال عشوائياً (‏5 من 23 سورة في تشغيلةٍ واحدة، وثلاث
    # في أخرى) — وبلا إعادة محاولةٍ يبدو تذبذبُ الشبكة تذبذباً في **النتيجة**:
    # ‏18 و19 و20 مقصوصة لثلاث تشغيلاتٍ لنفس المدخل. المحاولة تُعاد ثلاثاً.
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url,
                                         headers={"Range": f"bytes=0-{nbytes-1}"})
            with urllib.request.urlopen(req, timeout=90) as r, open(dst, "wb") as f:
                f.write(r.read())
            if os.path.getsize(dst) > 32768:
                return dst
            last = "حمولة أقصر من 32ك.ب"
        except Exception as ex:
            last = ex
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"تعذّر التنزيل بعد ثلاث محاولات: {last}")


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
            end = None
            for d in LADDER:
                w = text_of(model, cut(mp3, e["startMs"], d, clip)).split()
                j = fuzzy_seq(w)
                if d == LADDER[0] or j is not None:
                    row["heard"] = " ".join(w[:8])
                if j is not None and len(w) >= j + len(BAS):
                    end = d
                    row["rung"] = d
                    break
            # ⚠️ درجات السُّلَّم خشنة (‏1000م.ث بين درجتين)، والقصّ عند الدرجة
            # يحلق حتى ثانيةً من أول الآية. فتُصقل النهاية بمسحٍ ربع-ثانيةٍ
            # **بين الدرجة السابقة والدرجة المُصيبة** — أربع تفريغات لا أكثر.
            if end is not None:
                lo = LADDER[LADDER.index(end) - 1] if LADDER.index(end) else 500
                for d in range(lo + 250, end, 250):
                    w = text_of(model, cut(mp3, e["startMs"], d, clip)).split()
                    j = fuzzy_seq(w)
                    if j is not None and len(w) >= j + len(BAS):
                        end = d
                        row["refinedTo"] = d
                        break
            if end is None:
                row["verdict"] = "لا بسملة عبر السُّلَّم كلّه — لا قصّ"
                rows.append(row)
                continue
            new_start = e["startMs"] + end
            ref = norm(text[start_of[s]]).split()
            # ⛔ المقارن العام يشترط طول 4 للتسامح، وأوائل آياتٍ كثيرة ثلاثية
            # («عبس» «سبح» «حم») فيردّها ولو أصابت: «عبش» و«يسبح» رُفضتا في
            # hawashi 80 و87 وهما صحيحتان. فيُسمح بخطأ حرفٍ واحد من طول 3.
            def _ok(a, b):
                return _eq(a, b) or (min(len(a), len(b)) >= 3 and _edit(a, b) <= 1)
            # ⛔ التسامح مع مطابقةٍ في الموضع الثاني كان لضجيجٍ عابر، لكنه
            # يمرّر **بقيّة بسملة**: koshi 39 «وحيم تنزيل الكتاب» و70 «من سال»
            # قُبلتا والحدّ يترك كلمةً من البسملة قبل الآية. فإن كانت الكلمة
            # الأولى بسمليّة دُفع الحدّ ربع ثانيةٍ حتى تبدأ الآية من موضعها،
            # وإلا فلا قصّ.
            def _verify(st):
                a = text_of(model, cut(mp3, st, VERIFY_MS, clip)).split()
                if not a:
                    return False, a
                # ⛔ لا تسامح مع موضعٍ ثانٍ: كلمةٌ زائدة قبل أول الآية تعني
                # أن الحدّ **أبكر مما يجب**، وأغلبها بقيّة بسملةٍ مشوّهةُ
                # التعرّف لا يمسكها تطابقُ الكلمات (‏koshi 39 «وحيم» عن
                # «الرحيم»). فالشرط: تبدأ الآية من الكلمة الأولى، وإلا دُفع
                # الحدّ ربع ثانيةٍ حتى ألفَي ثانية ثم يُرفض القصّ.
                # الرسم يصل ما يفصله التعرّف: ﴿يَٰٓأَيُّهَا﴾ كلمةٌ واحدة في
                # النصّ («يايها») وكلمتان في المسموع («يا ايها») — فرُفض قصٌّ
                # صحيح في koshi 22 وdeban 5. فتُجرَّب الكلمتان موصولتين.
                if _ok(a[0], ref[0]):
                    return True, a
                if len(a) > 1 and _ok(a[0] + a[1], ref[0]):
                    return True, a
                return False, a

            # ⛔ **حارسُ الرأس القصير (‏R-2026-09-03-d/e).** ‏`_verify` يسمع
            #    **أربع ثوانٍ** (`VERIFY_MS`)، وفي أربع ثوانٍ **يبتلع النموذجُ
            #    ذيلَ البسملة** فتبدو الآيةُ أوّلَ ما يُسمع — فيمرّ حدٌّ ما زال
            #    داخل البسملة. مقيسٌ في الإنتاج: `kyat` 2:1 عند 2420 يُسمع في
            #    أوّل 1500م.ث «اذ ارحمن» (ذيلُ «الرحمن») **وهو مقصوصٌ مُتحقَّقٌ
            #    منه**. ⇒ **النافذةُ الطويلة تكذب**، فيُفحص الرأسُ القصيرُ
            #    مستقلاً: إن بدأ بكلمةٍ بسمليّةٍ فالحدُّ أبكرُ مما يجب.
            def _head_is_basmala(st):
                h = text_of(model, cut(mp3, st, HEAD_MS, clip)).split()
                if not h:
                    return False              # صمتٌ لا يشهد — والتعذّرُ ليس حكماً

                def _near(w, t, k):
                    return w == t or (min(len(w), len(t)) >= 3 and _edit(w, t) <= k)

                # ⛔ **الفاصلُ ليس شبهاً بالبسملة وحده، بل شبهاً بها أقربَ من
                #    شبهه بالآية.** جُرّب التسامحُ العدديّ وحدَه (حرفان لكلّ ما
                #    طولُه ≥5) فردّ مطالعَ صحيحةً: «الحمد» تبعُد عن «الرحمن»
                #    حرفين، و«افلح» عن «الله» حرفين — **فحارسٌ يمنع القصَّ
                #    الصحيح**. والمعلومةُ الفارقة عندنا مجّاناً: **نصُّ الآية
                #    نفسُه**. فما طابق أوائلَ الآية فهو الآيةُ لا بسملة.
                # ⛔ ولا يُستعمل `_eq` هنا: تسامحُه حرفان لكلّ ما طولُه ≥4،
                #    وهو مبنيٌّ لمقارنةِ كلمةٍ بنظيرها المعلوم لا لتصنيفِها.
                for w in h[:3]:
                    if any(_near(w, r, 1) for r in ref[:3]):
                        continue              # كلمةُ الآية — لا تُحسب بسملة
                    for bw in BASMALA_WORDS:
                        if w == bw or (len(w) >= 4 and _edit(w, bw) <= 2):
                            return True
                return False

            ok, after = _verify(new_start)
            if ok and _head_is_basmala(new_start):
                ok = False                    # الرأسُ ما زال بسملةً — ادفع الحدّ
            pushed = 0
            while not ok and after and pushed < 2000:
                pushed += 250
                new_start = e["startMs"] + end + pushed
                ok, after = _verify(new_start)
                if ok and _head_is_basmala(new_start):
                    ok = False
            if pushed:
                row["pushedMs"] = pushed
            row["afterHeard"] = " ".join(after[:6])
            row["startAfter"] = new_start
            row["deltaMs"] = new_start - e["startMs"]
            if not ok:
                row["verdict"] = "⛔ لم يتحقّق: ما بعد الحدّ الجديد لا يبدأ بأول الآية"
                rows.append(row)
                continue
            end_ms = e.get("endMs")
            if end_ms is None or new_start + MIN_REMAIN_MS > end_ms:
                row["endMs"] = end_ms
                row["remainMs"] = None if end_ms is None else end_ms - new_start
                row["verdict"] = ("⛔ لم يُقصّ: لا تبقى مدةٌ صالحة بعد الحدّ "
                                  f"(النهاية {end_ms} · المتبقّي "
                                  f"{row['remainMs']}م.ث)")
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
                  or "لم يُقصّ" in r.get("verdict", "")
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
