#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فرزٌ سريع لفهارس الدلو — **بلا صوتٍ ولا خادم**، لجولة المراقبة كل 20 دقيقة.

    python tools/index_qa/triage.py            # جدولٌ كامل، الأسوأ أولاً
    python tools/index_qa/triage.py --brief    # سطرٌ واحد للحصيلة
    python tools/index_qa/triage.py --json out.json

⛔ **ما هذه الأداة وما ليست:** هي **فرزٌ لا تدقيق**. تقرأ الميتاداتا وتعدّ
المداخل والنطاقات، فتفصل الفهرس الذي لا يستحق وقت الصوت أصلاً عمّا يستحقه.
**لا تُصدر «سليم»** — أقصى ما تقوله «مرشّحٌ للعيّنة». والحكم بالعطب لا يصدر
إلا من `run.py` بعيّنةٍ عمياء بتمريرين وشاهدٍ نصّي.

**لماذا الفرز بـMED لا بالتغطية** (درسٌ مقيسٌ ليلة 2026-09-02): `m_sayed_warsh`
تغطيته 94.7% — تبدو ممتازة — وMED عنده 73.3%، وهو الفهرس الذي أثبتت العيّنة
فيه **10.4% عطباً جسيماً**، وكل أعطابه في مداخل MED. فمن فرز بالتغطية شحن
أسوأ فهرسٍ في القائمة. والقياس المجمَّع حتى الآن:
**العطب الجسيم في HIGH صفرٌ من 41 · وفي MED 3 من 7.**
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run import fetch_index, list_indexes, structural   # noqa: E402  (مصدرٌ واحد للدوال)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# عتبتا الفرز — مطابقتان لحارس السائق (تغطية ≥90% · HIGH ≥50%) قصداً:
# حارسان مستقلان يقولان الشيء نفسه من طرفين خيرٌ من حارسٍ واحد.
MIN_COVERAGE = 0.90
MIN_HIGH     = 0.50

HERE = Path(__file__).parent


def _rows(name):
    """أسطرُ ملفِّ حالةٍ (مفتاح + عمودٌ ثانٍ) بلا تعليقات."""
    f = HERE / name
    out = {}
    if f.exists():
        for ln in f.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                parts = ln.split("	")
                out[parts[0].strip()] = (parts[1].strip() if len(parts) > 1 else "")
    return out


def _target_key(key):
    """مفتاحُ الإنتاج الذي يهدف إليه فهرسُ الاختبار: يسقط البصمةُ والبادئة."""
    k = key.replace("timings-staging/", "timings/")
    return re.sub(r"\.[0-9a-f]{8}\.jz$", ".jz", k)


def _target_state(key, sha):
    """⛔ **ما يمنع القبول يجب أن يظهر في الفرز لا في البوابة وحدها.**

    درسٌ بثمنه (2026-09-02): كان `husary_qalun.3e52af3d` يظهر «ينتظر حكم
    الصوت» وهدفُه **مجمَّدٌ ببصمةٍ أخرى** بُنيت عليها مدى الكلمات — فحتى
    «مقبول» لا يُرقّيه. والحاجزُ كان في بوابة github-bd وحدها، والبوابةُ
    تمنع الترقية **بعد** أن تُنفَق العيّنة. فمن وضع الحاجز في آخر السلسلة
    حمى الإنتاج وأهدر القياس (‏عيّنةُ 200 حدٍّ ≈ ساعتان).
    """
    tgt = _target_key(key)
    fr = _rows("frozen.txt")
    if tgt in fr and fr[tgt].split()[0] != (sha or ""):
        return ("⏭️ لا تُنفَق عيّنة",
                f"الهدف {tgt} مجمَّدٌ ببصمةٍ أخرى ({fr[tgt].split()[0][:8]}) — رفعُه قرارُ إنسان")
    hold = _rows("hold.txt")
    if tgt in hold:
        return ("⚠️ محجوز", f"محجوز: {hold[tgt][:70]} — القياس يفيد لرفع الحجز")
    return (None, "")

def triage_one(key):
    idx, _sha = fetch_index(key)
    fatal, warn, info = structural(idx, key, True)
    n = info["entries"] or 1
    b = info.get("bands", {})
    med, hi = b.get("MED", 0), b.get("HIGH", 0)
    cov, hir, medr = n / 6236, hi / n, med / n
    state, why_state = _target_state(key, _sha)
    if state and state.startswith("⏭️"):
        return {"key": key.replace("timings/", "").replace(".jz", ""),
                "entries": n, "coverage": cov, "med": med / n, "high": hi / n,
                "fatal": fatal, "warn": warn, "verdict": state, "why": why_state}
    reasons = []
    if cov < MIN_COVERAGE:
        reasons.append(f"تغطية {cov:.1%} < {MIN_COVERAGE:.0%}")
    if hir < MIN_HIGH:
        reasons.append(f"HIGH {hir:.1%} < {MIN_HIGH:.0%}")
    if fatal:
        reasons.append(f"بنيوي: {fatal[0][:60]}")
    if state:
        reasons.append(why_state)
    return {"key": key.replace("timings/", "").replace(".jz", ""),
            "entries": n, "coverage": cov, "med": medr, "high": hir,
            "fatal": fatal, "warn": warn,
            "verdict": "⛔ احجب" if reasons else "✅ مرشّح للعيّنة",
            "why": " · ".join(reasons)}

def main():
    ap = argparse.ArgumentParser(description="فرز فهارس الدلو بلا صوت")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--json", metavar="ملف")
    a = ap.parse_args()

    rows = []
    for r in list_indexes():
        try:
            rows.append(triage_one(r["key"]))
        except Exception as ex:
            rows.append({"key": r["key"], "verdict": "⚠️ تعذّر", "why": str(ex)[:80],
                         "med": -1, "coverage": 0, "high": 0, "entries": 0,
                         "fatal": [], "warn": []})
    rows.sort(key=lambda x: -x["med"])          # الأسوأ أولاً

    ok = [r for r in rows if r["verdict"].startswith("✅")]
    if not a.brief:
        print(f"{'MED%':>6} {'تغطية':>7} {'HIGH%':>6} {'مداخل':>6}  {'الحكم':<16} الفهرس")
        for r in rows:
            print(f"{r['med']:6.1%} {r['coverage']:7.1%} {r['high']:6.1%} {r['entries']:6d}  "
                  f"{r['verdict']:<16} {r['key']}"
                  + (f"   ← {r['why']}" if r["why"] else ""))
        print()
    print(f"الحصيلة: {len(rows)} فهرساً · مرشّحٌ للعيّنة {len(ok)} · محجوب {len(rows)-len(ok)}"
          + (f" · للعيّنة الآن: {', '.join(r['key'] for r in ok)}" if ok else ""))
    print("⚠️ فرزٌ لا تدقيق: «مرشّح» ليست «سليم» — الحكم بالعطب من run.py بعيّنةٍ بتمريرين.")

    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
