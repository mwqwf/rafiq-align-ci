#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر `agent_cmd._push_answer` — دفعُ جوابِ كلّ أمرٍ فور تنفيذه.

    python tools/ci_fleet/test_agent_cmd_push.py

⛔ **لماذا كُتب (2026-09-20):** كان دفعُ الأجوبة خطوةً أخيرةً وحدَها في
`agent_cmd.yml`، فإذا بلغ الشوطُ `timeout-minutes` أُلغي **قبلها** ⇒ **ضاعت
أجوبةُ الأوامر كلِّها** ولو نُفّذت فعلاً وكتبت في الدلو. وقع على الشوط
35528235170: ترقيتان نُفّذتا ولا أثرَ لجوابهما، فلم يُعرف أتمّتا أم لا.

⚖️ يعمل في مستودعٍ مؤقَّتٍ ببعيدٍ مؤقَّت — لا يمسّ المستودعَ الحقيقيّ ولا الدلو.
⭐ **وهذا الاختبارُ التقط عطباً فعلاً قبل الاستعمال**: `git add a b` يسقط كلُّه
إن غاب أحدُ المسارَين فلا يُدفع شيء — وهي حالةٌ تقع حقّاً حين يخلو
`ops/commands` بعد نقل آخر أمرٍ إلى `done/`.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

SRC = pathlib.Path(__file__).resolve().with_name("agent_cmd.py")


def git(*a, cwd, **kw):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True,
                          text=True, **kw)


def load(root: pathlib.Path):
    spec = importlib.util.spec_from_file_location("ac_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    m.ROOT = root
    return m


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td)
        bare, work = base / "origin.git", base / "work"
        git("init", "-q", "--bare", "-b", "main", str(bare), cwd=base)
        git("clone", "-q", str(bare), str(work), cwd=base)
        git("config", "user.email", "t@t", cwd=work)
        git("config", "user.name", "t", cwd=work)
        git("checkout", "-q", "-B", "main", cwd=work)
        (work / "ops" / "out").mkdir(parents=True)
        (work / "ops" / "out" / ".keep").write_text("", encoding="utf-8")
        git("add", "-A", cwd=work)
        git("commit", "-qm", "init", cwd=work)
        git("push", "-q", "origin", "HEAD:main", cwd=work)

        m = load(work)

        # ① لا جديدَ ⇒ لا إيداع.
        before = git("rev-parse", "HEAD", cwd=work).stdout.strip()
        m._push_answer("nothing")
        after = git("rev-parse", "HEAD", cwd=work).stdout.strip()
        good = before == after
        ok &= good
        print(f"{'✅' if good else '🔴'} لا جديدَ يُدفع ⇒ لا إيداعَ فارغ")

        # ② جوابٌ جديدٌ و`ops/commands` **غائبٌ تماماً** — الحالةُ التي كسرت الأصل.
        (work / "ops" / "out" / "demo.txt").write_text("# rc=0\nجواب\n",
                                                       encoding="utf-8")
        m._push_answer("demo")
        got = git("show", "origin/main:ops/out/demo.txt", cwd=work).stdout
        good = "جواب" in got
        ok &= good
        print(f"{'✅' if good else '🔴'} جوابٌ يصل إلى origin/main ولو غاب "
              f"ops/commands (العطبُ الذي التقطه هذا الاختبار)")

        # ③ ثمّ يظهر `ops/commands` ⇒ يُدفع هو أيضاً.
        (work / "ops" / "commands" / "done").mkdir(parents=True)
        (work / "ops" / "commands" / "done" / "x.json").write_text(
            "{}", encoding="utf-8")
        (work / "ops" / "out" / "demo2.txt").write_text("# rc=0\nثانٍ\n",
                                                        encoding="utf-8")
        m._push_answer("demo2")
        got2 = git("show", "origin/main:ops/commands/done/x.json",
                   cwd=work).stdout
        good = got2.strip() == "{}"
        ok &= good
        print(f"{'✅' if good else '🔴'} نقلُ الأمر إلى done/ يُدفع مع جوابه")

        # ④ جوابٌ ثانٍ لا يمحو الأوّل — فالسقفُ يقطع ما لم يُنفَّذ لا ما نُفِّذ.
        still = git("show", "origin/main:ops/out/demo.txt", cwd=work).stdout
        good = "جواب" in still
        ok &= good
        print(f"{'✅' if good else '🔴'} الجوابُ الأوّلُ باقٍ بعد الثاني")

    print()
    print("⇒ فائدتُه بلغة العمل: شوطٌ يبلغ سقفَ الوقت لم يعد يمحو ما أُنجز —"
          " تُقرأ أجوبةُ ما تمّ، ويُعاد ما لم يتمّ وحدَه.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
