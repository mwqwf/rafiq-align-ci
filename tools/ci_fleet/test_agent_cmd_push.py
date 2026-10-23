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


    # ⑤–⑦ (2026-10-23) سباقُ الدفع: أجوبةُ أوامر tool ضاعت (20 من 488 في يوم) لأنّ الجلبَ والدمجَ في عدّاءٍ سطحيٍّ يستغرقان دقائق
    #      فيخسر الدفعُ الثاني، ثمّ لا يرى خطوةُ آخر الشوط فرقاً مرحلاً. العلاجُ: رفعٌ بالواجهة أوّلاً ثمّ حلقةُ جلبٍ ودمج.
    import base64
    import json as _json
    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td)
        bare, work, other = base / "origin.git", base / "work", base / "other"
        git("init", "-q", "--bare", "-b", "main", str(bare), cwd=base)
        for d in (work, other):
            git("clone", "-q", str(bare), str(d), cwd=base)
            git("config", "user.email", "t@t", cwd=d)
            git("config", "user.name", "t", cwd=d)
            git("checkout", "-q", "-B", "main", cwd=d)
        (work / "ops" / "out").mkdir(parents=True)
        (work / "ops" / "out" / ".keep").write_text("", encoding="utf-8")
        git("add", "-A", cwd=work)
        git("commit", "-qm", "init", cwd=work)
        git("push", "-q", "origin", "HEAD:main", cwd=work)
        git("pull", "-q", "origin", "main", cwd=other)

        m = load(work)

        # ⑤ وحدةُ الواجهة: 404 على المحتوى (لا sha) ثمّ 409 ثمّ نجاح — والمحتوى base64 لما في الملف، والفرع main.
        (work / "ops" / "out" / "api1.txt").write_text("# rc=0\nجوابٌ بالواجهة\n", encoding="utf-8")
        calls = []
        seq = {"put": 0}

        def fake_run(cmd, **kw):
            calls.append((cmd, kw))
            if cmd[:2] == ["gh", "api"] and "-X" not in cmd:
                return 1, "[stderr]\nHTTP 404"
            seq["put"] += 1
            return (1, "HTTP 409") if seq["put"] == 1 else (0, "{}")

        real_run = m.run
        m.run = fake_run
        got = m._api_put_files(["ops/out/api1.txt"], repo="o/r", sleep=lambda _s: None)
        m.run = real_run
        puts = [c for c in calls if "-X" in c[0]]
        pl = _json.loads(puts[-1][1]["input"]) if puts else {}
        good = (got is True and len(puts) == 2 and pl.get("branch") == "main" and "sha" not in pl
                and base64.b64decode(pl.get("content", "")).decode("utf-8") == "# rc=0\nجوابٌ بالواجهة\n"
                and "contents/ops/out/api1.txt" in puts[-1][0][4])
        ok &= good
        print(f"{'✅' if good else '🔴'} الواجهة: تعيد المحاولة بعد 409 وترفع المحتوى كاملاً إلى main")

        # ⑤ب ملفٌّ موجودٌ على الخادم ⇒ يُرسل sha الحالي (وإلا رفضت الواجهةُ بـ422).
        calls.clear()
        seq["put"] = 0

        def fake_run2(cmd, **kw):
            calls.append((cmd, kw))
            if "-X" not in cmd:
                return 0, "abc123\n"
            return 0, "{}"
        m.run = fake_run2
        got = m._api_put_files(["ops/out/api1.txt"], repo="o/r", sleep=lambda _s: None)
        m.run = real_run
        pl = _json.loads([c for c in calls if "-X" in c[0]][-1][1]["input"])
        good = got is True and pl.get("sha") == "abc123"
        ok &= good
        print(f"{'✅' if good else '🔴'} الواجهة: ملفٌّ قائمٌ ⇒ يُرسَل sha الحالي")

        # ⑤ج لا مستودعَ في البيئة (أو لا gh) ⇒ False بلا رمي، فيعود المنادي إلى الجلب والدمج.
        old_env = __import__("os").environ.pop("GITHUB_REPOSITORY", None)
        good = m._api_put_files(["ops/out/api1.txt"]) is False
        if old_env is not None:
            __import__("os").environ["GITHUB_REPOSITORY"] = old_env
        ok &= good
        print(f"{'✅' if good else '🔴'} الواجهة: بلا GITHUB_REPOSITORY تُرجع False ولا ترمي")

        # ⑥ خسارةُ السباق + الواجهةُ تنجح ⇒ لا جلبَ ولا دمجَ (‏لا إيداعَ دمجٍ في الشجرة) والمنادي يطلبها بالمسار الصحيح.
        (other / "ops" / "out" / "x.txt").write_text("x", encoding="utf-8")
        git("add", "ops/out/x.txt", cwd=other)
        git("commit", "-qm", "غيري سبق", cwd=other)
        git("push", "-q", "origin", "HEAD:main", cwd=other)                # الأصلُ تقدّم ⇒ دفعُ work مرفوض
        asked = []
        m._api_put_files = lambda paths, **kw: asked.append(list(paths)) or True
        (work / "ops" / "out" / "tool1.txt").write_text("# rc=0\nأداة\n", encoding="utf-8")
        m._push_answer("tool1", api_paths=["ops/out/tool1.txt"])
        merges = git("log", "--merges", "--oneline", cwd=work).stdout.strip()
        good = asked == [["ops/out/tool1.txt"]] and merges == ""
        ok &= good
        print(f"{'✅' if good else '🔴'} خسر الدفعُ السباقَ ⇒ تُستعمل الواجهةُ فوراً بلا دمجٍ بطيء")

        # ⑦ الواجهةُ تفشل ⇒ الجلبُ والدمجُ يوصلان الجواب (السلوكُ القديمُ باقٍ كاحتياط).
        m._api_put_files = lambda paths, **kw: False
        (work / "ops" / "out" / "tool2.txt").write_text("# rc=0\nثانية\n", encoding="utf-8")
        m._push_answer("tool2", api_paths=["ops/out/tool2.txt"])
        landed = git("show", "origin/main:ops/out/tool2.txt", cwd=work).stdout
        theirs = git("show", "origin/main:ops/out/x.txt", cwd=work).stdout
        good = "ثانية" in landed and theirs == "x"
        ok &= good
        print(f"{'✅' if good else '🔴'} تعذّرت الواجهة ⇒ الدمجُ يوصل الجواب ولا يمحو عملَ غيره")

    print()
    print("⇒ فائدتُه بلغة العمل: شوطٌ يبلغ سقفَ الوقت لم يعد يمحو ما أُنجز —"
          " تُقرأ أجوبةُ ما تمّ، ويُعاد ما لم يتمّ وحدَه.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
