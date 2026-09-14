# -*- coding: utf-8 -*-
"""🪞 **حارسُ المرآة** — أيُّ ملفٍّ في `rafiq-align-ci` تخلّف عن أصله في `QuranRafiq`؟

⛔ **لِمَ وُجد:** أدواتُ المقعد تعيش في مستودعَين — الأصلُ في `QuranRafiq/tools/tasmi_bench`
والمرآةُ هنا حيث تعمل مسارات GitHub. **وانحرافُ المرآة لا يصرخ: يعطي رقماً معقولاً وخاطئاً.**
وقد كلّف هذا ليلةَ 2026-09-12/13 ثلاثَ مرّات:

1. مفتاحُ نموذجٍ أُضيف في الأصل ولم يُنسخ ⇒ مُرِّر الاسمُ حرفاً إلى `whisper-cli` فمات الشوطُ
   كلُّه بـ«failed to initialize whisper context» — **وكلُّ بندٍ فيه خطأ**.
2. `cli_time.py` أُصلح في الأصل ولم يُنسخ ⇒ شوطان على `arm64`.
3. **وأخطرُها صامت:** `scorer.py` — **الحاكمُ نفسُه** — تخلّف عن ثلاث قواعدِ إمالةٍ
   (‏D-402/403/404) و`snr_probe.py` بقي على عتبتَي 8/15 وقد صارتا 14/18 (‏D-344)
   ⇒ **مرآةٌ تحكم بغير ما يحكم به المحرك، وتطبع نسبةً لا تنقصها إلّا الصحّة.**

    python tools/tasmi_bench/mirror_check.py            # يطبع ويخرج بـ1 إن وُجد انحراف
    python tools/tasmi_bench/mirror_check.py --sync     # ينسخ الأصلَ فوق المرآة
"""
import argparse
import filecmp
import marshal
import os
import re
import shutil
import sys

# ⛔ **ثالثةُ ثلاثٍ في ليلةٍ:** أداةٌ تُشغَّل بلا بيئةٍ مضبوطةٍ تسقط بـ`UnicodeEncodeError`
# على رسالةِ **نجاحها** فيُظنّ العطبُ في المفحوص لا في الفاحص. ⇒ تفرض ترميزها بنفسها.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "QuranRafiq", "tools", "tasmi_bench"))
# مجلداتٌ مولَّدةٌ أو مؤقّتةٌ لا يُسأل عن مرآتها
IGNORED_DIRS = {"__pycache__", "work", "requests", "patches", ".pytest_cache"}


def classify_callers(callers, wf_dir):
    """أيُّ أداةٍ من [callers] **يشغّلها مسارٌ** في `wf_dir`؟ ⇒ [(الأداة، ملفُّ المسار)].

    ⛔ **والنداءُ يُعرَف باسم الملفّ كاملاً** (`x.py`) لا بجذره: `riwaya_gate_arms` يذكره
    `slip_dagger_gate_arm.py` في شرحه — وذلك **ليس تشغيلاً**. والمسارُ وحدَه يُشغّل.
    """
    out = []
    if not os.path.isdir(wf_dir):
        return out
    texts = {}
    for w in sorted(os.listdir(wf_dir)):
        if not w.endswith((".yml", ".yaml")):
            continue
        try:
            texts[w] = open(os.path.join(wf_dir, w), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
    for c in callers:
        for w, t in texts.items():
            if c in t:
                out.append((c, w))
                break
    return out


COMMENT_ONLY = re.compile(r"^\s*(#.*)?$")


def appended_tail(mir_path, src_path):
    """⛔ **سابعةُ الثغرات (‏قِيست 10:50Z 2026-09-14): `--sync` كان يمحو قياسَ غيري.**

    وُجد `net_guard.py` منحرفاً، فأمر الحارسُ بـ`--sync` **بلا شرط**. وحقيقةُ الانحراف:
    ملفُّ المرآة = **الأصلُ بايتاً ببايت + سطرَي تعليقٍ في آخره** كتبتهما مناوبةٌ أخرى
    مسباراً لزنادٍ (`11c6ea9`: «أتشتعل `bench-selftest` على دفعةٍ بلا وسمِ تخطٍّ؟»)
    ⇒ **والنسخُ كان يمحو تجربةً جارية** وسؤالاً لم يُجَب بعد، وهو نقضُ قاعدةِ الأسطول:
    «مَن وجد مسارَ غيره مشغولاً فلا يلمسه — يكتب ما رأى ويمضي».

    ⇒ يُعيد **الذيلَ** (بايتاتٍ) إن كان ملفُّ المرآة يبدأ بالأصل كلِّه وفيه زيادةٌ بعده،
    و`None` إن كان الاختلافُ في **جسم** الملفّ (‏تخلُّفٌ حقيقيٌّ يُنسخ).
    ⛔ **وأصلٌ فارغٌ لا يُعدّ بادئةً لأحد** — وإلّا صار كلُّ ملفٍّ «ذيلاً مُلحَقاً».
    """
    try:
        a = open(mir_path, "rb").read()
        b = open(src_path, "rb").read()
    except OSError:
        return None
    if not b or len(a) <= len(b) or not a.startswith(b):
        return None
    return a[len(b):]


def append_kind(name, tail, mir_path, src_path):
    """⇒ `(kind, reason, first_line)` حيث `kind` ∈ {`"تعليق"`, `None`}.

    ⭐⭐ **والحكمُ بالمُنفَّذ لا بالرسم:** «ذيلٌ تعليقٌ» دعوى تُقاس، لا تُصدَّق بالعين —
    فسطرٌ مُلحَقٌ في آخر ملفٍّ بايثونَ **يُنفَّذ**، وسطرُ `THRESHOLD = 0.01` في آخر حاكمٍ
    يُلغي عتبتَه فوقَه ويطبع رقماً معقولاً خاطئاً. ⇒ فشرطانِ مجتمعان لا واحد:
    ① كلُّ سطرٍ في الذيل فراغٌ أو `#`، ② **وترجمةُ الملفَّين واحدةٌ** (`compile` ثمّ
    `marshal`) ⇒ **ما يُنفَّذ سواءٌ بالقياس**، فلا رقمَ يتغيّر.

    ⛔ **وما لا يُقاس فيه أثرُ الذيل يُحسب انحرافاً**: `.json` **يَبطل بالإلحاق** أصلاً
    (فلا يُقرأ)، و`.sh` لا مِيزانَ ترجمةٍ له هنا ⇒ كلاهما إلى قائمة العطب، **والتسامحُ
    لا يُمنح إلّا حيث قِيس**. ⭐ وهذا يجعل الحارسَ أصعبَ خداعاً لا أضعف: مَن أراد
    تمريرَ شفرةٍ خلف «تعليقٍ» كسرَ الشرطَ الثاني فسقط.
    """
    first = ""
    try:
        txt = tail.decode("utf-8")
    except UnicodeDecodeError:
        return None, "ذيلٌ ليس نصّاً مقروءاً", first
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    first = lines[0].strip() if lines else "(فراغٌ محض)"
    if not all(COMMENT_ONLY.match(ln) for ln in txt.splitlines()):
        return None, "في الذيل سطرٌ ليس تعليقاً ولا فراغاً ⇒ **شفرةٌ تُنفَّذ**", first
    if not name.endswith(".py"):
        return None, "نوعٌ لا يُقاس فيه أثرُ الذيل (‏`.json` يَبطل بالإلحاق) ⇒ لا تسامح", first
    try:
        ca = marshal.dumps(compile(open(mir_path, encoding="utf-8").read(), "m", "exec"))
        cb = marshal.dumps(compile(open(src_path, encoding="utf-8").read(), "m", "exec"))
    except (SyntaxError, ValueError) as e:
        return None, f"لا تُترجَم إحداهما ⇒ لا قياسَ: {type(e).__name__}", first
    if ca != cb:
        return None, "**ترجمتُهما تختلف** — فالذيلُ يغيّر ما يُنفَّذ ولو رُسم تعليقاً", first
    return "تعليق", "ترجمةُ الملفَّين واحدةٌ بالقياس ⇒ لا رقمَ يتغيّر", first


def _selftest_appended():
    """⛔ ويُختبر التصنيفُ الجديدُ بحالاتٍ تُعرف أجوبتُها — وفيها **ضابطٌ سالب**."""
    import tempfile
    bad = 0
    base = "# -*- coding: utf-8 -*-\nT = 0.05\n\n\ndef f():\n    return T\n"
    cases = [
        ("py: ذيلُ تعليقٍ وفراغ ⇒ تعليقٌ مقيس", "g.py", base, base + "\n# 🧪 مسبارٌ\n", "تعليق"),
        ("⛔ py: ذيلُ شفرةٍ يلغي عتبةً ⇒ انحراف", "g.py", base, base + "T = 0.01\n", None),
        ("⛔ py: «تعليقٌ» يكسر الترجمة ⇒ انحراف", "g.py", base, base + "#x\nT=1\n", None),
        ("⛔ sh: تعليقٌ لا مِيزانَ له ⇒ انحراف", "g.sh", "set -e\n", "set -e\n# مسبار\n", None),
        ("⛔ json: تعليقٌ يُبطل القراءة ⇒ انحراف", "g.json", '{"a":1}\n', '{"a":1}\n# x\n', None),
    ]
    with tempfile.TemporaryDirectory() as td:
        for i, (nm, fn, src_txt, mir_txt, want) in enumerate(cases):
            s = os.path.join(td, f"s{i}_{fn}")
            m = os.path.join(td, f"m{i}_{fn}")
            open(s, "w", encoding="utf-8").write(src_txt)
            open(m, "w", encoding="utf-8").write(mir_txt)
            tail = appended_tail(m, s)
            got = None if tail is None else append_kind(fn, tail, m, s)[0]
            ok = got == want
            print(f"  {'✅' if ok else '⛔'} {nm}: {got!r} · المتوقَّع {want!r}")
            bad += 0 if ok else 1
        # ⛔ واختلافٌ في الجسم ليس ذيلاً ولو زاد طولاً (‏تخلُّفٌ حقيقيٌّ يُنسخ)
        s = os.path.join(td, "body_s.py")
        m = os.path.join(td, "body_m.py")
        open(s, "w", encoding="utf-8").write("T = 0.05\n")
        open(m, "w", encoding="utf-8").write("T = 0.01\n# وذيلٌ أيضاً\n")
        ok = appended_tail(m, s) is None
        print(f"  {'✅' if ok else '⛔'} اختلافُ جسمٍ + ذيلٌ ⇒ انحرافٌ لا إلحاق")
        bad += 0 if ok else 1
        # ⛔ وأصلٌ فارغٌ لا يجعل المرآةَ «ذيلاً»
        open(s, "w", encoding="utf-8").write("")
        ok = appended_tail(m, s) is None
        print(f"  {'✅' if ok else '⛔'} أصلٌ فارغٌ ⇒ لا يُقرأ إلحاقاً")
        bad += 0 if ok else 1
        # ⭐⭐ والأهمُّ: **`--sync` لا يمحو الذيلَ** — يُقاس بالبايتات قبلَه وبعدَه
        mir = os.path.join(td, "rafiq-align-ci", "tools", "tasmi_bench")
        srcd = os.path.join(td, "QuranRafiq", "tools", "tasmi_bench")
        os.makedirs(mir); os.makedirs(srcd)
        open(os.path.join(srcd, "probe.py"), "w", encoding="utf-8").write(base)
        open(os.path.join(mir, "probe.py"), "w", encoding="utf-8").write(base + "\n# 🧪 مسبارٌ\n")
        open(os.path.join(srcd, "lag.py"), "w", encoding="utf-8").write("T = 0.05\n")
        open(os.path.join(mir, "lag.py"), "w", encoding="utf-8").write("T = 0.01\n")
        rc = check_pair(mir, srcd, True, "ضابط")
        after = open(os.path.join(mir, "probe.py"), encoding="utf-8").read()
        ok = after.endswith("# 🧪 مسبارٌ\n")
        print(f"  {'✅' if ok else '⛔'} `--sync` أبقى الذيلَ (‏قياسُ غيري لا يُمحى): {after[-14:]!r}")
        bad += 0 if ok else 1
        lag = open(os.path.join(mir, "lag.py"), encoding="utf-8").read()
        ok2 = lag == "T = 0.05\n"
        print(f"  {'✅' if ok2 else '⛔'} وفي الدفعة نفسِها نُسخ المتخلّفُ الحقيقيّ: {lag!r}")
        bad += 0 if ok2 else 1
        ok3 = rc == 0
        print(f"  {'✅' if ok3 else '⛔'} وذيلُ تعليقٍ مقيسٍ لا يُسقط الحارسَ بعد النسخ: rc={rc}")
        bad += 0 if ok3 else 1
        # ⛔ وذيلُ شفرةٍ **يُسقط** الحارسَ ولا يُنسخ عليه
        open(os.path.join(mir, "probe.py"), "w", encoding="utf-8").write(base + "T = 0.01\n")
        rc2 = check_pair(mir, srcd, True, "ضابط")
        kept = open(os.path.join(mir, "probe.py"), encoding="utf-8").read().endswith("T = 0.01\n")
        print(f"  {'✅' if rc2 == 1 else '⛔'} ذيلُ شفرةٍ ⇒ يخرج بـ1: rc={rc2}")
        bad += 0 if rc2 == 1 else 1
        print(f"  {'✅' if kept else '⛔'} ولا يُنسخ عليه بلا إذنٍ صريح")
        bad += 0 if kept else 1
        # ⭐ والإذنُ الصريحُ يمحوه (‏بابٌ مفتوحٌ بمفتاحٍ لا بلا مفتاح)
        rc3 = check_pair(mir, srcd, True, "ضابط", take=True)
        gone = open(os.path.join(mir, "probe.py"), encoding="utf-8").read() == base
        print(f"  {'✅' if gone else '⛔'} و`--take-appended` ينسخ الأصلَ فوقه: rc={rc3}")
        bad += 0 if gone else 1
    return bad


def _selftest():
    """⛔ حارسُ التصنيف يُختبر قبل أن يُحكم به (‏قاعدةُ المالك) — بحالاتٍ تُعرف أجوبتُها."""
    import tempfile
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        wf = os.path.join(td, "workflows")
        os.makedirs(wf)
        open(os.path.join(wf, "live.yml"), "w", encoding="utf-8").write(
            "name: x\njobs:\n  a:\n    steps:\n      - run: python tools/tasmi_bench/parity_full.py --x\n")
        open(os.path.join(wf, "notes.txt"), "w", encoding="utf-8").write("locator_parity.py")
        cases = [
            ("أداةٌ يشغّلها مسارٌ ⇒ حيّة", ["parity_full.py"], [("parity_full.py", "live.yml")]),
            ("أداةٌ لا يشغّلها مسارٌ ⇒ نائمة", ["locator_parity.py"], []),
            ("⛔ وذِكرُها في ملفٍّ ليس مساراً (‏txt) لا يجعلها حيّة", ["locator_parity.py"], []),
            ("وقائمةٌ فارغةٌ لا تُخرج شيئاً", [], []),
        ]
        for name, callers, want in cases:
            got = classify_callers(callers, wf)
            ok = got == want
            print(f"  {'✅' if ok else '⛔'} {name}: {got} · المتوقَّع {want}")
            bad += 0 if ok else 1
        # ⛔ ومجلدُ مساراتٍ غائبٌ يُعيد فراغاً ولا يرمي (‏تُشغَّل الأداةُ من الأصل أيضاً).
        got = classify_callers(["parity_full.py"], os.path.join(td, "لا-وجود"))
        ok = got == []
        print(f"  {'✅' if ok else '⛔'} مجلدُ مساراتٍ غائبٌ ⇒ فراغٌ لا استثناء: {got}")
        bad += 0 if ok else 1
    # ⛔⛔ **وضابطُ الاتّجاه** (‏سادسةُ الثغرات): مقارنةُ مجلدٍ بنفسِه لا تُقرأ «لا انحراف».
    with tempfile.TemporaryDirectory() as td:
        same = os.path.join(td, "QuranRafiq", "tools", "tasmi_bench")
        os.makedirs(same)
        # ① لا مرآةَ ⇒ **يُرفض الحكم** (‏None) ولا يُقارَن المجلدُ بنفسِه
        got = resolve_dir(same, same, "ض")[0]
        ok = got is None
        print(f"  {'✅' if ok else '⛔'} أصلٌ بلا مرآةٍ ⇒ يُرفض الحكم: {got}")
        bad += 0 if ok else 1
        # ② ومرآةٌ موجودةٌ ⇒ **يُقلب الاتّجاه** إليها
        mir = os.path.join(td, "rafiq-align-ci", "tools", "tasmi_bench")
        os.makedirs(mir)
        got2 = resolve_dir(same, same, "ض")[0]
        ok2 = got2 is not None and os.path.realpath(got2) == os.path.realpath(mir)
        print(f"  {'✅' if ok2 else '⛔'} أصلٌ ومرآةٌ ⇒ يُقلب الاتّجاه: {got2}")
        bad += 0 if ok2 else 1
        # ③ واتّجاهٌ صحيحٌ أصلاً يُمرَّر كما هو
        got3 = resolve_dir(mir, same, "ض")[0]
        ok3 = os.path.realpath(got3) == os.path.realpath(mir)
        print(f"  {'✅' if ok3 else '⛔'} اتّجاهٌ سليمٌ يبقى كما هو: {got3}")
        bad += 0 if ok3 else 1
    bad += _selftest_appended()
    print("✅ التصنيفُ سليمٌ على حالاته" if not bad else f"⛔ التصنيفُ نفسُه معطوبٌ في {bad} حالة")
    return 1 if bad else 0


def resolve_dir(mir, src, label):
    """⛔⛔ **سادسةُ الثغرات (‏قِيست 2026-09-14): الحارسُ كان يُقارن الأصلَ بنفسِه.**

    `SRC` تُشتقّ من **موضع الملفّ الذي جرى** (`__file__`)، فإن شُغِّلت نسخةُ **الأصل**
    (‏من `QuranRafiq/` أو بمسارٍ مطلقٍ إليها من أيِّ مكان) صارت `SRC == HERE` حرفاً
    ⇒ **مقارنةُ مجلدٍ بنفسِه ⇒ «✅ لا انحراف» دائماً وأبداً**. وقد وقع ذلك مراراً
    في ليلة 09-13/14: قُرئ «لا انحراف» وفي المرآة انحرافٌ قائمٌ ومجلدٌ غائبٌ كامل.

    ⇒ فصار الحارسُ **يقلب الاتّجاه بنفسه** إن وُجدت مرآةٌ أخرى، **ويرفض الحكمَ** إن
    لم يجدها — ولا يقول «لا انحراف» عن مقارنةٍ لم تقع. ⭐ **وحارسٌ يُخدع بموضع تشغيله
    ليس حارساً.**
    """
    if os.path.realpath(mir) != os.path.realpath(src):
        return mir, src
    # نحن على الأصل: تُطلب المرآةُ في المستودع العامّ المعروف
    up = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(mir))))
    alt = os.path.join(up, "rafiq-align-ci", "tools", os.path.basename(os.path.realpath(mir)))
    if os.path.isdir(alt):
        print(f"🔄 **قُلب الاتّجاه لـ{label}**: جرت نسخةُ الأصل، والمرآةُ المفحوصةُ `{alt}`"
              " (‏ولولا القلبُ لقارن الأصلَ بنفسِه فقال «لا انحراف» بلا مقارنة).")
        return alt, src
    print(f"⛔ **لا يُحكم على {label}**: النسخةُ الجارية هي الأصلُ نفسُه ولا مرآةَ وُجدت في "
          f"`{alt}` ⇒ **المقارنةُ لم تقع** (ولا يُقرأ هذا «لا انحراف»). شغّلْ نسخةَ المرآة: "
          "`cd rafiq-align-ci && python tools/tasmi_bench/mirror_check.py`.")
    return None, src


def check_pair(HERE, src, sync, label, take=False):
    """يفحص مجلدَ مرآةٍ واحداً ضدّ أصله ويطبع، ويُعيد عددَ الانحرافات الباقية بعد العلاج.

    ⛔⛔ **خامسةُ الثغرات (2026-09-13) — والحارسُ كان يفحص مجلداً واحداً:** الفحصُ كان على
    `tools/tasmi_bench` وحدَه، **و`tools/finetune/` مُمرأًى أيضاً** وتناديه المساراتُ في كلّ
    شوط (`r2_put.py` في `emu-gate` و`tasmi-gate` و`arm-time` · و`prep.py` في `finetune-prep`).
    فوُجد فيه انحرافٌ قائمٌ **لم يكشفه أحد**: `target_audit.py` في المرآة هو **نسخةُ ما قبل
    D-316** (‏التي كانت تُسقط الآيةَ كلَّها فتعمى عن 3,582 آيةً — تغطيةُ 71.2٪ لا غير)، وتعليقُ
    `prep.py` باقٍ على الرقم المنسوخ. ⇒ **مرآةٌ تُخبر برقمٍ عُلم خطؤه** لو شُغِّلت.
    """
    if not os.path.isdir(src):
        print(f"⛔ لا مجلدَ أصلٍ لـ{label} في {src} — لا يُقرأ «لا انحراف» من غياب المقارَن به")
        return 1
    if not os.path.isdir(HERE):
        print(f"ℹ️ لا مجلدَ مرآةٍ لـ{label} هنا — لا يُفحَص")
        return 0
    print(f"— 🪞 **{label}**")
    a = argparse.Namespace(src=src, sync=sync)
    drift, missing, appended = [], [], []
    for f in sorted(os.listdir(HERE)):
        # ⛔⛔ **ولا `.py` وحدَها — ثغرةٌ وُجدت 2026-09-13 (D-374 وما بعده):** جسمُ **كلِّ** شوط
        # محاكٍ هو `ci_emu_run.sh` (‏وهو الذي يُنشئ الأذرعَ ويثبّت لغتَها)، وخُطَطُ الحقن
        # `inject_plan*.json` هي **المدخَلُ المقيسُ** الذي تُحسب عليه أرقامُ الحقن. فكان
        # الحارسُ يقرأ `.py` فقط ⇒ **انحرافُ سطرٍ في صدفةٍ أو بندٍ في خطّةٍ يمرّ صامتاً**
        # ويعطي أرقاماً معقولةً لعيّنةٍ غيرِ العيّنة. وعلّةُ وجودِ الحارس عينُها تُوجِب توسيعَه.
        # ⭐ (‏وفُحص يومَ التوسيع فلم يكن هناك انحرافٌ — فالتوسيعُ **منعٌ** لا إصلاح.)
        if not f.endswith((".py", ".sh", ".json")):
            continue
        o = os.path.join(a.src, f)
        if not os.path.exists(o):
            missing.append(f)
        elif not filecmp.cmp(os.path.join(HERE, f), o, shallow=False):
            # 🧪 **أشكالُ الاختلاف ثلاثةٌ لا شكلٌ واحد** (‏انظر `appended_tail`):
            #    تخلُّفٌ في الجسم · ذيلٌ مقيسُ الأثر · ذيلٌ يُحتمل أن يُنفَّذ.
            tail = None if take else appended_tail(os.path.join(HERE, f), o)
            if tail is None:
                drift.append(f)
            else:
                appended.append((f,) + append_kind(f, tail, os.path.join(HERE, f), o))

    # ⛔⛔ **وثغرةٌ ثالثةٌ سُدّت 2026-09-13 — وقعت في اليوم نفسِه:** الحلقةُ تمشي على **المرآة**،
    # فملفٌّ **في الأصل ولا نسخةَ له هنا** كان **لا يُرى البتّة**: أُضيف `hyps_time_ab.py` إلى
    # `QuranRafiq` وأُشير إليه في خطوةِ مسارٍ، فقال الحارسُ «لا انحراف» **وكان المسارُ سيسقط**
    # بـ«لا ملفّ» في العدّاء. ⇒ يُسرد الأصلُ أيضاً، والغائبُ عن المرآة **انحرافٌ يُنسخ بـ`--sync`**.
    absent = []
    for f in sorted(os.listdir(a.src)):
        if not f.endswith((".py", ".sh", ".json")):
            continue
        if not os.path.exists(os.path.join(HERE, f)):
            absent.append(f)

    if absent:
        print("⛔ **في الأصل ولا نسخةَ لها في المرآة** (‏وهذه تُسقط المساراتَ التي تناديها): "
              + " · ".join(absent))
        if a.sync:
            for f in absent:
                shutil.copyfile(os.path.join(a.src, f), os.path.join(HERE, f))
            print("↻ نُسخت الغائبةُ — أودِعها بمسارٍ صريح.")
        else:
            drift = drift + absent   # كي لا يخرج بـ0 والمرآةُ ناقصة

    # ⛔⛔ **ورابعةٌ — والحارسُ نفسُه كان أعمى عنها (2026-09-13):** الحلقتان تمشيان على
    # **الملفّات المسطَّحة** وحدَها، والأصلُ فيه مجلدُ `engine_judge/` (‏حاكمُ المحرك بالكوتلن)
    # **لا وجودَ له في المرآة البتّة** — فقال الحارسُ «لا انحراف» وفي المرآة **تسعُ أدواتٍ
    # تناديه بالاسم** (`parity_full` · `riwaya_surface` · `locator_parity` …). فمتى نادى
    # مسارٌ إحداها **سقط بـ«لا ملفّ»**، وذلك أوّلُ ما وُجد الحارسُ ليمنعه.
    # ⭐⭐ **ولا يُعالَج بنسخٍ تلقائيّ:** `QuranRafiq` **خاصّ**، و`engine_judge/` **مصدرُ محرّكٍ
    # بالكوتلن** — ونسخُه إلى المستودع العامّ **نشرٌ لا مزامنة**. ⇒ الغيابُ هنا **قرارٌ** لا
    # سهو، وواجبُ الحارس أن يقول **مَن سيسقط به** لا أن يملأه.
    danger = []
    for d in sorted(os.listdir(a.src)):
        if not os.path.isdir(os.path.join(a.src, d)) or d in IGNORED_DIRS:
            continue
        if os.path.isdir(os.path.join(HERE, d)):
            continue          # مُمرأًى فعلاً — وفحصُ داخله بابٌ آخرُ يُفتح حين يُمرأى شيء
        callers = []
        # ⛔ **والنداءُ يُعرَف بصورته لا بذكرِ الاسم**: مِن مسارٍ (`engine_judge/…`) أو من اسمٍ
        #    مقتبَسٍ في `os.path.join` — ولولا ذلك لعُدَّ **كلُّ ملفٍّ يشرح المجلدَ في تعليقه**
        #    نادياً له. ⭐ وهذا الحارسُ نفسُه يذكره في شرحه ⇒ **لا يعدّ نفسَه**.
        pat = re.compile(r'%s/|["\']%s["\']' % (re.escape(d), re.escape(d)))
        for f in sorted(os.listdir(HERE)):
            if not f.endswith((".py", ".sh")) or f == os.path.basename(__file__):
                continue
            try:
                if pat.search(open(os.path.join(HERE, f), encoding="utf-8", errors="replace").read()):
                    callers.append(f)
            except OSError:
                continue
        if callers:
            danger.append((d, callers))
    # ⛔⛔ **وخامسةٌ — الحارسُ كان يُنذر بما لا يعرف** (‏قِيس 2026-09-13 ‏22:3xZ): قال «أيُّ مسارٍ
    # يشغّلها يسقط» **ولم يسأل: أفي المرآة مسارٌ يشغّلها أصلاً؟** فأنفقتُ نداءاتٍ أُجيبُ سؤالاً
    # كان الحارسُ أقدرَ على جوابه: **صفرُ مسارٍ** في `.github/workflows/` ينادي أيّاً من العشرة.
    # ⇒ صار يفصّل: **نائمٌ** (لا مسارَ يشغّلها ⇒ ملاحظةٌ لا إنذار) أو **حيٌّ** (مسارٌ يناديها
    # ⇒ عطبٌ يُوقف الحارسَ بـ1). ⭐ **وحارسٌ يُنذر بما لا يقيسه يُعلّم قارئَه تجاهلَه.**
    live_any = []
    for d, callers in danger:
        live = classify_callers(callers, os.path.join(os.path.dirname(os.path.dirname(HERE)), ".github", "workflows"))
        print(f"⛔ **مجلدُ `{d}/` في الأصل ولا وجودَ له في المرآة، و{len(callers)} أداةً هنا "
              f"تناديه**: " + " · ".join(callers[:6]) + (" …" if len(callers) > 6 else ""))
        if live:
            live_any += [f"{d}/ ⇐ {c} (‏في {w})" for c, w in live]
            print("   ⛔⛔ **ومسارٌ حيٌّ يناديها فيسقط بـ«لا ملفّ»**: "
                  + " · ".join(f"{c} في {w}" for c, w in live))
        else:
            print("   ℹ️ **نائمٌ**: لا مسارَ في `.github/workflows/` يشغّل واحدةً منها "
                  "⇒ الغيابُ لا يُسقط شوطاً اليومَ (‏وتُشغَّل من الأصل حيث المجلدُ موجود).")
    if danger:
        print("⭐ **وليس علاجُه نسخاً**: قد يكون الغيابُ مقصوداً (‏مصدرُ محرّكٍ لا يُنشر في "
              "مستودعٍ عامّ) ⇒ فإمّا أن يُمرأى بقرارٍ صريح، وإمّا **ألّا يُنادى من المرآة**.")
    # ⛔ ولا يُدسّ الحيُّ في قائمة `drift`: تلك أسماءُ ملفّاتٍ يَنسخها `--sync`، ونسخُ مجلدِ
    #    محرّكٍ إلى مستودعٍ عامّ **نشرٌ** ⇒ يُحسب عطباً يُوقف الحارسَ، ولا يُعالَج بنسخ.

    if missing:
        # ⚠️ ملفٌّ هنا وليس في الأصل: **ليس انحرافاً** بالضرورة (قد يكون أداةَ مسارٍ خاصّةً
        # بالمستودع العامّ) — يُذكر ولا يُعالَج تلقائيّاً.
        print("ℹ️ هنا ولا أصلَ لها (تُراجَع بالعين): " + " · ".join(missing))

    # 🧪 **ذيلٌ مُلحَقٌ والأصلُ تحته بايتاً ببايت** — شكلٌ ثالثٌ بين «مطابقٍ» و«متخلّف»،
    # وهو في العادة **عملٌ جارٍ لمناوبةٍ أخرى** لا سهوٌ. ⇒ يُسمّى ولا يُمحى.
    app_bad = 0
    if appended:
        print("🧪 **ذيلٌ مُلحَقٌ في المرآة** (‏الأصلُ تحته بايتاً ببايت ⇒ **ليس تخلُّفاً**، "
              "وهو في الغالب مسبارُ مناوبةٍ أخرى):")
        for f, kind, why, first in appended:
            mark = "⚠️" if kind else "⛔"
            print(f"   {mark} {f}: {why} — «{first}»")
            app_bad += 0 if kind else 1
        print("⛔ **ولا يُنسخ عليه `--sync`**: النسخُ **يمحو قياساً حيّاً لغيرك** وسؤالاً لم "
              "يُجَب (‏وقع 10:50Z على `net_guard.py`) — «مَن وجد مسارَ غيره مشغولاً فلا يلمسه». "
              "⇒ فإن أردتَ محوَه فبإذنٍ صريحٍ وحدَه: `--sync --take-appended`.")
        if app_bad:
            print(f"⛔⛔ **و{app_bad} من الذيول يُحتمل أن تغيّر ما يُنفَّذ** ⇒ تُحسب عطباً "
                  "(‏والتسامحُ لا يُمنح إلّا حيث قِيس أنّ الترجمةَ واحدة).")
    if not drift:
        if app_bad:
            # ⛔ ولا «✅» على ذيلٍ لم يُقَس أثرُه — فالسكوتُ عنه يُقرأ تزكيةً.
            print("⛔ لا انحرافَ في جسم ملفٍّ — **لكنّ ذيلاً غيرَ مقيسٍ يُوقف الحارس** (فوقَه).")
            return 1
        # ⛔ ولا تُقال «✅» مجرّدةً وفوقَها تنبيهٌ — فالعينُ تقرأ آخرَ سطرٍ وتمضي.
        print("✅ لا انحرافَ في الملفّات: كلُّ ملفٍّ له أصلٌ مطابقٌ بايتاً ببايت."
              + (" ⚠️ **لكن فوقَه ما يُنظر فيه.**" if (danger or appended) else ""))
        if live_any:
            print("⛔ **ومع ذلك يخرج بـ1**: مسارٌ حيٌّ ينادي أداةً على مجلدٍ غائبٍ ⇒ "
                  + " · ".join(live_any))
            return 1
        return 0
    print("⛔ **انحرافُ مرآة** في " + str(len(drift)) + " ملفّاً:")
    for f in drift:
        print("   ≠ " + f)
    if a.sync:
        for f in drift:
            shutil.copyfile(os.path.join(a.src, f), os.path.join(HERE, f))
        print("↻ نُسخ الأصلُ فوق المرآة — راجع `git diff` قبل الإيداع."
              + (" ⛔ **وذيولُ الإلحاق لم تُلمَس** (فوقَه)." if appended else ""))
        return 1 if app_bad else 0
    print("⇒ `python tools/tasmi_bench/mirror_check.py --sync` ثمّ أودِع بمسارات صريحة"
          + (" — **ولن يمسّ ذيولَ الإلحاق أعلاه**." if appended else "."))
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC, help="أصلُ tasmi_bench (‏وأخواتُه تُشتقّ منه)")
    ap.add_argument("--sync", action="store_true", help="انسخ الأصلَ فوق المرآة (لا يحذف ولا يضيف)")
    ap.add_argument("--take-appended", action="store_true",
                    help="⛔ إذنٌ صريحٌ بمحو ذيلٍ مُلحَقٍ في المرآة (‏قد يكون قياسَ مناوبةٍ أخرى)")
    ap.add_argument("--only", default="", help="اسمُ مجلدٍ مُمرأًى واحدٍ يُفحَص وحدَه (‏للاختبار)")
    ap.add_argument("--selftest", action="store_true", help="يختبر تصنيفَ «حيٌّ أم نائم» على حالاتٍ معلومة")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    # 🪞 **كلُّ مجلدٍ مُمرأًى يُفحَص** — والقائمةُ هنا **مصدرٌ واحدٌ للحقيقة**: ما يُضاف إلى
    # المرآة يُضاف إليها، ⛔ **وإلّا فانحرافُه لا يراه أحدٌ حتى يُعطي رقماً خاطئاً**.
    pairs = [("tasmi_bench", os.path.dirname(os.path.abspath(__file__)), a.src)]
    tools_mir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tools_src = os.path.dirname(a.src)
    for d in ("finetune",):
        pairs.append((d, os.path.join(tools_mir, d), os.path.join(tools_src, d)))
    # ℹ️ **وحدُّ هذا الحارس يُقال صريحاً**: في المرآة مجلداتٌ أخرى لها أصلٌ هنا
    # (`alignment*` · `index_qa` · `ci_fleet` · `cloud*`) وهي **مرآةُ مناوبةٍ أخرى** (الفهرسة)
    # — لا تُفحَص هنا ولا تُلمَس. ⭐ **وتُسمّى كي لا يُقرأ سكوتُ الحارس عنها «لا انحرافَ فيها»**،
    # فمَن يملكها يضيفها إلى قائمته. (وتُحسب آليّاً فلا تتقادم القائمةُ إن ظهر مجلدٌ جديد.)
    named = {lbl for lbl, _, _ in pairs}
    others = []
    if os.path.isdir(tools_mir) and os.path.isdir(tools_src):
        for d in sorted(os.listdir(tools_mir)):
            if d in named or d in IGNORED_DIRS or not os.path.isdir(os.path.join(tools_mir, d)):
                continue
            if os.path.isdir(os.path.join(tools_src, d)):
                others.append(d)
    if others and not a.only:
        print("ℹ️ ولا يُفحَص هنا (مرآةُ مناوبةٍ أخرى — وسكوتُنا عنها **ليس** حكماً بسلامتها): "
              + " · ".join(others))
    rc = 0
    for label, mir, src in pairs:
        if a.only and a.only != label:
            continue
        mir2, src2 = resolve_dir(mir, src, label)
        if mir2 is None:
            rc = max(rc, 1)          # ⛔ مقارنةٌ لم تقع ⇒ سقوطٌ لا سكوت
            continue
        rc = max(rc, check_pair(mir2, src2, a.sync, label, take=a.take_appended))
    return rc


if __name__ == "__main__":
    sys.exit(main())
