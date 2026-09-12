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
import tempfile
import time

from common import ROOT, WORK, fetch_retry, load_index, write_jz
from pipeline import run_surah
from validate import make_timing_index, sha256_file


def catalog_files(reciter):
    """جدولُ أسماء الملفات من الكتالوج لمضيفٍ **لا يرقّم** أسماءه.

    ⛔ سببُ وجود هذه الدالّة (‏درسٌ بثمنه 2026-09-09): مضيفٌ يسمّي ملفّاته
    `001 الفاتحة.mp3` أو `001Al-fatiha.mp3` **لا يجمعه قالبُ عنوانٍ واحد**،
    فكان `shaykhna_qalun` و`fakhfakh_qalun` — مصحفان كاملان في الكتالوج —
    محبوسَين خارج الفهرسة، وبقاؤهما في موجةٍ بقالبٍ مخمَّن **يهدر شريحةً
    كاملةً على 404 في كلّ سورة**. وجدولُ `files` مكتوبٌ في الكتالوج سلفاً
    **ومرمَّزٌ** (‏يكتبه `add_surah_reciter.py`، ويستعمله `QuranRepository.kt`
    في التطبيق منذ تلاوة لغظف الشنقيطي) — فالحقيقةُ موجودةٌ ولم تكن تُقرأ.

    يرجع `{رقم السورة: اسمُ الملفّ}` بـ114 مدخلاً بالضبط، أو `None` إن لم
    يكن للقارئ جدولٌ. ولا يُخمَّن شيء: عددٌ غيرُ 114 يُرفع خطأً صريحاً.
    """
    import boto3  # noqa: PLC0415 — لا يُستورد إلا عند الحاجة
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json"),
                       encoding="utf-8"))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"],
                      region_name="auto")
    body = s3.get_object(Bucket=c["bucket"],
                         Key="catalog/reciters.json")["Body"].read()
    cat = json.loads(body.decode("utf-8"))
    for group in cat.get("riwayat", []):
        for r in group.get("reciters", []):
            if r.get("id") != reciter:
                continue
            files = r.get("files")
            if not files:
                return None
            if len(files) != 114:
                raise SystemExit(
                    f"⛔ جدولُ files لـ{reciter} فيه {len(files)} لا 114 — "
                    "لا يُبنى فهرسٌ على جدولٍ ناقص")
            return {i + 1: name for i, name in enumerate(files)}
    return None


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
    # ⛔ الروايات الست كلها مدعومة (وُسّع 2026-09-01). ضاقت القائمة إلى ثلاث في
    # نسخة `main` فأسقطت البصريَّين وشعبة فوراً بـ`invalid choice` — والخطأ
    # يقع **قبل** أي عمل فيبدو القارئ «فاشلاً» بلا سبب في السجل.
    ap.add_argument("--riwaya", required=True,
                    choices=["hafs", "warsh", "qalun", "douri", "sousi", "shuba"])
    ap.add_argument("--base", required=True,
                    help="قالب URL فيه {surah:03d}، أو مجلَّدٌ ينتهي بـ/ "
                         "فتُقرأ أسماءُ الملفات من جدول files في الكتالوج")
    ap.add_argument("--surahs", default="1-114")
    ap.add_argument("--counting", default=None, help="KUFI/MADANI (الافتراضي: فهرس التطبيق الكوفي)")
    args = ap.parse_args()

    # ── مصدرُ العناوين: قالبٌ أم جدولُ أسماءٍ من الكتالوج ────────────────
    # ⛔ الاختيارُ **بغياب `{surah` من الأساس** لا بعَلَمٍ جديد: فلا يُمَسّ
    #    `run_shard.sh` ولا صفوفُ TSV القائمة، ويكفي أن يحمل الصفُّ المجلَّدَ.
    files_map = None
    if "{surah" not in args.base:
        files_map = catalog_files(args.reciter)
        if not files_map:
            raise SystemExit(
                f"⛔ الأساسُ بلا `{{surah}}` ولا جدولَ files لـ{args.reciter} "
                "في الكتالوج — لا يُخمَّن اسمُ ملفّ")
        print(f"📇 أسماءُ الملفات من جدول files في الكتالوج — 114 مدخلاً "
              f"(س1={files_map[1]})", flush=True)

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

    # ⛔ سورٌ صوتها مبتور **عند المصدر** (قياس github-12): إعادتها تُنتج
    # توقيتاً «ناجحاً» على البتر نفسه فلا يكشفه حارس. أخطرها `husary_douri`
    # س25: فهرسٌ تامّ 77/77 على صوتٍ بـ62% من طوله — يمرّ من كل الحُرّاس
    # بعلامة نجاح. فتُتخطّى وتُوسم بدل أن تُبنى.
    skip = set()
    try:
        with open("/root/skip_surahs.txt", encoding="utf-8") as f:
            for ln in f:
                ln = ln.split("#", 1)[0].split()
                if len(ln) >= 2 and ln[0] == args.reciter:
                    skip.add(int(ln[1]))
    except FileNotFoundError:
        pass
    if skip:
        print(f"⏭ سورٌ مبتورة عند المصدر تُتخطّى: {sorted(skip)}", flush=True)

    def one_surah(sn):
        if sn in skip:
            return None            # ليست فشلاً: مصدرٌ معيب موسوم
        # حارس القرص (درس 09-01): الفهرسة على قرص خانق تنتج ملفات مبتورة صامتة
        while True:
            free_mb = __import__("shutil").disk_usage(d).free // (1 << 20)
            if free_mb >= 250:
                break
            print(f"⏸ القرص {free_mb}م.ب فقط — انتظار 60ث لتحرر مساحة", flush=True)
            time.sleep(60)
        out_json = os.path.join(d, f"s{sn:03d}.json")
        if os.path.exists(out_json):
            # ⛔ ملفٌ موجودٌ ليس ملفاً صالحاً: مهمةٌ قُتلت وسط الكتابة تترك
            #    sNNN.json فارغاً أو مبتوراً، فينهار json.load بـrc=1 ⇒
            #    الحاوية تموت ⇒ Cloud Run يعيدها ⇒ تستأنف ⇒ تنهار على الملف
            #    نفسه. حلقةٌ تحرق ثماني أنوية بلا مخرج، ولا يكسرها إلا حذفه.
            try:
                with open(out_json, encoding="utf-8") as f:
                    per_surah[sn] = json.load(f)
                return None
            except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
                print(f"⚠️ س{sn:03d}: {os.path.basename(out_json)} تالف "
                      f"({type(e).__name__}) ⇒ يُحذف ويُعاد حسابه", flush=True)
                os.remove(out_json)
        url = (args.base + files_map[sn]) if files_map else args.base.format(surah=sn)
        audio = os.path.join(d, f"{sn:03d}.mp3")
        try:
            if not os.path.exists(audio) or os.path.getsize(audio) < 10_000:
                fetch_retry(url, audio)
            t0 = time.time()
            result = run_surah(audio, sn, args.riwaya, log=lambda *a: None)
            import vad as _vad  # noqa: PLC0415
            rec = {"fileRef": url, "sha256": sha256_file(audio),
                   "vadRel": _vad.LAST_REL,
                   # نسخة العتبة **لكل سورة**: الفهرس الواحد قد يحمل سوراً
                   # بـadaptive-1 وأخرى بـadaptive-2، فالترويسة تسرد لا تختار.
                   "vadVersion": _vad.VAD_VERSION,
                   "entries": result["entries"], "issues": result["issues"],
                   "bands": result["bands"], "totalMs": result["totalMs"]}
            # ⛔ كتابةٌ ذرّية: الكتابة المباشرة تترك ملفاً **مبتوراً** إن انقطعت
            # (‏انتهاء مهلة المهمة، دحرجة، نفاد ذاكرة) — والمبتور أسوأ من
            # المفقود لأن الاستئناف يعدّه سورةً منجزة فلا يعيدها، فيدخل
            # الفهرسَ نقصٌ لا يشتكي منه أحد. و`os.replace` ذرّية على نظام
            # الملفات نفسه، فإمّا القديمُ سليماً وإمّا الجديدُ تامّاً ولا ثالث.
            tmp_fd, tmp_path = tempfile.mkstemp(dir=d, prefix=f".s{sn:03d}.", suffix=".tmp")
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(rec, f, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())   # الذرّية بلا fsync وعدٌ لا ضمان
                os.replace(tmp_path, out_json)
            except BaseException:
                try:
                    os.remove(tmp_path)    # لا يُترك مؤقتٌ يتيم
                except OSError:
                    pass
                raise
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
    # ⚠️ تمريرتان لا تكفيان: `a_turki` حُجز ساعةً كاملة بسورةٍ واحدة سقطت
    # بعطب ترميز عابر (0xa2) ونجحت من أول إعادة يدوية. وقارئٌ كامل يُحجب
    # بسورة واحدة خسارةٌ غير متناسبة — فأربع تمريرات بتراجع أسّي.
    fails = sweep(surahs)
    for attempt in range(3):
        if not fails:
            break
        wait = 30 * (2 ** attempt)
        print(f"↻ إعادة {len(fails)} سورة فشلت: {[s for s, _ in fails]} — بعد {wait}ث",
              flush=True)
        time.sleep(wait)
        fails = sweep([s for s, _ in fails])

    _rels = sorted(v["vadRel"] for v in per_surah.values() if v.get("vadRel") is not None)
    _med = _rels[len(_rels) // 2] if _rels else None
    ti = make_timing_index(args.riwaya, args.reciter, "SURAH_FILES",
                           args.counting or "KUFI", per_surah, vad_rel=_med)
    out = os.path.join(WORK, f"timings_{args.riwaya}_{args.reciter}.jz")
    write_jz(out, ti)
    # ⏱️ سطرُ الأطوار — ثوانٍ متراكمةٌ لهذا القارئ (‏`pipeline.PHASE`).
    #    يُطبع ويُرفع إلى ملخّص الوظيفة إن وُجد، فيُقرأ بلا فتح سجلّ.
    try:
        import pipeline as _pl
        _ph = " · ".join(f"{k}={int(v)}ث" for k, v in _pl.PHASE.items())
        _line = f"⏱️ أطوارُ {args.reciter}: {_ph}"
        print(_line)
        _sum = os.environ.get("GITHUB_STEP_SUMMARY")
        if _sum:
            with open(_sum, "a", encoding="utf-8") as _f:
                _f.write("- " + _line + chr(10))
    except Exception as _e:  # noqa: BLE001 — قياسٌ لا يُسقط إنتاجاً
        print(f"⚠️ تعذّر سطرُ الأطوار: {_e}")
    bands = {}
    for e in ti["entries"]:
        bands[e["confBand"]] = bands.get(e["confBand"], 0) + 1
    total_issues = sum(len(v.get("issues", [])) for v in per_surah.values())
    print(f"\n=== TimingIndex: {out} ({os.path.getsize(out)//1024}ك.ب) ===")
    print(f"آيات مفهرسة: {len(ti['entries'])} · نطاقات: {bands} · مخالفات: {total_issues} · فشل سور: {fails}")


if __name__ == "__main__":
    main()
