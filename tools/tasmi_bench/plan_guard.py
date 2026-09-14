# -*- coding: utf-8 -*-
"""🧷 **حارسُ الحقيقة الأرضيّة** — يفحص خطط الحقن (`inject_plan*.json`) قبل أن يُحكم بها.

⛔ **لِمَ وُجد (‏عطبٌ مقيسٌ لا احتمالٌ مفترَض · 2026-09-14):** أرقامُ الكشف كلُّها مبنيّةٌ على
دعوى واحدة: **«في هذا الموضع خطأٌ مصنوعٌ فعلاً»**. وقياسُ `inject_plan.json` أظهر أنّ الدعوى
تكذب في بنودٍ منها:

- **ثلاثةُ بنودِ `SWAP` مقطعُها المُبدَّلُ هو مقطعُها نفسُه** (‏`swapMs == cutMs`) ⇒ الصوتُ
  **لا يتغيّر بحرفٍ واحد**، والبندُ يُعَدّ مع ذلك خطأً يجب كشفُه. ⇒ **سقفُ الصنف 37/40 =
  92.5٪ بالبناء** — وهو بعينه أعلى رقمِ `SWAP` ظهر في اللوحة قطّ.
- **وسبعةُ بنودٍ هدفُها «كلمةٌ» لا صوتَ لها**: علامةُ وقفٍ (‏`ۖ ۗ ۚ`) يعدّها `refText.split()`
  كلمةً. وقِيس حكمُها في المسطرة: **صحيحةٌ في 44 من 44** تلاوةٍ مثاليّة ⇒ **لا تُتَّهم ولا
  تُكشَف**، فالحقنُ عليها حقيقةٌ أرضيّةٌ كاذبةُ الاسم.

⭐ **ولا يُصحَّح رقمٌ بحذف بندٍ يضرّه**: إسقاطُ هذه البنود **يرفع** الكشفَ — وهي الجهةُ التي
يُشتبه فيها. فالحارسُ **يقيس ويُعلن** ويمنع الجديدَ (‏`inject.py` صار يتخطّاها عند التوليد)،
والخططُ المودَعةُ تبقى بحالها كي تبقى الأرقامُ السالفةُ قابلةً للمقارنة.

    python tools/tasmi_bench/plan_guard.py tools/tasmi_bench/inject_plan*.json
    python tools/tasmi_bench/plan_guard.py --selftest
"""
import argparse
import glob as _glob
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# حروفُ العربيّة الأصليّة — وما خلا منها فعلامةُ وقفٍ أو ضبطٍ لا صوتَ لها مستقلّاً.
LETTERS = re.compile(r"[ء-ي]")
# فجوةُ الـ`SWAP` المسموحة: `inject.py` يشترط ألّا يفصل بين المقطعَين أكثرُ من 400م.ث
# (‏وإلّا صار قطعاً لا تبديلاً)، والهامشُ يقضم 2×`padMs` من الفجوة المعلنة.
SWAP_MAX_GAP_MS = 400

# ⛔ **قاتلٌ** = الحقيقةُ الأرضيّةُ نفسُها كاذبةٌ ⇒ الرقمُ المبنيُّ عليها لا يُقرأ.
# ⚠️ **منبِّهٌ** = البندُ يصحّ صوتاً ويُخطئ اسماً ⇒ يُقرأ الرقمُ بحدٍّ مكتوب.
FATAL = {
    "wordcount_mismatch": "⛔ `wordCount` يخالف عدَّ `refText`",
    "index_not_internal": "⛔ `wordIndex` ليس كلمةً داخليّةً (لا أوّلَ ولا آخر)",
    "target_mismatch": "⛔ `targetWord` لا يطابق `refText[wordIndex]`",
    "cut_malformed": "⛔ `cutMs` غيرُ مرتّبٍ أو سالب",
    "swap_missing": "⛔ `SWAP` بلا `swapMs`",
    "swap_degenerate": "⛔ `SWAP` مقطعاه متطابقان أو متداخلان ⇒ **الصوتُ لا يتغيّر**",
    "donor_missing": "⛔ `SUBSTITUTE`/`INSERT` بلا `donor`",
    "donor_same_word": "⛔ الكلمةُ المانحةُ هي المستبدَلةُ نفسُها ⇒ لا خطأ",
    "donor_cut_malformed": "⛔ `donor.cutMs` غيرُ مرتّب",
    "dup_id": "⛔ معرّفٌ مكرَّرٌ (بندان بحكمٍ واحد)",
}
WARN = {
    "silent_target": "⚠️ الهدفُ علامةُ وقفٍ لا صوتَ لها — تُحكم صحيحةً دائماً",
    "silent_donor": "⚠️ المانحُ علامةُ وقفٍ لا صوتَ لها",
    "swap_gap_wide": f"⚠️ فجوةُ `SWAP` تتجاوز {SWAP_MAX_GAP_MS}م.ث ⇒ قطعٌ لا تبديل",
}


# ⛔⛔ **ولا خضرةَ بلا شهادة** (‏عطبٌ وقع في `judge_parity` ثمّ **في هذا الحارس نفسِه** · D-442):
# خطّةٌ بلا بنودٍ كانت تُطبع «✅ سليمة» وتخرج بصفر — **وصفرُ بنودٍ ليس سلامةً بل غيابُ قياس**.
EMPTY_MSG = ("⛔ **صفرُ بنودٍ في هذا الملفّ — ولا يُقرأ هذا سلامةً**: الحارسُ لم يفحص شيئاً "
             "(أهو مبتورٌ؟ أم المسارُ خطأ؟).")


def has_sound(token):
    """أفي هذا المقطع حرفٌ عربيٌّ يُنطَق؟ — «الكلمةُ» بلا حرفٍ علامةُ وقف."""
    return bool(LETTERS.search(token))


def check_item(it, pad_ms=0):
    """يعيد قائمةَ رموزِ العطب في بندٍ واحد — فارغةٌ إن سلم."""
    bad = []
    ref = it.get("refText", "").split()
    wi = it.get("wordIndex")
    if not ref or not isinstance(wi, int):
        return ["wordcount_mismatch"]
    if it.get("wordCount") != len(ref):
        bad.append("wordcount_mismatch")
    if not (0 < wi < len(ref) - 1):
        bad.append("index_not_internal")
        return bad                       # ما بعده يقرأ `ref[wi]` فلا يُقرأ على فهرسٍ باطل
    op = it.get("op")
    want = ref[wi] + " ↔ " + ref[wi + 1] if op == "SWAP" and wi + 1 < len(ref) else ref[wi]
    if "targetWord" in it and it["targetWord"] != want:
        bad.append("target_mismatch")
    if not has_sound(ref[wi]):
        bad.append("silent_target")
    cut = it.get("cutMs")
    if not (isinstance(cut, list) and len(cut) == 2 and 0 <= cut[0] < cut[1]):
        bad.append("cut_malformed")
        cut = None
    if op == "SWAP":
        sw = it.get("swapMs")
        if not (isinstance(sw, list) and len(sw) == 2 and 0 <= sw[0] < sw[1]):
            bad.append("swap_missing")
        elif cut:
            # ⛔ تطابقُ المقطعَين ⇒ تبديلُ الشيء بنفسِه: مخرَجٌ مطابقٌ للأصل حرفاً.
            #    وتداخلُهما بأكثرَ من الهامشَين ⇒ المقطعُ الثاني يبدأ قبل انتهاء الأوّل.
            if sw == cut or sw[0] < cut[1] - 2 * pad_ms:
                bad.append("swap_degenerate")
            elif sw[0] - cut[1] > SWAP_MAX_GAP_MS:
                bad.append("swap_gap_wide")
    if op in ("SUBSTITUTE", "INSERT"):
        dn = it.get("donor")
        if not isinstance(dn, dict):
            bad.append("donor_missing")
        else:
            if dn.get("word") == ref[wi]:
                bad.append("donor_same_word")
            if not has_sound(dn.get("word", "")):
                bad.append("silent_donor")
            dc = dn.get("cutMs")
            if not (isinstance(dc, list) and len(dc) == 2 and 0 <= dc[0] < dc[1]):
                bad.append("donor_cut_malformed")
    return bad


def check_plan(plan):
    """يعيد (‏رمزُ العطب → قائمةُ المعرّفات) لخطّةٍ كاملةٍ — والمعرّفُ المكرَّرُ يُعَدّ مرّةً."""
    pad = plan.get("padMs", plan.get("pad", 0)) or 0
    found, seen = {}, set()
    for it in plan.get("items", []):
        i = it.get("id", "<بلا معرّف>")
        if i in seen:
            found.setdefault("dup_id", []).append(i)
        seen.add(i)
        for code in check_item(it, pad):
            found.setdefault(code, []).append(i)
    return found


def report(path, plan):
    """يطبع حصيلةَ خطّةٍ ويعيد عددَ أصنافِ العطب القاتل."""
    items = plan.get("items", [])
    found = check_plan(plan)
    fatal = [c for c in found if c in FATAL]
    print(f"\n## `{os.path.basename(path)}` — **{len(items)}** بنداً")
    if not items:
        print(EMPTY_MSG)
        return 1
    if not found:
        print("✅ الحقيقةُ الأرضيّةُ سليمةٌ على كلّ شرطٍ يُفحص.")
        return 0
    print("\n| الحكم | العدد | من البنود |\n|---|---:|---|")
    for code, ids in sorted(found.items(), key=lambda kv: (kv[0] not in FATAL, kv[0])):
        label = FATAL.get(code) or WARN.get(code, code)
        pct = len(ids) / len(items) * 100 if items else 0
        print(f"| {label} | **{len(ids)}** ({pct:.1f}٪) | " + " · ".join(f"`{i}`" for i in ids[:4])
              + (" …" if len(ids) > 4 else "") + " |")
    if fatal:
        # ⭐ والسقفُ يُحسب لا يُقدَّر: بنودٌ لا يتغيّر صوتُها **لا تُكشَف أبداً**.
        dead = set(found.get("swap_degenerate", []))
        if dead:
            by_op = [it for it in items if it.get("op") == "SWAP"]
            print(f"\n⛔ **سقفُ `SWAP` بالبناء: {len(by_op) - len(dead)}/{len(by_op)} = "
                  f"{(len(by_op) - len(dead)) / len(by_op) * 100:.1f}٪** — فما فوقَه مستحيلٌ ولو أُصلح المحرك.")
    return len(fatal)


# ---- 🧼 والحقيقةُ الأرضيّةُ الأخرى: **العيّنةُ النظيفة** (`sample.json` · G1) ----
# ⛔ **ولِمَ تُفحص هي أيضاً:** الحقنُ يقيس الكشف، وهذه تقيس **الاتّهامَ الكاذب** — ودعواها
# أثقل: «هذا **نصُّ المصحف** في هذه الرواية، وهذا **صوتُ هذه الآية بعينها**». فبندٌ نصُّه من
# آيةٍ وصوتُه من أخرى **يُحسب اتّهاماً كاذباً في المحرك وهو تحريفٌ في العيّنة**. ⇒ تُقابَل
# بالأصول لا بنفسها: `text_<riwaya>.jz` و(سورة:آية) في الرابط.
SAMPLE_FATAL = {
    "s_wordcount_mismatch": "⛔ `wordCount` يخالف عدَّ `refText`",
    "s_text_drift": "⛔⛔ `refText` يخالف نصَّ المصحف في روايته",
    "s_ayah_mismatch": "⛔⛔ رابطُ الصوت (أو مفتاحُ السورة) لا يوافق آيةَ البند",
    "s_index_mismatch": "⛔ `globalIndex` لا يوافق (سورة:آية)",
    "s_cut_malformed": "⛔ نافذةُ القصّ معطوبةٌ أو مقلوبة",
    "s_source_unknown": "⛔ مصدرٌ بلا نوعٍ معروف",
    "s_id_mismatch": "⛔ المعرّفُ لا يوافق آيةَ البند",
    "s_dup_id": "⛔ معرّفٌ مكرَّر",
}
SAMPLE_WARN = {
    "s_stratum_mismatch": "⚠️ الطبقةُ تخالف عدَّ الكلمات",
    "s_reciter_unlisted": "⚠️ قارئٌ ليس في قائمة روايته",
}


def check_sample_item(it, ids=None, texts=None, reciters=None):
    """يعيد رموزَ العطب في بندِ عيّنةٍ نظيفة.

    [ids] (‏globalIndex → (سورة، آية)) و[texts] (‏رواية → قائمةُ الآيات) **إن توفّرا**؛
    ⛔ وغيابُهما **لا يُسكِت الحارس**: الفاحصُ يُعلن أنّ فحصَ المصحف **لم يجرِ** (‏درسُ
    «التخطّي الصامت»: اختبارٌ يتخطّى نفسَه يبقى أخضرَ وهو لا يفحص).
    """
    bad = []
    ref = it.get("refText", "").split()
    s, a, gi = it.get("surah"), it.get("ayah"), it.get("globalIndex")
    if it.get("wordCount") != len(ref):
        bad.append("s_wordcount_mismatch")
    if stratum_of_words(len(ref)) != it.get("stratum"):
        bad.append("s_stratum_mismatch")
    if ids is not None and gi in ids and ids[gi] != (s, a):
        bad.append("s_index_mismatch")
    if texts is not None:
        body = texts.get(it.get("riwaya")) or []
        if not (isinstance(gi, int) and 0 <= gi < len(body) and body[gi].split() == ref):
            bad.append("s_text_drift")
    if reciters is not None and it.get("reciter") not in reciters.get(it.get("riwaya"), ()):
        bad.append("s_reciter_unlisted")
    src = it.get("source") or {}
    kind = src.get("kind")
    if kind == "ayah_file":
        if not str(src.get("url", "")).endswith(f"{s:03d}{a:03d}.mp3"):
            bad.append("s_ayah_mismatch")
    elif kind == "cut_from_surah":
        if str(src.get("r2Key", "")).split("/")[-1] != f"{s:03d}.mp3":
            bad.append("s_ayah_mismatch")
        if not (0 <= src.get("startMs", -1) < src.get("endMs", -1)):
            bad.append("s_cut_malformed")
    else:
        bad.append("s_source_unknown")
    if not str(it.get("id", "")).endswith(f"{s:03d}{a:03d}"):
        bad.append("s_id_mismatch")
    return bad


# طبقاتُ الطول كما في `sample.py` بالضبط — تُكرَّر هنا كي يعمل الحارسُ **بلا أصول المصحف**.
STRATA = (("S", 1, 4), ("M", 5, 9), ("L", 10, 19), ("XL", 20, 10_000))


def stratum_of_words(n):
    for name, lo, hi in STRATA:
        if lo <= n <= hi:
            return name
    return None


def load_mushaf():
    """يحاول تحميلَ نصّ المصحف وفهرسِه من أصول التطبيق — ويعيد (ids, texts) أو (None, None).

    ⛔ والغيابُ **يُعلَن ولا يُبتلع**: الفاحصُ يطبع «لم يجرِ فحصُ المصحف» ليقرأه مَن يقرأ.
    """
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(os.path.dirname(root), "tools", "alignment"))
        sys.path.insert(0, os.path.join(root, "alignment"))
        from common import load_index, load_text  # noqa: E402
        index = load_index()
        ids = {}
        for s in index["surahs"]:
            for a in range(s["ayahs"]):
                ids[s["start"] + a] = (s["n"], a + 1)
        return ids, {r: load_text(r) for r in ("hafs", "warsh", "qalun")}
    except Exception as e:                                         # noqa: BLE001
        print(f"⚠️ تعذّر تحميلُ نصّ المصحف ({type(e).__name__}) ⇒ **لم يجرِ فحصُ النصّ**")
        return None, None


def check_sample(doc, ids=None, texts=None):
    """يعيد (‏رمزُ العطب → معرّفات) لعيّنةٍ نظيفةٍ كاملة."""
    meta = doc.get("meta") or {}
    reciters = meta.get("reciters")
    found, seen = {}, set()
    for it in doc.get("items", []):
        i = it.get("id", "<بلا معرّف>")
        if i in seen:
            found.setdefault("s_dup_id", []).append(i)
        seen.add(i)
        for code in check_sample_item(it, ids, texts, reciters):
            found.setdefault(code, []).append(i)
    return found


def report_sample(path, doc):
    """يطبع حصيلةَ عيّنةٍ نظيفةٍ ويعيد عددَ أصنافِ العطب القاتل."""
    ids, texts = load_mushaf()
    items = doc.get("items", [])
    found = check_sample(doc, ids, texts)
    fatal = [c for c in found if c in SAMPLE_FATAL]
    print(f"\n## `{os.path.basename(path)}` — **{len(items)}** بنداً (عيّنةٌ نظيفة)")
    if not items:
        print(EMPTY_MSG)
        return 1
    checked = "✅ ونصُّ كلِّ بندٍ قوبل بالمصحف" if texts is not None else \
              "⚠️ **ولم يُقابَل النصُّ بالمصحف** (الأصولُ غائبة) — فلا يُقرأ الأخضرُ تزكيةً للنصّ"
    if not found:
        print(f"✅ الحقيقةُ الأرضيّةُ سليمةٌ على كلّ شرطٍ يُفحص. {checked}")
        return 0
    print("\n| الحكم | العدد | من البنود |\n|---|---:|---|")
    for code, ids_ in sorted(found.items(), key=lambda kv: (kv[0] not in SAMPLE_FATAL, kv[0])):
        label = SAMPLE_FATAL.get(code) or SAMPLE_WARN.get(code, code)
        print(f"| {label} | **{len(ids_)}** | " + " · ".join(f"`{i}`" for i in ids_[:4])
              + (" …" if len(ids_) > 4 else "") + " |")
    print(checked)
    return len(fatal)


# ---- 🎙️ والحقيقةُ الأرضيّةُ الثالثة: **التلاوةُ الطويلة** (`long_plan.json` · g4/g4n) ----
# ⛔ **ولِمَ هي الأخطر:** البندُ هنا **آياتٌ متتاليةٌ موصولةٌ في تسجيلٍ واحد**، ونصُّه المرجعيُّ
# **سلسلةُ نصوصها بالترتيب**. فإن زلّ الترتيبُ أو سقطت آيةٌ من النصّ دون الصوت، صار المقياسُ
# يحاسب المحركَ على **ما لم يُطلب منه**، أو يعدّ آيةً مسموعةً «ضائعةً» — وهي أرقامُ `g4`/`g4n`
# التي بُني عليها أكبرُ عطبٍ في اللوحة. ⇒ يُقابَل النصُّ بالمصحف **آيةً آيةً بالترتيب**.
LONG_FATAL = {
    "l_wordcount_mismatch": "⛔ `wordCount` يخالف عدَّ `refText`",
    "l_text_drift": "⛔⛔ `refText` ليس سلسلةَ آياتِ المدى في المصحف بترتيبها",
    "l_id_mismatch": "⛔ المعرّفُ لا يوافق (سورة · أوّلُ آيةٍ · العدد)",
    "l_range_bad": "⛔ مدى الآيات غيرُ مقبول (‏`ayahs` أو `firstAyah` غائبٌ أو دون الواحد)",
    "l_duration_bad": "⛔ `durationSec` غائبٌ أو غيرُ موجب",
    "l_dup_id": "⛔ معرّفٌ مكرَّر",
}
LONG_WARN = {
    "l_duration_odd": "⚠️ المدّةُ بعيدةٌ جدّاً عن عدّ الكلمات (أقلُّ من 0.15ث أو أكثرُ من 3ث للكلمة)",
    "l_single_ayah": "⚠️ تسجيلٌ من آيةٍ واحدةٍ — ليس «تلاوةً طويلةً» وإن صحّ بناؤه (اختيارُ `--ayahs 1`)",
}


def check_long_item(it, texts=None, starts=None):
    """يعيد رموزَ العطب في بندِ تلاوةٍ طويلة. [starts] (سورة → فهرسُ أوّل آيةٍ عالميّ)."""
    bad = []
    ref = it.get("refText", "").split()
    s, first, n = it.get("surah"), it.get("firstAyah"), it.get("ayahs")
    if it.get("wordCount") != len(ref):
        bad.append("l_wordcount_mismatch")
    if not (isinstance(n, int) and n >= 1 and isinstance(first, int) and first >= 1):
        bad.append("l_range_bad")
        return bad                       # ما بعده يقرأ المدى فلا يُقرأ على مدىً باطل
    # ⚠️ والآيةُ الواحدةُ **منبِّهٌ لا قاتل**: بناؤها قد يصحّ (‏`--ayahs 1` اختيارٌ صريح)،
    #    لكنّها **لا تقيس ما وُجدت له المجموعة** (مسارُ الطويل) ⇒ تُقال ولا تُسقط شوطاً.
    if n == 1:
        bad.append("l_single_ayah")
    if texts is not None and starts is not None:
        body = texts.get(it.get("riwaya")) or []
        gi = starts.get(s)
        want = None
        if gi is not None and gi + first - 1 + n <= len(body):
            want = " ".join(body[gi + first - 1 + k] for k in range(n)).split()
        if want is None or want != ref:
            bad.append("l_text_drift")
    if not (isinstance(it.get("durationSec"), (int, float)) and it["durationSec"] > 0):
        bad.append("l_duration_bad")
    elif ref and not (0.15 <= it["durationSec"] / len(ref) <= 3.0):
        bad.append("l_duration_odd")
    if not str(it.get("id", "")).endswith(f"{s:03d}_{first:03d}x{n}"):
        bad.append("l_id_mismatch")
    return bad


def check_long(doc, texts=None, starts=None):
    """يعيد (‏رمزُ العطب → معرّفات) لخطّةِ تلاوةٍ طويلةٍ كاملة."""
    found, seen = {}, set()
    for it in doc.get("items", []):
        i = it.get("id", "<بلا معرّف>")
        if i in seen:
            found.setdefault("l_dup_id", []).append(i)
        seen.add(i)
        for code in check_long_item(it, texts, starts):
            found.setdefault(code, []).append(i)
    return found


def report_long(path, doc):
    """يطبع حصيلةَ خطّةِ تلاوةٍ طويلةٍ ويعيد عددَ أصنافِ العطب القاتل."""
    ids, texts = load_mushaf()
    starts = mushaf_starts()
    items = doc.get("items", [])
    found = check_long(doc, texts, starts)
    fatal = [c for c in found if c in LONG_FATAL]
    print(f"\n## `{os.path.basename(path)}` — **{len(items)}** تسجيلاً (تلاوةٌ طويلة)")
    if not items:
        print(EMPTY_MSG)
        return 1
    checked = ("✅ ونصُّ كلِّ تسجيلٍ قوبل بالمصحف آيةً آيةً" if texts and starts else
               "⚠️ **ولم يُقابَل النصُّ بالمصحف** (الأصولُ غائبة) — فلا يُقرأ الأخضرُ تزكيةً للنصّ")
    if not found:
        print(f"✅ الحقيقةُ الأرضيّةُ سليمةٌ على كلّ شرطٍ يُفحص. {checked}")
        return 0
    print("\n| الحكم | العدد | من البنود |\n|---|---:|---|")
    for code, ids_ in sorted(found.items(), key=lambda kv: (kv[0] not in LONG_FATAL, kv[0])):
        label = LONG_FATAL.get(code) or LONG_WARN.get(code, code)
        print(f"| {label} | **{len(ids_)}** | " + " · ".join(f"`{i}`" for i in ids_[:4])
              + (" …" if len(ids_) > 4 else "") + " |")
    print(checked)
    return len(fatal)


def mushaf_starts():
    """(سورة → فهرسُ أوّل آيةٍ عالميّ) أو `None` إن غابت الأصول — ولا يُبتلع الغياب."""
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(os.path.dirname(root), "tools", "alignment"))
        sys.path.insert(0, os.path.join(root, "alignment"))
        from common import load_index  # noqa: E402
        return {s["n"]: s["start"] for s in load_index()["surahs"]}
    except Exception:                                              # noqa: BLE001
        return None


def is_long(doc):
    """أهي تلاوةٌ طويلة؟ — من شكل البند: مدىً من آياتٍ لا آيةٌ واحدة."""
    items = doc.get("items") or []
    return bool(items) and "firstAyah" in items[0] and "ayahs" in items[0]


def is_sample(doc):
    """أهي عيّنةٌ نظيفةٌ أم خطّةُ حقن؟ — يُقرأ من شكل البند لا من اسم الملفّ."""
    items = doc.get("items") or []
    return bool(items) and "op" not in items[0] and "stratum" in items[0]


# ---- 🧪 اختبارٌ ذاتيٌّ (حالاتٌ مقيسةٌ من الدوالّ نفسِها قبل كتابتها) ----
_REF = "الحمد لله رب العالمين الرحمن الرحيم"


def _it(**kw):
    base = {"id": "t1", "op": "OMIT", "refText": _REF, "wordCount": 6, "wordIndex": 2,
            "targetWord": "رب", "cutMs": [1000, 2000]}
    base.update(kw)
    return base


def selftest():
    bad = 0

    def ok(name, got, want):
        nonlocal bad
        good = got == want
        print(f"  {'✅' if good else '⛔'} {name}: {got} · المتوقَّع {want}")
        bad += 0 if good else 1

    ok("بندٌ سليمٌ ⇒ لا عطب", check_item(_it()), [])
    ok("عدُّ الكلمات يكذب ⇒ يُمسَك", check_item(_it(wordCount=9)), ["wordcount_mismatch"])
    ok("وآخرُ كلمةٍ ليست موضعَ حقن", check_item(_it(wordIndex=5)), ["index_not_internal"])
    ok("وأوّلُها كذلك", check_item(_it(wordIndex=0)), ["index_not_internal"])
    ok("وهدفٌ يخالف فهرسَه", check_item(_it(targetWord="الرحيم")), ["target_mismatch"])
    ok("وقطعٌ مقلوب", check_item(_it(cutMs=[2000, 1000])), ["cut_malformed"])

    # ⛔ **الحالةُ التي أوجدت الحارس**: مقطعان متطابقان ⇒ الصوتُ لا يتغيّر.
    sw = _it(op="SWAP", targetWord="رب ↔ العالمين", swapMs=[1000, 2000])
    ok("تبديلُ المقطع بنفسِه ⇒ قاتل", check_item(sw), ["swap_degenerate"])
    ok("وتبديلٌ سليمٌ يمرّ", check_item(_it(op="SWAP", targetWord="رب ↔ العالمين",
                                            swapMs=[2100, 3000])), [])
    # والهامشُ يقضم من الفجوة: تداخلُ 60م.ث مع `padMs=30` **مسموحٌ بالبناء** لا عطب.
    ok("وتداخلُ الهامشَين وحدَه ليس عطباً",
       check_item(_it(op="SWAP", targetWord="رب ↔ العالمين", swapMs=[1940, 2500]), pad_ms=30), [])
    ok("وفجوةٌ واسعةٌ ⇒ منبِّهٌ لا قاتل",
       check_item(_it(op="SWAP", targetWord="رب ↔ العالمين", swapMs=[2500, 3000])), ["swap_gap_wide"])

    # ⚠️ **علامةُ الوقف «كلمةٌ» في العدّ وليست كلمةً في السمع** (‏مقيسٌ: صحيحةٌ 44 من 44).
    mark = "الحمد لله ۖ العالمين الرحمن الرحيم"
    ok("هدفٌ بلا صوتٍ ⇒ منبِّهٌ يُكتب",
       check_item(_it(refText=mark, targetWord="ۖ")), ["silent_target"])
    ok("والحرفُ العربيُّ صوتٌ", (has_sound("رب"), has_sound("ۖ"), has_sound("ۗ")), (True, False, False))

    sub = _it(op="SUBSTITUTE", donor={"word": "مالك", "cutMs": [10, 900]})
    ok("واستبدالٌ سليم", check_item(sub), [])
    ok("وبلا مانحٍ ⇒ لا خطأَ مصنوع", check_item(_it(op="SUBSTITUTE")), ["donor_missing"])
    ok("ومانحٌ هو المستبدَلةُ نفسُها",
       check_item(_it(op="INSERT", donor={"word": "رب", "cutMs": [10, 900]})), ["donor_same_word"])
    ok("ومانحٌ بلا صوت",
       check_item(_it(op="INSERT", donor={"word": "ۚ", "cutMs": [10, 900]})), ["silent_donor"])

    # 🧾 وعلى مستوى الخطّة: المعرّفُ المكرَّرُ يُمسَك، والجردُ يجمع الرموز.
    plan = {"padMs": 30, "items": [_it(), _it(), _it(id="t2", wordCount=9)]}
    got = check_plan(plan)
    ok("خطّةٌ فيها مكرَّرٌ ومعطوب", {k: len(v) for k, v in sorted(got.items())},
       {"dup_id": 1, "wordcount_mismatch": 1})

    # ---- 🧼 وحالاتُ العيّنة النظيفة ----
    TX = {"hafs": ["", "الحمد لله رب العالمين الرحمن الرحيم"], "warsh": ["", "غيرُ ذلك"]}
    IDS = {1: (1, 2)}

    def _s(**kw):
        base = {"id": "hafs_husary_muallim_001002", "riwaya": "hafs", "surah": 1, "ayah": 2,
                "globalIndex": 1, "stratum": "M", "wordCount": 6, "reciter": "husary_muallim",
                "refText": _REF,
                "source": {"kind": "ayah_file", "url": "https://x/001002.mp3",
                           "reciter": "husary_muallim"}}
        base.update(kw)
        return base

    R = {"hafs": ["husary_muallim", "minshawi"], "warsh": ["dosary"]}
    ok("بندُ عيّنةٍ سليمٌ ⇒ لا عطب", check_sample_item(_s(), IDS, TX, R), [])
    # ⛔⛔ **أخطرُ حالتَين**: نصٌّ ليس نصَّ المصحف · وصوتٌ من آيةٍ أخرى.
    ok("نصٌّ يخالف المصحف ⇒ قاتل",
       check_sample_item(_s(refText="الحمد لله رب العالمين الرحمن الرحيب", wordCount=6), IDS, TX, R),
       ["s_text_drift"])
    ok("ونصُّ روايةٍ أخرى في بندِ حفصٍ يُمسَك",
       check_sample_item(_s(riwaya="warsh", reciter="dosary"), IDS, TX, R), ["s_text_drift"])
    ok("ورابطُ صوتٍ من آيةٍ أخرى ⇒ قاتل",
       check_sample_item(_s(source={"kind": "ayah_file", "url": "https://x/001003.mp3"}), IDS, TX, R),
       ["s_ayah_mismatch"])
    ok("ومفتاحُ سورةٍ أخرى في المقصوص",
       check_sample_item(_s(source={"kind": "cut_from_surah", "r2Key": "audio/qalun/h/002.mp3",
                                    "startMs": 10, "endMs": 20}), IDS, TX, R), ["s_ayah_mismatch"])
    ok("ونافذةُ قصٍّ مقلوبة",
       check_sample_item(_s(source={"kind": "cut_from_surah", "r2Key": "audio/qalun/h/001.mp3",
                                    "startMs": 900, "endMs": 20}), IDS, TX, R), ["s_cut_malformed"])
    ok("ومصدرٌ بلا نوعٍ معروف", check_sample_item(_s(source={"kind": "x"}), IDS, TX, R),
       ["s_source_unknown"])
    ok("و`globalIndex` لا يوافق الآية", check_sample_item(_s(globalIndex=7), IDS, TX, R),
       ["s_text_drift"])   # ⚠️ وفهرسٌ خارجَ المصحف يُقرأ **انحرافَ نصٍّ** لا فهرساً وحدَه
    ok("ومعرّفٌ لا يوافق آيتَه", check_sample_item(_s(id="hafs_x_001009"), IDS, TX, R),
       ["s_id_mismatch"])
    ok("وطبقةٌ تخالف العدَّ ⇒ منبِّهٌ لا قاتل", check_sample_item(_s(stratum="XL"), IDS, TX, R),
       ["s_stratum_mismatch"])
    ok("وقارئٌ ليس في قائمة روايته", check_sample_item(_s(reciter="alafasy"), IDS, TX, R),
       ["s_reciter_unlisted"])
    # ⛔ **وغيابُ الأصول لا يُنتج خضرةً كاذبة**: فحصُ النصّ لا يجري، وسائرُ الشروط تعمل.
    ok("وبلا مصحفٍ: لا فحصَ نصٍّ ولا سكوتَ عن سواه",
       check_sample_item(_s(refText="كلامٌ آخرُ هنا", wordCount=3), None, None, R),
       ["s_stratum_mismatch"])
    ok("والطبقاتُ حدودُها كما في `sample.py`",
       tuple(stratum_of_words(n) for n in (1, 4, 5, 9, 10, 19, 20, 0)),
       ("S", "S", "M", "M", "L", "L", "XL", None))
    ok("وتمييزُ العيّنة من الخطّة من شكل البند",
       (is_sample({"items": [_s()]}), is_sample({"items": [_it()]}), is_sample({"items": []})),
       (True, False, False))
    ok("وعيّنةٌ فيها مكرَّرٌ", {k: len(v) for k, v in check_sample(
        {"items": [_s(), _s()]}, IDS, TX).items()}, {"s_dup_id": 1})

    # ---- 🎙️ وحالاتُ التلاوة الطويلة ----
    # مصحفٌ مصغَّرٌ: السورةُ 78 تبدأ عند الفهرس 1، وثلاثُ آياتٍ متتالية.
    LT = {"warsh": ["(صفرٌ)", "آيةٌ أولى هنا", "وآيةٌ ثانية", "وثالثةٌ أخيرة", "ورابعةٌ خارجَ المدى"]}
    ST = {78: 1}
    _long = {"id": "long_warsh_078_001x3", "riwaya": "warsh", "surah": 78, "firstAyah": 1,
             "ayahs": 3, "refText": "آيةٌ أولى هنا وآيةٌ ثانية وثالثةٌ أخيرة",
             "wordCount": 7, "durationSec": 12.0}

    def _lg(**kw):
        d = dict(_long)
        d.update(kw)
        return d

    ok("تسجيلٌ طويلٌ سليمٌ ⇒ لا عطب", check_long_item(_long, LT, ST), [])
    # ⛔⛔ **الحالةُ التي وُجد لها:** النصُّ ليس سلسلةَ آياتِ المدى — آيةٌ سقطت أو تبدّل ترتيبُها.
    ok("آيةٌ ناقصةٌ من النصّ ⇒ قاتل",
       check_long_item(_lg(refText="آيةٌ أولى هنا وثالثةٌ أخيرة", wordCount=5), LT, ST),
       ["l_text_drift"])
    ok("وترتيبٌ مقلوبٌ ⇒ قاتل",
       check_long_item(_lg(refText="وآيةٌ ثانية آيةٌ أولى هنا وثالثةٌ أخيرة"), LT, ST),
       ["l_text_drift"])
    ok("ومدىً يتجاوز آخرَ السورة ⇒ قاتلٌ لا انفجار",
       check_long_item(_lg(id="long_warsh_078_003x3", firstAyah=3), LT, ST),
       ["l_text_drift"])
    ok("وعدُّ الكلمات يكذب", check_long_item(_lg(wordCount=99), LT, ST), ["l_wordcount_mismatch"])
    # ⚠️ وتسجيلٌ من آيةٍ واحدةٍ **ليس تلاوةً طويلة** — والمجموعةُ كلُّها تفقد معناها به.
    # ⚠️ آيةٌ واحدةٌ: **منبِّهٌ لا قاتل** — ومعها ينكسر النصُّ والمعرّفُ فيظهر الثلاثةُ معاً.
    ok("وآيةٌ واحدةٌ ⇒ منبِّهٌ يُقال ولا يُسقط",
       check_long_item(_lg(ayahs=1, refText="آيةٌ أولى هنا", wordCount=3,
                           id="long_warsh_078_001x1", durationSec=4.0), LT, ST), ["l_single_ayah"])
    ok("ومدىً بلا عددٍ صحيحٍ ⇒ قاتل", check_long_item(_lg(ayahs=0), LT, ST), ["l_range_bad"])
    ok("ومدّةٌ صفريّةٌ أو غائبة", check_long_item(_lg(durationSec=0), LT, ST), ["l_duration_bad"])
    # ⚠️ ومدّةٌ بعيدةٌ عن عدّ الكلمات: منبِّهٌ لا قاتل (فالسكتاتُ والترتيلُ يوسّعان المدى).
    ok("ومدّةٌ 0.5ث لسبعِ كلماتٍ ⇒ منبِّه", check_long_item(_lg(durationSec=0.5), LT, ST),
       ["l_duration_odd"])
    ok("و30ث لسبعٍ ⇒ منبِّهٌ كذلك", check_long_item(_lg(durationSec=30.0), LT, ST),
       ["l_duration_odd"])
    ok("ومعرّفٌ لا يوافق مداه", check_long_item(_lg(id="long_warsh_078_002x3"), LT, ST),
       ["l_id_mismatch"])
    ok("وبلا مصحفٍ: لا فحصَ نصٍّ ولا سكوتَ عن سواه",
       check_long_item(_lg(refText="كلامٌ آخر", wordCount=99, durationSec=4.0), None, None),
       ["l_wordcount_mismatch"])
    ok("وتمييزُ الطويل من النظيف ومن الحقن",
       (is_long({"items": [_long]}), is_long({"items": [_s()]}), is_long({"items": [_it()]})),
       (True, False, False))
    ok("وخطّةٌ طويلةٌ فيها مكرَّر",
       {k: len(v) for k, v in check_long({"items": [_long, _long]}, LT, ST).items()},
       {"l_dup_id": 1})

    # ---- ⛔ ولا خضرةَ بلا شهادة: صفرُ بنودٍ **ليس سلامةً** (D-442) ----
    import io, contextlib
    def _rc(fn, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*args)
    ok("خطّةُ حقنٍ فارغةٌ ⇒ تُردّ لا تُزكّى", _rc(report, "x.json", {"items": []}), 1)
    ok("وعيّنةٌ نظيفةٌ فارغةٌ كذلك", _rc(report_sample, "x.json", {"items": []}), 1)
    ok("وتلاوةٌ طويلةٌ فارغةٌ كذلك", _rc(report_long, "x.json", {"items": []}), 1)
    ok("والمملوءةُ السليمةُ تُزكّى", _rc(report, "x.json", {"padMs": 30, "items": [_it()]}), 0)

    print("✅ الحارسُ سليمٌ على حالاته" if not bad else f"⛔ الحارسُ نفسُه معطوبٌ في {bad} حالة")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plans", nargs="*", help="ملفّاتُ خططٍ (‏يُقبل النمطُ النجميّ)")
    ap.add_argument("--selftest", action="store_true", help="يختبر الحارسَ على حالاتٍ مقيسة")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    paths = [p for pat in a.plans for p in sorted(_glob.glob(pat))]
    if not paths:
        raise SystemExit("⛔ لا خطّةَ تُفحص — سمِّ ملفّاً أو نمطاً")
    print("# 🧷 حارسُ الحقيقة الأرضيّة")
    fatal = 0
    for p in paths:
        doc = json.load(open(p, encoding="utf-8"))
        if is_long(doc):
            fatal += report_long(p, doc)
        elif is_sample(doc):
            fatal += report_sample(p, doc)
        else:
            fatal += report(p, doc)
    print(f"\n**الحصيلة:** {len(paths)} خطّةً · أصنافُ عطبٍ قاتلٍ: **{fatal}**")
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
