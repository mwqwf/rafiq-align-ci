#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر التنفيذَ المتوازي في `agent_cmd.main` على نسخةٍ سطحيّةٍ (fetch-depth: 1).

    python tools/ci_fleet/test_agent_cmd_parallel.py

يحرس ما اشترطه التسريع (2026-10-22):
  ١) لا يضيع أمرٌ ولا جواب: كلُّ أمرٍ → ملفُّ جوابٍ في origin/main، وملفُّه في done/، ولا `.attempts` باقٍ.
  ٢) المعالجاتُ تعمل معاً فعلاً (زمنُ الكلّ أقلُّ من مجموع الأزمنة).
  ٣) الدمجُ عند رفض الدفع يعمل على نسخةٍ سطحيّة (main تقدّم أثناء الشوط) ويُبقي جوابَنا.
  ٤) أمرٌ بلغ المحاولاتِ يُنحّى بجواب rc=98 ولا يُنفَّذ.
⚖️ مستودعٌ مؤقّتٌ ببعيدٍ مؤقّت — لا يمسّ الشبكةَ ولا الدلوَ ولا gh.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

SRC = pathlib.Path(__file__).resolve().with_name("agent_cmd.py")


def git(*a, cwd):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
                          cwd=cwd, capture_output=True, text=True)


def load(root: pathlib.Path):
    spec = importlib.util.spec_from_file_location("ac_par_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ROOT = root
    m.CMD_DIR = root / "ops" / "commands"
    m.OUT_DIR = root / "ops" / "out"
    m.DONE_DIR = m.CMD_DIR / "done"
    return m


def main() -> int:
    ok = True

    def check(cond, msg):
        nonlocal ok
        ok &= bool(cond)
        print(f"{'✅' if cond else '🔴'} {msg}")

    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td)
        bare, seed, work = base / "o.git", base / "seed", base / "work"
        git("init", "-q", "--bare", "-b", "main", str(bare), cwd=base)
        git("clone", "-q", str(bare), str(seed), cwd=base)
        git("checkout", "-q", "-B", "main", cwd=seed)
        (seed / "ops" / "commands").mkdir(parents=True)
        (seed / "ops" / "out").mkdir(parents=True)
        (seed / "ops" / "out" / ".keep").write_text("", encoding="utf-8")
        for i in range(7):
            (seed / "ops" / "commands" / f"c{i}.json").write_text(
                '{"action":"slow"}', encoding="utf-8")
        # أمرٌ بلغ حدَّ المحاولات
        (seed / "ops" / "commands" / "c9_stuck.json").write_text('{"action":"slow"}', encoding="utf-8")
        (seed / "ops" / "out" / "c9_stuck.attempts").write_text("3", encoding="utf-8")
        git("add", "-A", cwd=seed)
        git("commit", "-qm", "init", cwd=seed)
        git("push", "-q", "origin", "HEAD:main", cwd=seed)
        # نسخةٌ سطحيّة كما يفعل actions/checkout بـ fetch-depth: 1
        r = git("clone", "-q", "--depth", "1", "--branch", "main", f"file://{bare}", str(work), cwd=base)
        check(r.returncode == 0 and (work / ".git" / "shallow").exists(), "النسخةُ سطحيّة فعلاً")
        git("config", "user.name", "t", cwd=work)
        git("config", "user.email", "t@t", cwd=work)
        # main يتقدّم من خارجنا بعد الـcheckout (يُجبر الدمجَ على نسخةٍ سطحية)
        for i in range(4):
            (seed / f"other{i}.txt").write_text("x", encoding="utf-8")
            git("add", "-A", cwd=seed)
            git("commit", "-qm", f"other{i}", cwd=seed)
        git("push", "-q", "origin", "HEAD:main", cwd=seed)

        m = load(work)
        ran = []

        def slow(c):
            time.sleep(1.0)
            ran.append(c["_name"])
            return 0, "تمّ " + c["_name"]
        m.HANDLERS = {"slow": slow}
        m.POOL = 4

        t0 = time.time()
        m.main()
        dt = time.time() - t0

        outs = git("ls-tree", "-r", "--name-only", "origin/main", "ops/out", cwd=work)
        git("fetch", "-q", "origin", "main", cwd=work)
        tree = git("ls-tree", "-r", "--name-only", "FETCH_HEAD", cwd=work).stdout.split("\n")
        for i in range(7):
            check(f"ops/out/c{i}.txt" in tree, f"جوابُ c{i} وصل إلى origin/main")
            check(f"ops/commands/done/c{i}.json" in tree and f"ops/commands/c{i}.json" not in tree,
                  f"c{i} نُقل إلى done/")
        check(not any(t.endswith(".attempts") and "c9" not in t for t in tree), "لا .attempts لأمرٍ منجز")
        stuck = git("show", "FETCH_HEAD:ops/out/c9_stuck.txt", cwd=work).stdout
        check("# rc=98" in stuck and "c9_stuck" not in ran, "الأمرُ الذي بلغ المحاولات نُحّي بـrc=98 ولم يُنفَّذ")
        check("other3.txt" in tree, "دمجُ تقدّم main على النسخة السطحية سليم")
        check(sorted(ran) == [f"c{i}" for i in range(7)], "نُفّذت الأوامرُ السبعةُ كلُّها مرّةً واحدة")
        print(f"زمنُ التنفيذ {dt:.1f}ث (تسلسلاً ≥ 7ث)")
        check(dt < 6.5, "التنفيذُ متوازٍ فعلاً")
        st = git("status", "--porcelain", cwd=work).stdout.strip()
        check(not st.replace("?? ops/.tmp", ""), f"الشجرةُ نظيفة بعد الشوط ({st!r})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
