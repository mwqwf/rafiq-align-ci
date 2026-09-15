# -*- coding: utf-8 -*-
"""🧷 **مدقّقُ حزم التماثل** — أتزعم الحزمةُ اليومَ ما تقوله المرآةُ اليومَ؟

## الثغرةُ التي يسدّها (‏قِيست 2026-09-14 ولم تكن مسدودة)
حزمُ التماثل في `engine/recitation/src/test/resources/` هي **عقدُ** المرآة البايثونيّة
مع المحرك: اختبارُ `RecitationScorerParityTest` يعيد تشغيل **الحاكم الحقيقيّ** عليها
ويطابق أحكامَها حرفاً بحرف. فينتج عن ذلك:

    الاختبارُ يضمن:  المحرك == الحزمة
    ولا شيءَ يضمن:   المرآة  == الحزمة

⇒ فلو تغيّرت `scorer.py` ولم تُعَد الحزمةُ، **بقي الاختبارُ أخضرَ** (المحركُ لم يتغيّر)
وانحرفت المرآةُ عن المحرك **صامتةً** — والمرآةُ هي التي تُحسب بها كلُّ أرقام اللوحة.
وهذا المدقّقُ يضمن الضلعَ الناقص، فيصير الضمانُ متعدّياً: **المرآة == الحزمة == المحرك**.

## كيف يدقّق — وبغير طريقةٍ لكلِّ حزمةٍ بحسب ما تحتاجه
- `parity_fixture.tsv` — **يُعاد حسابُ الأحكام من صفوفها** (‏المرجعُ والمسموعُ محفوظان
  فيها) بإعداد `make_parity_fixture.cfg_for` نفسِه. ولا يحتاج فرضيّاتٍ ⇒ يعمل بلا شبكة.
- `norm_fixture.tsv` — **تُعاد توليداً** إلى ملفٍّ مؤقّتٍ وتُقابَل بايتاً ببايت
  (‏مُدخَلُها نصُّ المصحف وهو في المستودع).
- `parity_fixture_strict.tsv` · `locator_top_fixture.tsv` — **بـ`--check` الذي فيهما
  أصلاً** ⭐: ما له مدقّقٌ يُدقَّق به **لا بنسخةٍ ثانيةٍ من المنطق** تنحرف عنه.

⛔ **وما لا يدقّقه يُسمّى**: `parity_fixture.tsv` **لا يُعاد توليدُها** هنا لأنّ صفوفَها
من فرضيّاتٍ محفوظةٍ في R2 (‏`work/hyps_ar.json`) — فيُدقَّق **عمودُ الأحكام** لا اختيارُ
الصفوف. (‏ومنذ D-579 يُحدَّث ذلك العمودُ بلا شبكة: `make_parity_fixture --refresh-verdicts`.)

⭐ **وأُضيفت حزمتان 2026-09-15 (D-587):** `position_parity.tsv` و`snr_fixture.tsv` كانتا
مُستثنَيَتَين بحجّة «لا `--check` فيها ولا مُدخَلَ محلّيّاً» — **والحجّةُ لا تصحّ لهما**:
مُدخَلُ الأولى `sample.json` المُودَعةُ في الشجرة، والثانيةُ تولّد إشارتَها عدديّاً. وقِيس
أنّ كلتيهما تُعاد **بايتاً ببايت** بلا شبكة ⇒ دخلتا `audit_regen` كما دخلتها `norm_fixture`.

⛔ **وتبقى `long_anchor` خارجَه** — لا مولّدَ لها في `tools/tasmi_bench/` أصلاً ⇒ **سكوتُنا
عنها ليس حكماً بسلامتها**، وهي الحزمةُ الوحيدةُ الباقيةُ بلا حارس.

    python fixture_audit.py            # يدقّق ويخرج بـ1 عند أوّل انحراف
    python fixture_audit.py --selftest
"""
import argparse
import re
import importlib
import io
import os
import shutil
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources")
TAB, NL = chr(9), chr(10)


def _mods():
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
    import scorer
    return scorer


def rows_of(path):
    out = []
    for line in io.open(path, encoding="utf-8"):
        line = line.rstrip(NL)
        if not line.strip() or line.startswith("#"):
            continue
        out.append(line.split(TAB))
    return out


def audit_parity(path=None, limit_report=5):
    """يعيد حسابَ (‏الأحكام · الزوائد) من صفوف الحزمة بالمرآة اليومَ."""
    scorer = _mods()
    import make_parity_fixture as MP
    path = path or os.path.join(RES, "parity_fixture.tsv")
    code = {scorer.CORRECT: "C", scorer.MISSED: "M", scorer.SUBSTITUTED: "S",
            scorer.UNCERTAIN: "U", scorer.ADDED: "A"}
    bad, n = [], 0
    for f in rows_of(path):
        if len(f) < 5:
            continue
        name, ref, hyp, rw, verd = f[0], f[1], f[2], f[3], f[4]
        add = f[5] if len(f) > 5 else ""
        s = scorer.score(ref.split(), hyp, MP.cfg_for(rw))
        got = "".join(code[w[1]] for w in s["words"])
        got_add = " ".join(s["additions"])
        n += 1
        if got != verd or got_add != add:
            bad.append((name, verd, add, got, got_add))
    name = os.path.basename(path)
    if bad:
        print(f"⛔ **{name}**: انحرفت المرآةُ عن الحزمة في **{bad and len(bad)} من {n}** حالة:")
        for b in bad[:limit_report]:
            print(f"   · `{b[0]}`: الحزمةُ {b[1]!r}/{b[2]!r} · والمرآةُ اليومَ {b[3]!r}/{b[4]!r}")
        print("   ⇒ العلاجُ: `python tools/tasmi_bench/make_parity_fixture.py` ثمّ **اقرأ "
              "`engine-test`** — فالحزمةُ عقدٌ مع المحرك لا مخرَجُ أداةٍ يُحدَّث بلا شهادة.")
        return 1
    print(f"✅ **{name}**: المرآةُ تُطابق الحزمةَ في {n} حالة.")
    return 0


def audit_regen(module, path, extra=()):
    """يعيد توليدَ الحزمة إلى ملفٍّ مؤقّتٍ ويقابلها بايتاً ببايت."""
    _mods()
    mod = importlib.import_module(module)
    name = os.path.basename(path)
    tmpd = tempfile.mkdtemp(prefix="fixaudit_")
    tmp = os.path.join(tmpd, name)
    saved = getattr(mod, "OUT")
    saved_argv = sys.argv
    try:
        # ⛔ **وعزلُ `argv` شرطُ صحّة** (‏وقع فعلاً 2026-09-14): بعضُ المولّدات تقرأ
        #    `argv` بنفسها (`make_strict_parity_fixture --check`)، فنداءُ `main()`
        #    ومعه رايةُ المدقّق يُسقطها بـ«وسيطٌ غيرُ معروف» — **فالعطبُ في المدقّق
        #    يُقرأ عطباً في الحزمة**. ⇒ يُمرَّر لها اسمُها وحدَه.
        sys.argv = [module]
        mod.OUT = tmp
        for k, v in extra:
            setattr(mod, k, v)
        rc = mod.main()
        if rc not in (None, 0):
            print(f"⛔ **{name}**: سقط مولّدُها بالرمز {rc} ⇒ **لم تُدقَّق**")
            return 1
        a = io.open(path, encoding="utf-8").read()
        b = io.open(tmp, encoding="utf-8").read()
    finally:
        mod.OUT = saved
        sys.argv = saved_argv
        shutil.rmtree(tmpd, ignore_errors=True)
    if a != b:
        la, lb = a.split(NL), b.split(NL)
        diff = [i for i in range(max(len(la), len(lb)))
                if (la[i] if i < len(la) else None) != (lb[i] if i < len(lb) else None)]
        print(f"⛔ **{name}**: المُودَعُ يخالف ما يولّده `{module}` اليومَ "
              f"(أسطرٌ مختلفة: {len(diff)} · أوّلُها {diff[:3]}):")
        for i in diff[:3]:
            print(f"   · سطر {i + 1}: المُودَعُ {(la[i] if i < len(la) else '—')[:90]!r}")
            print(f"     واليومَ   {(lb[i] if i < len(lb) else '—')[:90]!r}")
        print(f"   ⇒ العلاجُ: `python tools/tasmi_bench/{module}.py` ثمّ **اقرأ `engine-test`**.")
        return 1
    print(f"✅ **{name}**: إعادةُ التوليد تُطابق المُودَع بايتاً ببايت.")
    return 0


def run_check(module, label):
    """⭐ **ما له `--check` يُدقَّق به لا بنسخةٍ ثانيةٍ من المنطق.**

    `make_strict_parity_fixture` و`make_locator_top_fixture` فيهما `--check` (‏لا يكتب ·
    يخرج بـ1 إن تخلّفت الحزمةُ) — فهو **مصدرُ الحكم**، ويُستدعى في عمليّةٍ مستقلّةٍ
    كي لا يختلط `argv` ولا حالةُ الوحدات.
    """
    import subprocess
    p = subprocess.run([sys.executable, os.path.join(HERE, module + ".py"), "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    tail = [x for x in (p.stdout + p.stderr).strip().split(chr(10)) if x.strip()][-2:]
    if p.returncode != 0:
        print(f"⛔ **{label}**: `{module} --check` خرج بـ{p.returncode}:")
        for t in tail:
            print("   · " + t[:160])
        print(f"   ⇒ العلاجُ: `python tools/tasmi_bench/{module}.py` ثمّ **اقرأ `engine-test`**.")
        return 1
    print(f"✅ **{label}**: `{module} --check` راضٍ.")
    return 0


ABSENT_MARK = "⛔ENGINE-ABSENT"


def audit_engine_absent(src=None, cfg=None):
    """🏷️ **معالمُ لا نظيرَ لها في المحرك — أكلُّها مطفأةٌ افتراضاً؟**

    ⛔ **لِمَ حارسٌ لا مجرّدُ عادةٍ:** المرآةُ صورةُ الحاكم، وفيها اليومَ معالمُ **وُضعت
    لتُسعَّر قاعدةٌ قبل أن تُكتب بالكوتلن** (D-443 · D-445). ومع إطفائها **صفرُ تغيير**
    وبصماتُ التماثل كما هي — فإن أُشعل افتراضُ واحدٍ منها صارت المرآةُ **تحكم بغير ما
    يحكم به المحرك**، و**كلُّ رقمٍ تطبعه كذبٌ لا يصرخ** (‏وبصمةُ التماثل تمسكه، لكنّ هذا
    الحارسَ يسمّي السببَ في سطرٍ بدل أن يُترك للتخمين).

    ⭐ **والقائمةُ تُشتقّ من الوسم في الشفرة لا تُكتب بيدٍ** — فجدولٌ مكتوبٌ يتقادم بأوّل
    معلَمٍ جديدٍ يُضاف بلا ذكرٍ فيه، وهو بعينه ما وقع لعدّة الاختبارات الذاتيّة.
    """
    SCR = _mods()
    if src is None:
        src = open(os.path.join(HERE, "scorer.py"), encoding="utf-8").read()
    cfg = SCR.Config() if cfg is None else cfg
    names = [m.group(1) for m in re.finditer(
        r"self\.([A-Za-z_][A-Za-z_0-9]*)\s*=[^\n]*" + re.escape(ABSENT_MARK), src)]
    if not names:
        print(f"⛔ **صفرُ معالمَ موسومةٍ بـ`{ABSENT_MARK}`** — إمّا انكسر الاشتقاقُ وإمّا "
              "أُزيل الوسمُ. ⇒ **لا يُقرأ هذا «لا معالمَ غريبة»**.")
        return 1
    bad = [n for n in names if getattr(cfg, n, None)]
    print(f"🏷️ معالمُ لا نظيرَ لها في المحرك: **{len(names)}** ({' · '.join(names)})")
    if bad:
        print("⛔⛔ **وافتراضُها مُشعَلٌ** في: " + " · ".join(f"`{n}`" for n in bad)
              + " ⇒ **المرآةُ تحكم بغير ما يحكم به المحرك** ولا يُقرأ منها رقمٌ حتى تُطفأ.")
        return 1
    print("✅ **وكلُّها مطفأةٌ افتراضاً** ⇒ المرآةُ تبقى مرآةً.")
    return 0


def audit_all():
    rc = 0
    rc |= audit_engine_absent()
    rc |= audit_parity()
    rc |= run_check("make_strict_parity_fixture", "parity_fixture_strict.tsv")
    rc |= run_check("make_locator_top_fixture", "locator_top_fixture.tsv")
    rc |= audit_regen("make_norm_fixture", os.path.join(RES, "norm_fixture.tsv"))
    # ⭐ D-587: هاتان كانتا مُستثنَيَتَين بحجّة «لا مُدخَلَ محلّيّاً» — والحجّةُ لا تصحّ:
    #    `make_position_parity` مُدخَلُه `sample.json` المُودَعة، و`make_snr_fixture`
    #    يولّد إشارتَه عدديّاً. وكلتاهما تُعاد **بايتاً ببايت** بلا شبكة (قِيس).
    rc |= audit_regen("make_position_parity", os.path.join(RES, "position_parity.tsv"))
    rc |= audit_regen("make_snr_fixture", os.path.join(RES, "snr_fixture.tsv"))
    print("\n" + ("⛔ **حزمةٌ واحدةٌ على الأقلّ لا تُطابق المرآةَ اليومَ** — ولا يُقرأ رقمٌ من "
                  "المرآة حتى تُسوّى وتُشهَد."
                  if rc else "✅ الحزمُ **الستُّ** تُطابق المرآةَ اليومَ ⇒ **المرآة == الحزمة =="
                  " المحرك** (‏والضلعُ الأخيرُ يضمنه `RecitationScorerParityTest` في العدّاء)."))
    return rc


def selftest():
    """⛔ **ومدقّقٌ لا يُجرَّب على انحرافٍ مصنوعٍ ليس مدقّقاً.**"""
    ok = True
    src = os.path.join(RES, "parity_fixture.tsv")
    if not os.path.exists(src):
        print(f"⛔ لا حزمةَ في {src} ⇒ الضابطُ **لم يُقَس**")
        return 1
    if audit_parity(src, limit_report=1) != 0:
        print("⛔ الحزمةُ المُودَعةُ نفسُها منحرفةٌ ⇒ يُسوّى ذلك أوّلاً (وليس عطبَ الضابط)")
        ok = False
    # ⛔ وضابطُ عزل `argv`: المدقّقُ يُستدعى ومعه رايةٌ خاصّةٌ به، فلا يجوز أن تسقط
    #    الحزمُ لأنّ مولّداً قرأ رايتَنا (‏العطبُ الذي وقع فعلاً).
    keep = sys.argv
    try:
        sys.argv = [keep[0], "--only", "norm"]
        if audit_regen("make_norm_fixture", os.path.join(RES, "norm_fixture.tsv")) != 0:
            print("⛔ عزلُ argv: سقطت حزمةُ التطبيع ومعها رايةُ المدقّق ⇒ العزلُ لا يعمل")
            ok = False
    finally:
        sys.argv = keep
    tmpd = tempfile.mkdtemp(prefix="fixaudit_st_")
    try:
        # ① حرفُ حكمٍ واحدٌ يُقلب ⇒ **يجب** أن يُمسَك
        bent = os.path.join(tmpd, "bent.tsv")
        lines = io.open(src, encoding="utf-8").read().split(NL)
        for i, ln in enumerate(lines):
            if ln.startswith("#") or TAB not in ln:
                continue
            f = ln.split(TAB)
            if len(f) >= 5 and f[4]:
                f[4] = ("M" if f[4][0] != "M" else "C") + f[4][1:]
                lines[i] = TAB.join(f)
                break
        io.open(bent, "w", encoding="utf-8").write(NL.join(lines))
        if audit_parity(bent, limit_report=1) == 0:
            print("⛔ الضابطُ لم يمسك حرفَ حكمٍ مقلوباً — فهو لا يدقّق شيئاً")
            ok = False
        # ② وعمودُ زوائدَ محرَّفٌ يُمسَك كذلك
        bent2 = os.path.join(tmpd, "bent2.tsv")
        lines2 = io.open(src, encoding="utf-8").read().split(NL)
        for i, ln in enumerate(lines2):
            if ln.startswith("#") or TAB not in ln:
                continue
            f = ln.split(TAB)
            if len(f) >= 6:
                f[5] = (f[5] + " زائدةٌ").strip()
                lines2[i] = TAB.join(f)
                break
        io.open(bent2, "w", encoding="utf-8").write(NL.join(lines2))
        if audit_parity(bent2, limit_report=1) == 0:
            print("⛔ الضابطُ لم يمسك عمودَ زوائدَ محرَّفاً")
            ok = False
        # ③ وحزمةٌ سليمةٌ لا تُنذَر (‏نسخةٌ حرفيّةٌ)
        clean = os.path.join(tmpd, "clean.tsv")
        shutil.copyfile(src, clean)
        if audit_parity(clean, limit_report=1) != 0:
            print("⛔ الضابطُ أنذر بحزمةٍ سليمةٍ (إنذارٌ كاذب)")
            ok = False
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
    # 🏷️ وضوابطُ حارس «لا نظيرَ لها في المحرك» — ثلاثُ حالاتٍ تُعرف أجوبتُها
    class _Fake:
        pass
    f = _Fake()
    f.unheard_lexicon = {"x"}
    line = "self.unheard_lexicon = unheard_lexicon  " + ABSENT_MARK
    if audit_engine_absent(src=line, cfg=f) != 1:
        print("⛔ معلَمٌ **مُشعَلٌ** يجب أن يُسقط الحارس")
        ok = False
    f2 = _Fake()
    f2.unheard_lexicon = None
    if audit_engine_absent(src=line, cfg=f2) != 0:
        print("⛔ ومطفأٌ يجب أن يمرّ (وإلّا صار الحارسُ يردّ كلَّ شيء)")
        ok = False
    # ⛔⛔ والأهمّ: **صفرُ وسمٍ لا يُقرأ سلامةً** (‏درسُ «لا خضرةَ بلا شهادة»)
    if audit_engine_absent(src="self.x = 1", cfg=f2) != 1:
        print("⛔ صفرُ معالمَ موسومةٍ يجب أن يُقرأ «انكسر الاشتقاقُ» لا «لا معالمَ»")
        ok = False
    print("✅ المدقّقُ يمسك الانحرافَ المصنوعَ ولا يُنذر بالسليم."
          if ok else "⛔ سقط ضابطُ المدقّق")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--only", default="", choices=["", "parity", "strict", "norm", "locator", "absent"])
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.only == "absent":
        return audit_engine_absent()
    if a.only == "parity":
        return audit_parity()
    if a.only == "strict":
        return run_check("make_strict_parity_fixture", "parity_fixture_strict.tsv")
    if a.only == "locator":
        return run_check("make_locator_top_fixture", "locator_top_fixture.tsv")
    if a.only == "norm":
        return audit_regen("make_norm_fixture", os.path.join(RES, "norm_fixture.tsv"))
    return audit_all()


if __name__ == "__main__":
    raise SystemExit(main())
