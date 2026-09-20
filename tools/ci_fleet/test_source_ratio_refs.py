#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يُثبت بالقياس أنّ **مرجعاً ناقصاً يرفع نسبةَ المصدر كذباً** في
`restore_loop.source_ratio` — فيقول «سليم» عن مبتور.

    python tools/ci_fleet/test_source_ratio_refs.py

⛔ **لماذا كُتب (2026-09-20):** `REFS` أربعةٌ، و**ثلاثةٌ منها فيها نقصٌ هي
نفسُها** مقيساً من `ops/out/state.json`: ‏`tblawi` ينقصه 9 مداخلَ و`harthi` 6
و`abdullahk` 28 (‏و`a_turki` وحدَه كامل). ومدّةُ سورةٍ في مرجعٍ ناقصٍ **أقصرُ
من الحقّ**، فالمتوقَّعُ يصغر والنسبةُ (actual/exp) ترتفع ⇒ **الحارسُ يصير
أسهلَ خداعاً في الاتّجاه الخطر**: يمرّر مبتوراً على أنّه سليم.

⚖️ وهذا اختبارٌ **قارئٌ محض**: لا شبكةَ ولا دلوَ ولا كتابة — يُبدَّل `head_len`
بدالّةٍ صناعيّةٍ معلومةِ الجواب، فيُقاس المنطقُ وحدَه.
⛔ **ولا يغيّر عتبةً ولا حارساً**: يصف الحالَ ويطبع الفرقَ، والقرارُ لمن يقرأ.
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci_fleet"))

# ⛔ `restore_loop` يستورد من `index_qa` (‏boto3 وغيره) وقد لا يتوفّر هنا،
#    والمقصودُ دالّةٌ واحدةٌ رياضيّةٌ محضة ⇒ تُقرأ من الملفّ وتُنفَّذ وحدَها.
#    وهذا **ليس نسخاً للمنطق**: النصُّ المُختبَرُ هو نصُّ الأداة حرفاً.
import ast

src = (ROOT / "tools" / "ci_fleet" / "restore_loop.py").read_text(encoding="utf-8")
tree = ast.parse(src)
fn = next(n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name == "source_ratio")
ns: dict = {"statistics": __import__("statistics")}
exec(compile(ast.Module([fn], []), "<source_ratio>", "exec"), ns)      # noqa: S102
source_ratio = ns["source_ratio"]

TARGET = 46
# مدّاتُ القارئ (م.ث) — عشرُ سورٍ تكفي للسبر (الدالّةُ تأخذ أطولَ ثلاثٍ).
D = {s: 100_000 + 10_000 * s for s in range(1, 11)}
TRUE_RATIO = 0.70          # المصدرُ مبتورٌ حقّاً: 70٪ من المتوقَّع


def make_ref(gap: float):
    """مرجعٌ نسبتُه نفسُها، إلا أنّ سورةَ الهدف فيه أقصرُ بمقدار `gap`."""
    rd = dict(D)
    rd[TARGET] = int(D[TARGET] * (1.0 - gap))
    return rd


def run_case(refs, bytes_per_sec=1000.0):
    ns["head_len"] = lambda url: _len(url, bytes_per_sec)
    idx = object()
    ns["surah_ends"] = lambda _i: D
    return source_ratio(idx, "http://x/", TARGET, refs)


def _len(url, bps):
    s = int(url.rsplit("/", 1)[-1].split(".")[0])
    dur = D[s] / 1000.0
    if s == TARGET:
        dur *= TRUE_RATIO                      # الملفُّ المبتور
    return int(dur * bps)


def main() -> int:
    D[TARGET] = 150_000                        # سورةُ الهدف داخلَ الجدول
    complete = [dict(D) for _ in range(4)]
    mixed = [dict(D)] + [make_ref(0.20) for _ in range(3)]   # الحالُ اليوم: 1 كامل و3 ناقصة

    r_ok = run_case(complete)
    r_bad = run_case(mixed)
    r_wide = run_case(complete[:3] + [make_ref(0.20) for _ in range(3)])

    print("■ نسبةُ المصدر الحقيقيّةُ المصنوعة: 0.70 (مبتورٌ قطعاً · العتبة 0.85)")
    print(f"  بأربعةِ مراجعَ **كاملة**            ⇒ {r_ok:.3f}  {'✅ مبتور' if r_ok < 0.85 else '🔴 سليمٌ كذباً'}")
    print(f"  بحالِ اليوم (1 كامل · 3 ناقصة 20٪) ⇒ {r_bad:.3f}  {'✅ مبتور' if r_bad < 0.85 else '🔴 سليمٌ كذباً'}")
    print(f"  بستّةٍ (3 كاملة · 3 ناقصة)          ⇒ {r_wide:.3f}  {'✅ مبتور' if r_wide < 0.85 else '🔴 سليمٌ كذباً'}")
    print()

    ok = True
    if abs(r_ok - TRUE_RATIO) > 1e-6:
        print(f"🔴 المراجعُ الكاملةُ لم تُعِد الحقَّ: {r_ok} ≠ {TRUE_RATIO}")
        ok = False
    else:
        print("✅ المراجعُ الكاملةُ تُعيد النسبةَ الحقيقيّةَ بالضبط.")
    if not (r_bad > r_ok):
        print("🔴 لم يظهر الانحيازُ المتوقَّع (مرجعٌ ناقصٌ يرفع النسبة).")
        ok = False
    else:
        print(f"✅ الانحيازُ ثابتٌ واتّجاهُه خطِر: +{r_bad - r_ok:.3f} نحو «سليم».")
    if not (r_ok <= r_wide <= r_bad):
        print("🔴 توسيعُ المراجع لم يسحب الوسيطَ نحو الحقّ.")
        ok = False
    else:
        print("✅ زيادةُ المراجع الكاملة تسحب الوسيطَ نحو الحقّ.")

    print()
    print("⇒ الخلاصة: العطبُ في **سلامة المراجع** لا في العتبة."
          " ⛔ ولا تُخفَّض عتبةٌ ولا يُعطَّل حارس —")
    print("  العلاجُ أن تكون `REFS` فهارسَ **كاملةَ المداخل** (6236/6236)،"
          " وأن يُعاد قياسُ كلّ")
    print("  ما حُكم عليه بـ«مبتورٌ عند الناشر» وهو قريبٌ من العتبة"
          " (‏nufais 0.82 مثالاً).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
