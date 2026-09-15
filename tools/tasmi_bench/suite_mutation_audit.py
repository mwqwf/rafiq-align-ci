# -*- coding: utf-8 -*-
"""🧬 **هل يعضُّ طقمُ اختبارات المحرك؟** — يُجيب بالتجربة لا بعدّ الاختبارات.

**لماذا وُجد:** ثبت في هذه المناوبة **مرّتين** أنّ الأخضرَ وحدَه ليس شهادة:
- **D-438:** الطقمُ كلُّه (173 اختباراً) كان يمرّ أخضرَ وبندٌ كاملٌ من طريقة المُوضِّع معطَّل.
- **D-439:** بصمةُ حفصٍ مرَّت خضراءَ على إصلاحٍ جزئيٍّ ظننتُها تكشفه.

فالسؤالُ الصحيح ليس «كم اختباراً عندنا؟» بل **«ما الذي يمكن أن أكسره دون أن يُلاحظ أحد؟»**.
وهذه أداةُ **اختبارِ الطفرات**: تزرع في المحرك تغييراً صغيراً **ذا معنى** (ثابتٌ مشحونٌ
يتغيّر) ثمّ تُشغّل الطقم. فإن سقط ⇒ **الطفرةُ قُتلت** ✅ (ثمّة حارس). وإن مرَّ أخضرَ ⇒
**الطفرةُ نجت** 🚨 — والثابتُ مشحونٌ بلا شاهدٍ يعضّ، وهي عينُ حالة D-320/D-324 قبل D-421.

  python tools/tasmi_bench/suite_mutation_audit.py [--only <اسم>] [--list] [--timeout ث]

⛔ **الأمانُ أوّلاً:** تُحفظ نسخةُ كلِّ ملفٍّ قبل المسّ، وتُعاد في `finally` **مهما حدث**
(‏مقاطعةٌ أو خطأ)، ثمّ تُتحقَّق البصمةُ بعد الإعادة. وإن فشلت الإعادةُ صرخت الأداةُ ولم تسكت.
⚠️ ولا تُشغَّل وثمّة تعديلاتٌ غيرُ مودَعةٍ في `engine/` — تتوقّف وتقول لِمَ.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "engine", "recitation", "src", "main", "kotlin",
                   "com", "ali", "rafiq", "recitation")
RUNNER = os.path.join(HERE, "engine_judge", "build_and_run_tests.sh")

# (‏الاسم، الملفّ، النصُّ الأصليّ، النصُّ المطفور، لماذا يهمّ)
MUTANTS = [
    ("TOP=1", "QuranLocator.kt", "const val TOP = 8", "const val TOP = 1",
     "البند 3: إعادةُ ترتيب المرشّحين بالجودة — دَينُ D-320/D-324 الذي حرسه D-421"),
    ("RARE_BIGRAM=1", "QuranLocator.kt", "const val RARE_BIGRAM = 12", "const val RARE_BIGRAM = 1",
     "عتبةُ «الثنائيّةُ نادرة» في التصويت"),
    ("RARE_WORD=999", "QuranLocator.kt", "const val RARE_WORD = 4", "const val RARE_WORD = 999",
     "عتبةُ «الكلمةُ نادرةٌ جدّاً» — 999 يجعل كلَّ كلمةٍ نادرة"),
    ("MAX_MATCH=2", "LongAudioTranscriber.kt", "private const val MAX_MATCH = 12",
     "private const val MAX_MATCH = 2", "مدى البحث عن التراكب في دمج النوافذ"),
    ("WINDOW=5", "LongAudioTranscriber.kt", "const val WINDOW_SECONDS = 25",
     "const val WINDOW_SECONDS = 5", "طولُ نافذة التفريغ"),
    ("OVERLAP=0", "LongAudioTranscriber.kt", "const val OVERLAP_SECONDS = 4",
     "const val OVERLAP_SECONDS = 0", "تراكبُ النوافذ — صفرٌ يعني لا تراكب"),
    ("GAP=99", "LongAudioTranscriber.kt", "const val MAX_GAP_SECONDS = 2",
     "const val MAX_GAP_SECONDS = 99", "السكتةُ التي تقطع المجموعة (‏D-250)"),
    ("CAP=1", "LongAudioTranscriber.kt", "var GROUP_CAP_SECONDS = 10",
     "var GROUP_CAP_SECONDS = 1", "سقفُ المجموعة بالثواني — ثابتٌ مشحون"),
    ("collapse=0", "RecitationScorer.kt", "var collapseThreshold: Float = 0.60f",
     "var collapseThreshold: Float = 0.0f", "حارسُ الانهيار — 0 = مطفأ (‏ثابتٌ مشحون)"),
    ("collapse=1", "RecitationScorer.kt", "var collapseThreshold: Float = 0.60f",
     "var collapseThreshold: Float = 1.0f", "حارسُ الانهيار في أقصاه"),
    ("NoiseGate=off", "NoiseGate.kt", "var enabled: Boolean = true",
     "var enabled: Boolean = false", "بوّابةُ الضجيج — ثابتٌ مشحون"),

    # ——— الدفعةُ الثانية (‏D-445): منطقُ الحكم والمحاذاة لا الثوابتَ وحدَها ———
    ("criticalPairs=off", "RecitationScorer.kt", "var criticalPairsUncertain: Boolean = true",
     "var criticalPairsUncertain: Boolean = false",
     "D-323: زوجٌ قصيرٌ يفرق بحرفٍ ⇒ «غير متبيَّن» — ثابتٌ مشحونٌ والمرآةُ تخالفه"),
    ("tolerance=5⇒3", "RecitationScorer.kt", "return d * 5 <= n || (!strictShort && n <= 3 && d <= 1)",
     "return d * 3 <= n || (!strictShort && n <= 3 && d <= 1)",
     "قلبُ تسامح المطابقة: خُمسُ الطول ⇒ ثلثُه (‏أشدّ)"),
    ("tolerance=5⇒9", "RecitationScorer.kt", "return d * 5 <= n || (!strictShort && n <= 3 && d <= 1)",
     "return d * 9 <= n || (!strictShort && n <= 3 && d <= 1)",
     "قلبُ تسامح المطابقة في الاتّجاه الآخر (‏أرخى)"),
    ("shortLicense≤5", "RecitationScorer.kt", "return d * 5 <= n || (!strictShort && n <= 3 && d <= 1)",
     "return d * 5 <= n || (!strictShort && n <= 5 && d <= 1)",
     "رخصةُ الكلمة القصيرة: ≤3 حروف ⇒ ≤5"),
    ("criticalLen≤1", "RecitationScorer.kt",
     "criticalPairsUncertain && refs.any { r -> maxOf(r.length, hyp.length) <= 3 && edit(r, hyp) <= 1 }",
     "criticalPairsUncertain && refs.any { r -> maxOf(r.length, hyp.length) <= 1 && edit(r, hyp) <= 1 }",
     "مدى «الزوج القصير» في حارس D-323: ≤3 ⇒ ≤1 (‏يُعطّله عملياً)"),
    ("minAcc=0.5⇒0.05", "LongTasmiAnchor.kt", "minAccuracy: Float = 0.5f",
     "minAccuracy: Float = 0.05f",
     "عتبةُ «الآيةُ سُمعت» في المرساة — 0.05 يقبل كلَّ شيء", 4),
    ("slack=3⇒0", "LongTasmiAnchor.kt", "slack: Int = 3", "slack: Int = 0",
     "مرونةُ طول النافذة في المحاذاة", 4),
    ("locGuard=off", "QuranLocator.kt", "if (cover < 0.5 || correct < minOf(3, core.size)) continue",
     "if (false) continue",
     "البند 4: الحكمُ المحافظ («الإنذارُ الكاذب أسوأ من لم نتبيّن»)"),
    # ——— الدفعةُ الثالثة (‏D-446): حرّاسُ **الاتّهام الكاذب** في ما يراه المستخدم ———
    # كلُّ طفرةٍ هنا تنزع حارساً يمنع تنبيهاً كاذباً — وهو أسوأُ ما يقع في تطبيق حفظ.
    ("haraka:noLenGuard", "HarakaChecker.kt",
     "if (r.isEmpty() || r.size != h.size) return null", "if (r.isEmpty()) return null",
     "تنبيهُ الحركات يقارن كلمتَين مختلفتَي عدد الحروف"),
    ("haraka:noLetterGuard", "HarakaChecker.kt",
     "for (i in r.indices) if (r[i].first != h[i].first) return null",
     "for (i in r.indices) if (false) return null",
     "تنبيهُ الحركات يتّهم ولو اختلفت الحروفُ نفسُها"),
    ("haraka:noEmptyGuard", "HarakaChecker.kt",
     "if (a.isNotEmpty() && b.isNotEmpty() && a != b)", "if (a != b)",
     "يتّهم حين لا حركةَ في المسموع أصلاً — والتفريغُ بلا تشكيلٍ غالباً ⇒ اتّهامٌ شامل"),
    ("haraka:includeLast", "HarakaChecker.kt",
     "fun check(refIndex: Int, ref: String, heard: String, includeLast: Boolean = false): Issue?",
     "fun check(refIndex: Int, ref: String, heard: String, includeLast: Boolean = true): Issue?",
     "فحصُ حركة الحرف الأخير — موقوفٌ عمداً (‏الوقفُ يُسكّنه)"),
    ("slip:noBlankGuard", "RiwayaSlipDetector.kt", "if (h.isEmpty()) return null",
     "if (false) return null",
     "كاشفُ انزلاق الرواية بلا حارسِ المسموع الفارغ (‏صنفُ D-438)"),
    ("slip:noTolerance", "RiwayaSlipDetector.kt",
     "if (exact.isEmpty() && matches(mine, h, myProfile)) return null",
     "if (false) return null",
     "ينزع «تسامحُ روايتك» ⇒ يتّهم بالانزلاق ما تقبله روايتُك أصلاً"),
    # ——— الدفعةُ الرابعة (‏D-570): وحداتٌ لم تُطفَر قطّ — والدرسُ أنّ فيها تختبئ الثغرات ———
    ("band:cleanLoose", "LongTasmiMapper.kt", "errors == 0 -> Band.CLEAN",
     "errors <= 1 -> Band.CLEAN",
     "«ثابتة» تشمل آيةً فيها خطأ ⇒ يُطمأنُ القارئُ على ما ليس بسليم"),
    ("band:slipWide", "LongTasmiMapper.kt", "errors <= 2 && errors * 3 <= words -> Band.SLIP",
     "errors <= 5 && errors * 3 <= words -> Band.SLIP",
     "«تعثّر» يبتلع ما حقُّه «تحتاج مراجعة» (‏خمسةُ أخطاء)"),
    ("band:thirdRule", "LongTasmiMapper.kt", "errors <= 2 && errors * 3 <= words -> Band.SLIP",
     "errors <= 2 && errors * 9 <= words -> Band.SLIP",
     "قاعدةُ ثلثِ الكلمات ⇒ تُسعُها (‏أشدّ)"),
    ("band:cleanFlag", "LongTasmiMapper.kt", "val clean: Boolean get() = errors == 0",
     "val clean: Boolean get() = errors <= 1",
     "علَمُ «نظيفة» المستقلُّ عن النطاقات"),
    ("audio:LIMIT", "AudioLevelV2.kt", "const val LIMIT = 0.95f", "const val LIMIT = 0.10f",
     "عتبةُ المحدِّد الناعم في تسوية الجهارة"),
    # ——— الدفعةُ الخامسة (‏D-571): نصائحُ المحرك وتتبُّعُه الحيّ ———
    ("advice:trigger", "BiggerModelAdvice.kt", "const val ACCUSATION_TRIGGER: Float = 0.10f",
     "const val ACCUSATION_TRIGGER: Float = 0.90f",
     "عتبةُ «اتّهامٌ ثقيل» التي تعرض نصيحةَ النموذج الأكبر"),
    ("advice:noInstalledGuard", "BiggerModelAdvice.kt",
     "if (installed || declined) return null", "if (false) return null",
     "تُعرض النصيحةُ ولو كان النموذجُ مثبَّتاً أو رُفضت من قبل ⇒ إلحاحٌ على المستخدم"),
    ("advice:noMinWords", "BiggerModelAdvice.kt", "if (totalWords < MIN_WORDS) return null",
     "if (false) return null",
     "تُعرض النصيحةُ على تلاوةٍ قصيرةٍ جدّاً ⇒ حكمٌ على عيّنةٍ لا تكفي"),
    ("advice:snrFlip", "BiggerModelAdvice.kt",
     "if (snrDb != null && snrDb < AudioLevelV2.NOISY_SNR_DB) return Reason.NOISY_ROOM",
     "if (snrDb != null && snrDb > AudioLevelV2.NOISY_SNR_DB) return Reason.NOISY_ROOM",
     "قلبُ شرط «الغرفةُ ضاجّة» ⇒ يُنصح النظيفُ ويُترك الضاجّ"),
    ("live:badSet", "LiveTracker.kt",
     "fun bad(w: RecitationScorer.WordResult) = w.verdict == RecitationScorer.Verdict.MISSED || w.verdict == RecitationScorer.Verdict.SUBSTITUTED",
     "fun bad(w: RecitationScorer.WordResult) = w.verdict == RecitationScorer.Verdict.MISSED",
     "التتبّعُ الحيُّ يُسقط «المُبدَل» من الأخطاء ⇒ زلّةٌ لا تظهر للقارئ"),
    ("live:cursorBound", "LiveTracker.kt",
     "cur.words.filter { it.refIndex <= lastHit && bad(it) }",
     "cur.words.filter { bad(it) }",
     "يَعُدّ أخطاءَ ما لم يُقرأ بعدُ ⇒ اتّهامٌ بما لم يُنطق"),
]


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_suite(timeout):
    """يُعيد (‏نجح؟، السطرُ الأخيرُ الدالّ)."""
    try:
        p = subprocess.run(["bash", RUNNER], cwd=HERE, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "⏳ تجاوز الوقت"
    out = (p.stdout or "") + (p.stderr or "")
    for line in reversed(out.splitlines()):
        s = line.strip()
        if s.startswith("OK (") or s.startswith("Tests run:"):
            return s.startswith("OK ("), s
    return None, "⛔ لم يُفهم مخرجُ الطقم"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="اسمُ طفرةٍ واحدة")
    ap.add_argument("--list", action="store_true", help="اعرض الطفرات ولا تُشغّل")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    if args.list:
        for e in MUTANTS:
            print(f"  {e[0]:18s} {e[1]:24s} {e[4]}")
        return

    dirty = subprocess.run(["git", "status", "--porcelain", "engine/"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit("⛔ ثمّة تعديلاتٌ غيرُ مودَعةٍ في engine/ — أودِعها أوّلاً "
                         f"لئلّا تختلط بالطفرات:\n{dirty}")

    todo = [m for m in MUTANTS if not args.only or m[0] in args.only.split(",")]
    if not args.only:
        ok, line = run_suite(args.timeout)
        print(f"# خطُّ الأساس (بلا طفرة): {line}")
        if ok is not True:
            raise SystemExit("⛔ الطقمُ ليس أخضرَ أصلاً — لا معنى لقياس الطفرات")

    backup = tempfile.mkdtemp(prefix="mutaudit.")
    killed, survived, broke = [], [], []
    try:
        for entry in todo:
            name, fname, old, new, why = entry[:5]
            want = entry[5] if len(entry) > 5 else 1
            path = os.path.join(SRC, fname)
            keep = os.path.join(backup, fname)
            shutil.copy2(path, keep)
            before = sha(path)
            src = open(path, encoding="utf-8").read()
            if src.count(old) != want:
                broke.append((name, f"مواضعُ النصِّ الأصليّ {src.count(old)} والمنتظَر {want}"))
                continue
            open(path, "w", encoding="utf-8").write(src.replace(old, new))
            t0 = time.time()
            ok, line = run_suite(args.timeout)
            dt = time.time() - t0
            shutil.copy2(keep, path)
            if sha(path) != before:
                raise SystemExit(f"🚨🚨 فشلت إعادةُ {fname} — النسخةُ في {keep}. أوقفتُ كلَّ شيء.")
            if ok is False:
                killed.append((name, why, dt))
                print(f"  ✅ قُتلت   {name:16s} ({dt:.0f}ث) · {line}")
            elif ok is True:
                survived.append((name, why, dt))
                print(f"  🚨 نجت    {name:16s} ({dt:.0f}ث) · {line} · {why}")
            else:
                broke.append((name, line))
                print(f"  ⛔ تعذّرت {name:16s} · {line}")
    finally:
        for f in os.listdir(backup):
            shutil.copy2(os.path.join(backup, f), os.path.join(SRC, f))
        left = subprocess.run(["git", "status", "--porcelain", "engine/"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
        print(f"\n# 🔁 أُعيدت المصادرُ — حالةُ engine/: "
              f"{'✅ نظيفة' if not left else '🚨 ' + left}")

    n = len(killed) + len(survived)
    if n:
        print(f"\n# 🧬 قُتلت {len(killed)}/{n} · **نجت {len(survived)}** "
              f"⇒ درجةُ العضّ {100*len(killed)/n:.0f}٪")
    for name, why, _ in survived:
        print(f"#   🚨 بلا حارس: {name} — {why}")
    for name, msg in broke:
        print(f"#   ⛔ {name}: {msg}")


if __name__ == "__main__":
    main()
