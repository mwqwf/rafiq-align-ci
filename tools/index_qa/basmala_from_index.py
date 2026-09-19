#!/usr/bin/env python3
"""بسملةُ القارئ مقيسةً **من فهرسه نفسِه** — لا من سُلَّمٍ ثابت.

⛔⛔ **لماذا هذه الأداة، والقاعدةُ مكتوبةٌ في `CLAUDE.md` منذ مدّة:**
«بسملةُ كلّ قارئٍ تُقاس من فهرسه نفسِه (وسيطُ `startMs` للآية الأولى في جارات
السورة)، **لا من سُلَّمٍ ثابت**: سُلَّمُ `basmala.yml` سقفُه 3000م.ث وبسملةُ
`husary_douri` **10160م.ث** فيقول «لا بسملة» كذباً».
⇒ فالقاعدةُ كانت **وصيّةً بلا أداة**: مَن أرادها نفّذها بيدٍ أو استعمل السُّلَّمَ
الكاذب. ⭐ **والوصيّةُ لا تُنفَّذ؛ الأداةُ تُنفَّذ.** فهذه هي.

⛔ **ولماذا الوسيطُ لا المتوسّط:** سورةٌ واحدةٌ ابتُلعت بسملتُها (‏`startMs`
قريبٌ من الصفر) تجرّ المتوسّطَ إلى أسفلَ فتُنتج تخطّياً أقصرَ من الحقّ، فتُبتلع
بسملةُ السورة المسترجَعة — وهو العطبُ عينُه الذي نداوي.

⛔ **وتُستثنى الفاتحةُ (1) وبراءةُ (9):** الأولى البسملةُ فيها آيةٌ معدودة،
والثانية لا بسملةَ لها أصلاً. فإدخالُهما يُفسد الوسيط.

الاستعمال:
    basmala_from_index.py <مفتاح الفهرس> [سورةٌ مستهدَفة ...]

وإن ذُكرت سورٌ مستهدَفة قِيس لكلٍّ منها وسيطُ **جاراتها القريبة** أيضاً، لأنّ
بعضَ القرّاء يغيّر نفَسه بين أجزاء المصحف.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import fetch_index  # noqa: E402

SKIP = {1, 9}          # الفاتحة وبراءة — انظر الترويسة
NEIGHBOURS = 8         # عددُ الجارات في كل اتجاه عند قياسِ سورةٍ بعينها


def first_ayah_starts(idx):
    """{سورة: startMs للآية الأولى} — من المداخل نفسِها لا من ترويسة."""
    out = {}
    for e in idx.get("entries", []):
        try:
            s, a = (int(x) for x in e["ayahId"].split(":"))
        except (KeyError, ValueError):
            continue
        if a == 1:
            out[s] = e.get("startMs")
    return {s: v for s, v in out.items() if isinstance(v, int) and s not in SKIP}


def report(starts, label, pool):
    vals = sorted(v for s, v in starts.items() if s in pool)
    if len(vals) < 3:
        print(f"  {label}: عيّنةٌ دون الثلاث ({len(vals)}) — لا يُحكم بها")
        return None
    med = int(statistics.median(vals))
    print(f"  {label}: وسيط {med}م.ث · عيّنة {len(vals)} · "
          f"مدى [{vals[0]}..{vals[-1]}] · ربيعان "
          f"[{vals[len(vals)//4]}..{vals[-1-len(vals)//4]}]")
    return med


def main():
    if len(sys.argv) < 2:
        raise SystemExit("الاستعمال: basmala_from_index.py <مفتاح> [سور...]")
    key = sys.argv[1]
    targets = [int(x) for x in sys.argv[2:]]
    idx, sha = fetch_index(key)
    print(f"الفهرس {key} (بصمة {sha[:12]}…) · مداخل {len(idx.get('entries', []))}")
    starts = first_ayah_starts(idx)
    if not starts:
        raise SystemExit("⛔ لا مطالعَ تُقرأ من هذا الفهرس")

    med_all = report(starts, "كلُّ السور", set(starts))
    out = {}
    for t in targets:
        pool = {s for s in starts
                if abs(s - t) <= NEIGHBOURS and s != t}
        med = report(starts, f"جاراتُ س{t} (±{NEIGHBOURS})", pool)
        out[t] = med if med is not None else med_all

    if targets:
        print("\n⇒ التخطّي المقترَح لكلّ سورة (‏يُمرَّر skip_ms):")
        for t in targets:
            v = out[t]
            print(f"   س{t}: skip_ms={v}" if v else f"   س{t}: ⛔ لا قياس")
        # ⛔ التخطّي صفراً يبتلع البسملة دائماً (الملفّ يبدأ بها) — فيُرفض صراحةً
        #    لا يُترك ليمرّ صامتاً.
        if any(not v for v in out.values()):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
