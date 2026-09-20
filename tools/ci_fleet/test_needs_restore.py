#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر `restore_loop.needs_restore` — مِصفاةَ اختيار العمل في حلقة الاسترجاع.

    python tools/ci_fleet/test_needs_restore.py

⛔ **لماذا كُتب (2026-09-20):** كانت `LOWCOV = 0.75` بينما ماسحُ التغطية يشتكي
عند 0.98 ⇒ **النطاقُ [0.75, 0.98) لا تلمسه حلقةٌ واحدة** — الماسحُ يراه ولا
يُصلحه، والحلقةُ تُصلح ولا تراه؛ وفيه معظمُ الـ667 سورةً الحاضرةَ الناقصة.
فالشرطُ وُسّع، **ولا يُوسَّع شرطٌ بلا اختبارٍ يُثبت أنّه وسّع ما قُصد ولم يمسّ
غيرَه** (CLAUDE.md بند 2).

⚖️ قارئٌ محض: بلا شبكةٍ ولا دلو، ويستورد نصَّ الأداة حرفاً لا نسخةً منه.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "tools" / "ci_fleet" / "restore_loop.py").read_text(encoding="utf-8")
tree = ast.parse(SRC)
fn = next(n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name == "needs_restore")


def load(lowcov: float, min_ayahs: int = 3):
    ns = {"LOWCOV": lowcov, "MIN_AYAHS": min_ayahs}
    exec(compile(ast.Module([fn], []), "<needs_restore>", "exec"), ns)   # noqa: S102
    return ns["needs_restore"]


def main() -> int:
    old, new = load(0.75), load(0.98)
    # (‏حاضرٌ، متوقَّع، وصفٌ، أيُنتظر بالقديم؟، أيُنتظر بالجديد؟)
    cases = [
        (0,  35, "سورةٌ غائبةٌ كلّيّاً (nufais س46)",            True,  True),
        (5,   8, "س102 عند سبعةِ قرّاء — 62٪",                   True,  True),
        (17, 25, "bader س84 — 68٪",                              True,  True),
        (70, 78, "س55 ينقصها 8 — 90٪ · **النطاقُ الأعمى**",      False, True),
        (92, 96, "س56 ينقصها 4 — 96٪ · **النطاقُ الأعمى**",      False, True),
        (77, 78, "ينقصها آيةٌ واحدة — دون حدّ MIN_AYAHS",        False, False),
        (76, 78, "ينقصها آيتان — دون حدّ MIN_AYAHS",             False, False),
        (78, 78, "سورةٌ تامّة",                                   False, False),
    ]
    ok = True
    print(f"{'حاضر/متوقَّع':>14} {'قديم 0.75':>10} {'جديد 0.98':>10}   الوصف")
    for have, exp, desc, want_old, want_new in cases:
        g_old, g_new = old(have, exp), new(have, exp)
        good = (g_old == want_old) and (g_new == want_new)
        ok &= good
        mark = "✅" if good else "🔴"
        print(f"{mark} {have:>5}/{exp:<6} {str(g_old):>10} {str(g_new):>10}   {desc}")

    # ⛔ الحدُّ الأدنى للآيات حارسُ إنفاقٍ — والتوسيعُ لا يجوز أن يمسّه.
    assert not new(77, 78), "MIN_AYAHS مُسّ — ونقصُ آيةٍ واحدةٍ صار يُنفق عليه عدّاء"
    # ⛔ ولا يُقبل ما هو تامّ، مهما وُسّعت المصفاة.
    assert not new(6236, 6236) and not new(78, 78)

    print()
    env = load(float(os.environ.get("RESTORE_LOWCOV", "0.98")))
    print(f"✅ RESTORE_LOWCOV يعمل مفتاحاً: القيمةُ النافذة الآن"
          f" {os.environ.get('RESTORE_LOWCOV', '0.98')}"
          f" ⇒ س55 عند 90٪ {'تُنتظر' if env(70, 78) else 'تُترك'}.")
    print("✅ MIN_AYAHS لم يُمَسّ: نقصُ آيةٍ أو آيتَين لا يُنفق عليه عدّاء.")
    print("⛔ ولا عتبةَ حارسٍ في هذا الملفّ: SOUND=0.85 و«الجسيم 5٪» خارجَ نطاقه.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
