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
        print(f"⛔ {len(risky)} موضعَ خطرٍ — تُكتب سطورُ الشِّفرة في ملفٍّ بدل `heredoc` داخلَ كتلة")
        return 1
    print("✅ لا مُغلِقَ heredoc أعمقُ من أساس كتلته ولا مفتوحاً بلا مُغلِق")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
