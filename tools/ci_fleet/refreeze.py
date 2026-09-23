#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يُعيد تجميدَ فهرسٍ منشورٍ **على بصمته الحاليّة** — يسدّ باباً تركه رفعُ تجميدٍ بلا ترقية.

    python tools/ci_fleet/refreeze.py timings/douri/fateh_douri.jz 2e534d11 "سبب"

⛔ **العطبُ الذي وُلد منه (مقيسٌ 2026-09-23):** `promote.py --unfreeze` يكتب في
قائمة الدلو فوراً، فإن ردّ الحارسُ الترقيةَ التالية (تشخيصٌ متقادم) **بقي الهدفُ
بلا تجميد**. ثمّ جاء `promote.py --yes` المجدولُ في `keepalive.yml` فرقّى فوقه
**مرشّحاً أقدمَ مقبولَ الحكم** ⇒ رجع `fateh_douri` من 6235 إلى 6209 و`trabulsi`
من 6236 إلى 6214 بين جردَي 23:04Z و01:02Z.

⚖️ **يُشدّد ولا يُرخي:** لا يكتب في `timings/` بايتاً، ولا يُجمّد إلا إن طابقت
بصمةُ المنشور الحاليّ البادئةَ المعطاة — فلا يُجمَّد فهرسٌ لم يُتحقَّق منه.
"""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "index_qa"))
import promote as p                                                  # noqa: E402


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__); return 2
    target, want, reason = sys.argv[1:]
    cl, bucket = p.s3()
    frozen, _t, _e = p.load_frozen(cl, bucket)
    body = cl.get_object(Bucket=bucket, Key=target)["Body"].read()
    sha = hashlib.sha256(body).hexdigest()
    if not sha.startswith(want):
        print(f"⛔ بصمةُ المنشور {sha[:8]} لا تطابق {want} — لا تجميد"); return 1
    if frozen.get(target) == sha:
        print(f"✅ {target} مجمَّدٌ أصلاً على {sha[:8]}"); return 0
    line = p.freeze(cl, bucket, target, sha, "إعادةُ تجميد · " + reason)
    print(f"🧊 {line}"); return 0


if __name__ == "__main__":
    sys.exit(main())
