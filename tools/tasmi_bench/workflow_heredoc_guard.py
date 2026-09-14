# -*- coding: utf-8 -*-
"""🪤 **فاحصُ فخِّ الـ`heredoc` في مسارات GitHub** — يُشغَّل قبل دفعِ أيِّ مسار.

⛔ **لِمَ وُجد — بعطبٍ وقع فعلاً 2026-09-13 وكلّف ثلاثةَ أشواطٍ وساعةً:** كتلةُ `run: |` في
YAML **تُزال منها الإزاحةُ الأساسُ وحدَها**. فإن كُتب `heredoc` داخلَ كتلةٍ `{ … }` أو قوسَين
`( … )` بإزاحةٍ زائدة، بقي لمُغلِقه **فراغٌ في أوّل السطر بعد إزالة الأساس** ⇒ **لا يُغلق**،
فيبتلع كلَّ ما بعده — **ومنه توجيهُ المخرَج إلى ملفّه** — فيسقط الشوطُ بلا أثرٍ يُقرأ.
⭐ **وأسوأُ ما فيه أنّه لا يصرخ:** `bash` ينفّذ ما جمعه ثمّ يخرج بصفرٍ أحياناً، فيُقرأ الفشلُ
في الخطوة التالية ويُظَنّ السببُ فيها (وقد ظننتُ «شجرةً وسخةً يرفضها الدمج» وكتبتُه).

    python workflow_heredoc_guard.py .github/workflows/*.yml   # يخرج بـ1 إن وُجد خطر
    python workflow_heredoc_guard.py --selftest                # يختبر نفسَه على حالاتٍ معلومة

⛔ **والحارسُ يُختبر قبل أن يُستعمل** (‏قاعدةُ المالك): `--selftest` فيه حالةٌ سليمةٌ وحالةُ
مُغلِقٍ غائبٍ وحالةُ مُغلِقٍ أعمقَ من الأساس **وحالةُ إيجابيّةٍ كاذبةٍ حقيقيّةٍ من مستودعنا**
(`printf 'list<<EOF\\n%s\\nEOF\\n'` — نصٌّ لا `heredoc`).
"""
import argparse
import glob
import re
import sys

RUN = re.compile(r"run:\s*\|")
OPEN = re.compile(r"<<-?\s*'?([A-Za-z_]\w*)'?")


def _indent(s):
    return len(s) - len(s.lstrip())


def run_blocks(lines):
    """(أساسُ الإزاحة، أسطرُ الكتلة) لكلِّ كتلة `run: |`."""
    out = []
    for i, l in enumerate(lines):
        if not RUN.search(l):
            continue
        ind = _indent(l)
        body = []
        for j in range(i + 1, len(lines)):
            s = lines[j]
            if s.strip() and _indent(s) <= ind:
                break
            body.append((j, s))
        base = min((_indent(s) for _, s in body if s.strip()), default=0)
        out.append((base, body))
    return out


def scan_text(text, name="<نصّ>"):
    """يعيد قائمةَ مخاطرَ: (الملفّ، السطر، الوسم، السبب)."""
    lines = text.split("\n")
    risky = []
    for base, body in run_blocks(lines):
        opens = {}
        for j, s in body:
            st = s.strip()
            # ⛔ **وتُستثنى الإيجابيّةُ الكاذبةُ المعروفة:** `<<EOF` داخلَ نصٍّ بين علامتَي اقتباس
            # (‏فاصلُ مخرَجاتِ GitHub: `printf 'list<<EOF\\n…'`) ليس `heredoc` بحال.
            m = OPEN.search(s)
            if m and not st.startswith("#") and "<<<" not in s and not re.search(r"['\"][^'\"]*<<", s):
                opens.setdefault(m.group(1), j)
            for tag, oj in list(opens.items()):
                if st == tag and j > oj:
                    if _indent(s) > base:
                        risky.append((name, j + 1, tag,
                                      f"مُغلِقٌ أعمقُ من أساس الكتلة ({_indent(s)} > {base}) ⇒ لا يُغلق"))
                    del opens[tag]
        for tag, oj in opens.items():
            risky.append((name, oj + 1, tag, "لا مُغلِقَ له في الكتلة"))
        risky += scan_block_shell(body, name)
    return risky


# 🪤 **فخّان آخران في كتل `run:` — كلاهما وقع في أسطولنا ليلةَ 2026-09-13/14 وقُيس اليومَ:**
#
# ⛔⛔ **والحارسُ يُضيَّق عمداً إلى ما يكتم فشلاً حقيقيّاً:** أوّلُ صياغةٍ أنذرت بـ**42 موضعاً**
# أكثرُها عرضٌ لا أداة (`ls | wc` · `lscpu | grep` · `cat | head`) — **وحارسٌ يُنذر بما لا يضرّ
# يُعلّم قارئَه تجاهلَه** (وهو الدرسُ الذي كتبتُه بنفسي قبل ساعات). ⇒ لا يُنذَر إلّا حيث **يسار
# الأنبوب أداةُ مشروعٍ** (`python` · `gradlew` · `bash tools/…`): تلك وحدَها يُقرأ فشلُها نجاحاً.
# ⛔ **والأنبوبُ `|` وحدَه لا `||`:** كان الاستثناءُ `"||" not in st` يُخفي هذا الخلطَ
#    (فـ`cmd || echo` كان يُقرأ أنبوباً ويُبرَّأ في آنٍ) ⇒ لمّا رُفع الاستثناءُ ظهر
#    الخلطُ إنذاراً كاذباً في حالةِ `finetune-audit` من مستودعنا. فصار الفصلُ في الرسم:
#    `|` لا يليه ولا يسبقه `|`. (‏وضابطُه في `--selftest`: الحالتان معاً.)
TOOL_PIPE = re.compile(r"(?:^|\s|\()(python3?|\./gradlew|gradlew|bash|sh)\s+[^|]*(?<!\|)\|(?!\|)\s*\S")
TEST_AND = re.compile(r"^\[\s.*\]\s*&&\s*\S")


def scan_block_shell(body, name):
    """يفحص كتلةً واحدةً عن فخَّي الصَّدَفة المقيسَين (‏الأنبوبُ الكاتم · والشرطُ الأخير)."""
    risky = []
    txt = "\n".join(s for _, s in body)
    has_pipefail = "pipefail" in txt
    for j, s in body:
        st = s.strip()
        if st.startswith("#") or not st:
            continue
        # ⛔ **الأنبوبُ يكتم فشلَ أوّله** (‏مقيسٌ: `false | tee f` يخرج بـ**صفر**): فحالةُ الخطوة
        # حالةُ **آخرِ** الأنبوب لا حالةُ الأداة ⇒ خطوةٌ «ناجحةٌ» وجدولُها لا وجودَ له (وقع فعلاً
        # في شوط `34795058366`). والعلاجُ `set -o pipefail` في أوّل الكتلة، أو فصلُ الأمرَين.
        # ⛔ **وما عولج صراحةً لا يُنذَر به** (‏إيجابيّتان كاذبتان من مستودعنا نفسِه):
        #    `… | tee` ثمّ `rc=${PIPESTATUS[0]}` — وهو **الصوابُ عينُه** · و`… || echo`.
        # ⛔⛔ **تصحيحٌ مقيسٌ 2026-09-14 ‏03:2xZ (مناوبةُ :50):** كان `||` يُعدّ «عِلاجاً صريحاً»
        #     فيُستثنى — **وهو ليس علاجاً البتّة**. المقيسُ بـ`bash`:
        #         set +o pipefail; false | tee /dev/null || echo x   ⇒ **لا يُطبع x**
        #         set -o pipefail; false | tee /dev/null || echo x   ⇒ **يُطبع x**
        #     أي أنّ `||` بلا `pipefail` **لا يشتعل أصلاً** لأنّ حالةَ الأنبوب حالةُ `tee`.
        #     ⭐ **والعطبُ الذي بُني هذا الحارسُ لأجله كان بهذه الصورة عينِها** (`… | tee
        #     work/triage.md || echo …` في `gate-anatomy`) ⇒ **فالحارسُ كان يُبرّئ ما وقع**.
        #     وبقيت `PIPESTATUS` استثناءً لأنّها تقرأ حالةَ الأداة فعلاً (وقِيس ذلك في
        #     `plan-riwaya`). ⇒ الحارسُ صار **أصعبَ خداعاً لا أضعف**.
        if (TOOL_PIPE.search(st) and not has_pipefail
                and "PIPESTATUS" not in txt):
            risky.append((name, j + 1, "أنبوب",
                          "أداةٌ في أنبوبٍ بكتلةٍ بلا `set -o pipefail` ⇒ فشلُها يُكتم"))
    # ⛔ **`[ … ] && …` آخرَ الكتلة**: حالةُ النصّ حالةُ آخرِ أمرٍ، فشرطٌ كاذبٌ ⇒ الخطوةُ **تسقط**
    # بلا خطأٍ مفهوم. ⭐ **وفي الوسط لا يسقط شيء** (‏قِيس بـ`bash -e`: استثناءُ قوائم `&&`) —
    # فلا يُنذَر به كي لا يُعلَّم القارئُ قاعدةً كاذبةً ثمّ يتجاهل الحارس.
    real = [(j, s) for j, s in body if s.strip() and not s.strip().startswith("#")]
    if real:
        j, s = real[-1]
        # ⛔ وما تلاه `||` لا يُسقط شيئاً (‏شرطٌ كاذبٌ ⇒ يُنفَّذ البديلُ ⇒ صفر) — إيجابيّةٌ
        #    كاذبةٌ ثانيةٌ من مستودعنا (`finetune-audit`), فتُستثنى بالقياس لا بالظنّ.
        if TEST_AND.match(s.strip()) and "||" not in s:
            risky.append((name, j + 1, "شرطٌ أخير",
                          "`[ … ] && …` آخرَ الكتلة ⇒ شرطٌ كاذبٌ يُسقط الخطوةَ (قِيس)"))
    return risky


SELFTEST = [
    ("سليمٌ (مُغلِقٌ على الأساس)", """
jobs:
  a:
    steps:
      - run: |
          python3 - <<'PY'
          print(1)
          PY
          echo done
""", 0),
    ("مُغلِقٌ أعمقُ من الأساس داخلَ قوسَين", """
jobs:
  a:
    steps:
      - run: |
          (
            python3 - <<'PY'
            print(1)
            PY
          ) > out.txt
""", 1),
    ("لا مُغلِقَ البتّة", """
jobs:
  a:
    steps:
      - run: |
          python3 - <<'PY'
          print(1)
""", 1),
    ("إيجابيّةٌ كاذبةٌ حقيقيّةٌ من مستودعنا (نصٌّ لا heredoc)", """
jobs:
  a:
    steps:
      - run: |
          printf 'list<<EOF\\n%s\\nEOF\\n' "$LIST" >> "$GITHUB_OUTPUT"
""", 0),
    # ---- 🪤 الفخّان المقيسان 2026-09-14 ----
    ("⛔ أنبوبٌ بلا pipefail يكتم فشلَ أوّله", """
jobs:
  a:
    steps:
      - run: |
          python tool.py --x | tee work/out.md
""", 1),
    ("✅ وأنبوبٌ في كتلةٍ فيها pipefail سليم", """
jobs:
  a:
    steps:
      - run: |
          set -o pipefail
          python tool.py --x | tee work/out.md
""", 0),
    ("✅ و`cmd || echo` ليس أنبوباً أصلاً (‏خلطُ الرسم — من `finetune-audit`)", """
jobs:
  a:
    steps:
      - run: |
          python tools/finetune/r2_put.py a b || echo "لا مخرَج"
""", 0),
    ("⛔ وأنبوبٌ معطوفٌ عليه `||` **بلا** pipefail — و`||` لا يشتعل أصلاً (‏مقيس)", """
jobs:
  a:
    steps:
      - run: |
          python tool.py | tee out.md || echo "⚠️ سقطت"
""", 1),
    ("✅ و`||` **مع** pipefail علاجٌ حقيقيّ (‏الشكلُ المقيسُ في `gate-anatomy`)", """
jobs:
  a:
    steps:
      - run: |
          set -o pipefail
          python tool.py | tee out.md || { echo "⚠️ سقطت" | tee -a out.md; }
""", 0),
    ("⛔ `[ … ] && …` آخرَ الكتلة يُسقط الخطوةَ بشرطٍ كاذب", """
jobs:
  a:
    steps:
      - run: |
          echo قبلُ
          [ -f out.md ] && python r2_put.py out.md
""", 1),
    ("✅ والشرطُ نفسُه في الوسط لا يُسقط شيئاً (‏قِيس) فلا يُنذَر به", """
jobs:
  a:
    steps:
      - run: |
          [ -z "$B" ] && B=4
          echo "$B"
""", 0),
    ("✅ وأنبوبٌ حالتُه تُقرأ من PIPESTATUS — وهو الصوابُ (‏من `plan-riwaya`)", """
jobs:
  a:
    steps:
      - run: |
          set +e
          python inject_riwaya.py $ARGS | tee /tmp/plan_log.txt
          rc=${PIPESTATUS[0]}
          set -e
""", 0),
    ("✅ وشرطٌ أخيرٌ يتلوه `||` لا يُسقط شيئاً (‏من `finetune-audit`)", """
jobs:
  a:
    steps:
      - run: |
          [ -f "/mnt/ft/a.json" ] && python tools/finetune/r2_put.py a b || echo "لا مخرَج"
""", 0),
]


def selftest():
    bad = 0
    for name, text, want in SELFTEST:
        got = len(scan_text(text, name))
        ok = got == want
        print(f"  {'✅' if ok else '⛔'} {name}: وُجد {got} · المتوقَّع {want}")
        bad += 0 if ok else 1
    print("✅ الحارسُ سليمٌ على حالاته" if not bad else f"⛔ الحارسُ نفسُه معطوبٌ في {bad} حالة")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="ملفّاتُ المسارات (‏أو نمطٌ)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    files = [f for p in a.paths for f in sorted(glob.glob(p))]
    if not files:
        # ⛔ ولا يُقرأ «لا خطر» من «لا ملفّات»: الصمتُ على لا شيءٍ ليس براءة.
        raise SystemExit("⛔ لا ملفَّ مسارٍ لُفحص — سمِّ المسارات")
    risky = []
    for f in files:
        risky += scan_text(open(f, encoding="utf-8").read(), f)
    print(f"فُحص {len(files)} ملفَّ مسار")
    for r in risky:
        print(f"  ⚠️ {r[0]}:{r[1]} · الوسم `{r[2]}` — {r[3]}")
    if risky:
        print(f"⛔ {len(risky)} موضعَ خطرٍ — العلاجُ بحسب الوسم: شفرةٌ في ملفٍّ بدل `heredoc` · و`set -o pipefail` للأنبوب · و`if` بدل شرطٍ أخير")
        return 1
    print("✅ لا مُغلِقَ heredoc أعمقُ من أساس كتلته ولا مفتوحاً بلا مُغلِق")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
