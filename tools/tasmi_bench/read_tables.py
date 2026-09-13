# -*- coding: utf-8 -*-
"""📏🛡️ **جدولا القراءة الرخيصة** — دقّةُ التتبّع بالرواية · وحارسُ «ذراعان متطابقتان».

⛔ **لِمَ صار ملفّاً بعد أن كان داخل المسار (‏2026-09-13):** كُتب الجدولان **شفرةً مضمَّنةً في
`gate-anatomy.yml`**، وذلك يخلق ثغرةً من جنس ما نحرسه:
- **لا يفحصها حارسُ المرآة** (‏يفحص `.py`/`.sh`/`.json` لا شفرةَ YAML) ⇒ اختلافُ منطقٍ بين
  الأصل والمرآة **لا يُرى**؛
- **ولا تُختبر** قبل الدفع إلّا باستخراجٍ يدويٍّ بـ`sed` (‏وقد فعلتُه ثلاث مرّاتٍ اليومَ —
  والفحصُ الذي لا يُؤتمَت لا يُعاد)؛
- ⭐ وقد صُدِّق أنّ هذه الثغرةَ ليست نظريّةً: جردُ الفرضيّات كان مضمَّناً كذلك **فأسقط صامتاً
  كلَّ سلسلةٍ غيرِ `cap`** حتى قُرئ باليد.

⇒ **المنطقُ هنا وله `--selftest`**، والمسارُ ينادي أمراً واحداً.

    python read_tables.py track     --arms "A B" --sets "g1 g4n" --dir work
    python read_tables.py identical --arms "A B" --dir work
    python read_tables.py --selftest        # ⛔ يُشغَّل قبل كلّ دفعٍ لهذا الملفّ
"""
import argparse
import glob
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
FOOT_DIFF = ("\n⚠️ **والفرقُ يُقرأ بمجاله لا بمقداره** — ومجالٌ يعبر الصفرَ «لا يُعتدّ به» "
             "لا «لا فرق»، ومجالٌ صفريُّ العرض **إعلانُ أنّ الذراعَين متطابقتان** (D-380).")
FOOT_SAME = ("\n⭐ **وهذا يُقرأ قبل أيّ فرق:** صفرٌ بمجالٍ صفريِّ العرض ليس «لا أثرَ للمفتاح» "
             "بل **«لم تقع التجربةُ»** (D-380) — والتمييزُ بينهما في النصّ لا في المجال.")


def colon(x):
    """‏`g3r-clean` ⇒ `g3r:clean` — و`g1`/`g4*` كما هي (‏`tag_of` لا تضع `:` فيها)."""
    return x if (x.startswith("g1") or x.startswith("g4")) else x.replace("-", ":", 1)


def hyps_of(d, st, arm):
    """فرضيّاتُ (مجموعةٍ · ذراع) من مجلدٍ — **بأيّ سلسلةٍ حُفظت** لا بـ`cap` وحدَها."""
    for pat in (f"hyps_emu_{st}_cap_{arm}.json", f"hyps_emu_{st}_*_{arm}.json",
                f"hyps_emu_{st}_{arm}.json"):
        for p in sorted(glob.glob(os.path.join(d, pat))):
            return (json.load(open(p, encoding="utf-8")) or {}).get("hyps", {}) or {}, p
    return {}, ""


def identical(arms, d, out=print):
    """🛡️ أمتطابقتان **حرفاً** أم لا — فمجالٌ صفريُّ العرض استنتاجٌ، والنصُّ شهادة."""
    sets = []
    for p in sorted(glob.glob(os.path.join(d, f"hyps_emu_*_{arms[0]}.json"))):
        st = os.path.basename(p)[len("hyps_emu_"):].split("_")[0]
        if st not in sets:
            sets.append(st)
    rows = []
    for st in sets:
        a, _ = hyps_of(d, st, arms[0])
        b, _ = hyps_of(d, st, arms[1])
        ids = sorted(set(a) & set(b))
        if not ids:
            continue
        same = sum(1 for i in ids if (a[i] or {}).get("text") == (b[i] or {}).get("text"))
        rows.append((st, len(ids), same))
    if not rows:
        return rows
    out("| المجموعة | بنودٌ مشتركة | **نصٌّ متطابقٌ حرفاً** | الحكم |")
    out("|---|---:|---:|---|")
    for st, n, same in rows:
        v = ("⛔⛔ **الذراعان نسختان** — المفتاحُ لم ينعقد" if same == n
             else ("⚠️ تطابقٌ جزئيّ" if same else "✅ فرقٌ حقيقيٌّ في النصّ"))
        out(f"| `{st}` | {n} | {same} | {v} |")
    out(FOOT_SAME)
    return rows


def track(arms, sets, d, out=print, G=None, SC=None):
    """📏 دقّةُ التتبّع **للذراعَين على البنود عينِها** — مضمومةً وبالرواية.

    🕌 **والتفصيلُ بالرواية لازمٌ لا زينة:** أكثرُ قراراتنا روائيّةٌ (D-417 · D-423)،
    **والمضمومةُ تُخفي روايةً تخسر وأخرى تكسب** (‏قِيس: مضمومةٌ ‎−10.26 وورشٌ وحدَه ‎−30.77).
    ⚠️ ومجالُ الرواية أوسعُ (عيّنتُها أصغر) فلا يُقرأ ضيقُ المضمومة عليها.
    """
    if G is None:
        sys.path.insert(0, HERE)
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
        import v2_gate as G                      # noqa: E402
    if SC is None:
        import score as SC                       # noqa: E402
    G.WORK = d
    pool = G.pool_items()
    out(f"| المجموعة | ن | `{arms[0]}` | `{arms[1]}` | الفرقُ الزوجيّ | مجال 95٪ |")
    out("|---|---:|---:|---:|---:|---:|")
    for raw in sets:
        st = colon(raw)
        hs = [G.load_hyps(st, a) for a in arms]
        if not all(hs):
            out(f"| `{raw}` | — | — | — | ⛔ فرضيّاتٌ ناقصةٌ لإحدى الذراعَين | — |")
            continue
        ids = sorted(set(hs[0]) & set(hs[1]))
        items = [it for it in pool if it["id"] in ids]
        if not items:
            # ⭐ والسببُ يُسمّى لا يُعمَّم: مجموعةُ الحقن مرجعُها خطّةُ الحقن وحكمُها في جدول
            #    البوّابة ⇒ «بلا مرجع» لها تُقرأ عطباً وهو ليس عطباً.
            why = ("⛔ **مجموعةُ حقنٍ: حكمُها في جدول البوّابة** (‏اتّهامٌ كاذبٌ وكشفٌ) لا في "
                   "دقّة التتبّع" if raw.startswith("g3") else "⛔ **بلا مرجعٍ في العيّنة والخطّة**")
            out(f"| `{raw}` | {len(ids)} | — | — | {why} | — |")
            continue
        res = [SC.run(items, h, "proposed") for h in hs]
        agg = [SC.aggregate(r) for r in res]
        by = {}
        for k, r in enumerate(res):
            for row in r:
                if row["ok"]:
                    by.setdefault(row["id"], {})[k] = (row["correct"], row["total"])
        pairs = [(v[0][0], v[0][1], v[1][0], v[1][1]) for v in by.values() if 0 in v and 1 in v]
        lo, hi, pup = G._boot_diff(pairs)
        d0 = (agg[1]["accuracy"] - agg[0]["accuracy"]) * 100
        out(f"| `{raw}` | {len(pairs)} | {agg[0]['accuracy']*100:.2f}٪ | "
            f"**{agg[1]['accuracy']*100:.2f}٪** | **{d0:+.2f}** | "
            f"[{lo*100:+.2f} .. {hi*100:+.2f}] · ارتفاعٌ {pup*100:.0f}٪ |")
        riw = {}
        for it in items:
            v = by.get(it["id"])
            if v and 0 in v and 1 in v:
                riw.setdefault(it.get("riwaya", "—"), []).append(
                    (v[0][0], v[0][1], v[1][0], v[1][1]))
        for r in sorted(riw):
            ps = riw[r]
            ca, ta = sum(x[0] for x in ps), sum(x[1] for x in ps) or 1
            cb, tb = sum(x[2] for x in ps), sum(x[3] for x in ps) or 1
            l2, h2, p2 = G._boot_diff(ps)
            out(f"| ↳ `{raw}` · {r} | {len(ps)} | {ca/ta*100:.2f}٪ | **{cb/tb*100:.2f}٪** | "
                f"**{(cb/tb - ca/ta)*100:+.2f}** | [{l2*100:+.2f} .. {h2*100:+.2f}] · "
                f"ارتفاعٌ {p2*100:.0f}٪ |")
    out(FOOT_DIFF)


def selftest():
    """⛔ حارسٌ يُختبر قبل أن يُستعمل — وفيه الحالاتُ التي وقعت فعلاً اليومَ."""
    import tempfile
    d = tempfile.mkdtemp()

    def w(name, hyps):
        json.dump({"meta": {}, "hyps": hyps},
                  open(os.path.join(d, name), "w", encoding="utf-8"), ensure_ascii=False)

    # ① حارسُ التطابق: تامٌّ · جزئيٌّ (وهو ما وقع في D-385: 59 من 60) · ومختلفٌ تماماً
    w("hyps_emu_g4n_cap_armA.json", {"i1": {"text": "أ ب"}, "i2": {"text": "ج د"}})
    w("hyps_emu_g4n_gateonly_armB.json", {"i1": {"text": "أ ب"}, "i2": {"text": "ج د"}})
    w("hyps_emu_g1_cap_armA.json", {"i1": {"text": "أ ب"}, "i2": {"text": "ج د"}})
    w("hyps_emu_g1_cap_armB.json", {"i1": {"text": "أ ب"}, "i2": {"text": "س"}})
    w("hyps_emu_g4_cap_armA.json", {"i1": {"text": "أ ب"}})
    w("hyps_emu_g4_cap_armB.json", {"i1": {"text": "ص ض"}})
    rows = dict((r[0], (r[1], r[2])) for r in identical(["armA", "armB"], d, out=lambda *_: None))
    assert rows["g4n"] == (2, 2), rows          # نسختان
    assert rows["g1"] == (2, 1), rows           # جزئيّ
    assert rows["g4"] == (1, 0), rows           # مختلفٌ تماماً
    # ⭐ **وأهمُّ حالةٍ:** ذراعٌ حُفظت بسلسلةٍ غيرِ `cap` تُقرأ ولا تُهمَل (‏`g4n` أعلاه
    #    ذراعُها الثانية `gateonly`) — وهي العطبُ الذي كتم رقمَ D-384 يوماً كاملاً.

    # ② جدولُ التتبّع بمرجعٍ مصطنعٍ: مضمومةٌ + تفصيلٌ بالرواية يُظهر ما تُخفيه المضمومة
    class FakeG:
        WORK = d
        @staticmethod
        def pool_items():
            return [{"id": f"w{i}", "riwaya": "warsh", "refText": "أ ب ج", "wordCount": 3}
                    for i in range(3)] + \
                   [{"id": f"h{i}", "riwaya": "hafs", "refText": "أ ب ج", "wordCount": 3}
                    for i in range(3)]
        @staticmethod
        def load_hyps(st, arm):
            h, _ = hyps_of(d, "g1" if st.startswith("g1") else st, arm)
            return h
        @staticmethod
        def _boot_diff(pairs):
            return (0.0, 0.0, 0.0)
    class FakeSC:
        @staticmethod
        def run(items, h, _mode):
            out = []
            for it in items:
                t = (h.get(it["id"]) or {}).get("text")
                if t is None:
                    continue
                ok = len(t.split())
                out.append({"id": it["id"], "ok": True, "correct": ok, "total": 3,
                            "words": [], "additions": []})
            return out
        @staticmethod
        def aggregate(res):
            c = sum(r["correct"] for r in res); t = sum(r["total"] for r in res) or 1
            return {"accuracy": c / t, "scored": len(res)}
    w("hyps_emu_g1_cap_full.json", {**{f"w{i}": {"text": "أ ب ج"} for i in range(3)},
                                    **{f"h{i}": {"text": "أ ب ج"} for i in range(3)}})
    w("hyps_emu_g1_cap_warshbad.json", {**{f"w{i}": {"text": "أ ب"} for i in range(3)},
                                        **{f"h{i}": {"text": "أ ب ج"} for i in range(3)}})
    lines = []
    track(["full", "warshbad"], ["g1"], d, out=lines.append, G=FakeG, SC=FakeSC)
    body = "\n".join(lines)
    assert "| `g1` | 6 |" in body, body
    assert "↳ `g1` · warsh" in body and "↳ `g1` · hafs" in body, body
    # ⛔ **ويُنتقى الصفُّ بصورته لا بذكر الاسم**: اسمُ الذراع `warshbad` يقع في الترويسة،
    #    فبحثٌ عن «warsh» يُصيبها ويُفلت الصفَّ (وقع في أوّل تشغيلٍ لهذا الاختبار).
    wr = [l for l in lines if l.startswith("| ↳") and "· warsh " in l][0]
    hf = [l for l in lines if l.startswith("| ↳") and "· hafs " in l][0]
    assert "-33.33" in wr, wr                   # ورشٌ خسر ثلثاً
    assert "+0.00" in hf, hf                    # وحفصٌ لم يتغيّر ⇒ الإخفاءُ مقيس
    print("✅ اختبارٌ ذاتيّ: ثلاثُ حالاتِ تطابقٍ (تامٌّ · جزئيٌّ · مختلف) · وقراءةُ ذراعٍ "
          "بسلسلةٍ غيرِ `cap` · وتفصيلٌ بالرواية يُظهر ما تُخفيه المضمومة")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=("track", "identical"))
    ap.add_argument("--arms", default="", help="اسمَا الذراعَين بمسافة")
    ap.add_argument("--sets", default="", help="المجموعاتُ بمسافة (‏بأسمائها كما في الملفّات)")
    ap.add_argument("--dir", default=os.path.join(HERE, "work"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    arms = a.arms.split()
    if not a.cmd or len(arms) != 2:
        raise SystemExit("⛔ يلزم أمرٌ (`track`/`identical`) و`--arms` باسمَين — لا أكثرَ ولا أقلّ")
    if a.cmd == "identical":
        identical(arms, a.dir)
        return 0
    track(arms, a.sets.split(), a.dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
