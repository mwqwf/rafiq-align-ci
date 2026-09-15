# -*- coding: utf-8 -*-
"""⤓ **الفرضيّاتُ تعود إلى المقعد ثمّ تُحكَم فيه مرّاتٍ بلا شوط** (‏D-537).

⛔⛔ **لِمَ وُجدت — بسببٍ مقيسٍ مراراً:** الدلوُ ومضيفُ الأثَر **لا يُقرآن من صندوق
المناوبة** (‏`api.github.com` و`raw` وحدَهما)، فكلُّ قاعدةِ حاكمٍ أردتُ قياسَها كلّفت
**شوطاً كاملاً** في العدّاء، ورقمُها يخالطه **ضجيجُ تفريغٍ جديد** (‏±1.5 نقطة · D-523)
فلا تُقارَن قاعدةٌ بأختها إلا بتحفّظ. والفرضيّاتُ **نصٌّ**: يطبعها `cli_time --dump-hyps`
مضغوطةً في **سجلّ الشوط** (وهو المسارُ المقروءُ الوحيد) ⇒ **فتُقرأ مرّةً وتُحكَم بها
كلُّ قاعدةٍ أبداً، وعلى التفريغِ نفسِه**.

⭐ **والحكمُ حاكمُ التسميع نفسُه** (`scorer.score` عبر `cli_time.accuse_judge`) لا مسطرةٌ
ثانيةٌ تتقادم صامتة. ⛔ **والمرآةُ للاتّجاه لا للرقم** — والرقمُ النهائيُّ من `emu-gate`.

    python tools/tasmi_bench/hyps_log.py --selftest
    python tools/tasmi_bench/hyps_log.py --from-log run.txt --out work/hyps_g4n.json
    python tools/tasmi_bench/hyps_log.py --hyps work/hyps_g4n.json --doors
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import cli_time as CT  # noqa: E402


def load(path):
    """‏json الفرضيّات كما كتبه `--from-log` (‏أو كتلةُ سجلٍّ خامٍ — يُقبل الاثنان)."""
    txt = open(path, encoding="utf-8", errors="replace").read()
    if CT.HYPS_BEGIN in txt:
        return CT.read_hyps(txt)
    return json.loads(txt)


def door_table(hyps, plan_ref=None):
    """🚪 **جدولُ أبوابِ الاتّهام على فرضيّاتٍ محفوظة** — سطرٌ لكلّ (ذراعٍ · باب).

    ⛔ **والمقايسةُ داخلَ الملفّ الواحد**: الأبوابُ **إعادةُ وسمٍ بعد المحاذاة** لا تفريغٌ
    جديد ⇒ فالفرقُ بينها **حكمٌ** لا مرجّح، ولا يخالطه ضجيجُ تشغيلة.
    """
    out = []
    judges = [(n, CT.accuse_judge(plan_ref, door=d or None)) for n, d in CT.DOORS]
    for arm in sorted(hyps):
        rows = {i: {"text": t} for i, t in hyps[arm].items()}
        base = None
        for name, (j, SCR) in judges:
            st = CT.accuse_stats(rows, j, SCR)
            base = base or st
            out.append({"arm": arm, "door": name, **st,
                        "d_accused": st["accused"] - base["accused"],
                        "moved_correct": st["correct"] != base["correct"],
                        "moved_collapse": st["collapsed"] != base["collapsed"]})
    return out


def print_table(rows):
    print("\n| الذراع | الباب | اتّهامٌ كاذب | لم تقلها | قلتَ غيرَها | «لم أتبيّن» | مؤكَّد | زوائد | انهيار |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        ref = r["ref"] or 1
        d = f" (‏{100.0 * r['d_accused'] / ref:+.1f})" if r["d_accused"] else ""
        warn = " ⛔⛔" if (r["moved_correct"] or r["moved_collapse"]) else ""
        print(f"| `{r['arm']}` | {r['door']}{warn} | {r['accused']}/{r['ref']} = "
              f"**{100.0 * r['accused'] / ref:.1f}٪**{d} | {r['missed']} | {r['subst']} | "
              f"{100.0 * r['uncertain'] / ref:.1f}٪ | "
              f"{100.0 * r['correct'] / ref:.1f}٪ | {r['adds']} | {r['collapsed']} |")
    if any(r["moved_correct"] or r["moved_collapse"] for r in rows):
        print("\n⛔⛔ **بابٌ حرّك المؤكَّدَ أو الانهيار** — والبابُ لا يفعل ذلك بالبناء "
              "(`UNCERTAIN` يُعرَض ولا يُحسب زلّةً · D-231) ⇒ فالمقيسُ **قاعدةٌ أخرى**.")


def detect_table(hyps, plan_path, arms=None):
    """⚖️ **الصرفُ: كم نقطةَ كشفٍ تُدفع لكلّ نقطةِ اتّهامٍ كاذبٍ تُكسب** — على فرضيّاتٍ محفوظة.

    ⛔⛔ **ولِمَ لا يُقرأ كسبُ البابِ وحدَه أبداً** (‏درسُ D-445 بثمنه): «ليس كلمةً» **ليس
    علامةَ «لم أسمع»** — بل هو **كيف يُبلّغ المحركُ عن خطإٍ حقيقيٍّ أيضاً** (الطالبُ إذا
    خالف النصَّ خرج تفريغُه لا-كلمةً كما يخرج في الضجيج) ⇒ **فكلُّ ما يكسبه البابُ من
    الاتّهام الكاذب قد يدفعه من الكشف**. والقاعدةُ رُدّت يومَ سُعّرت بـ**صرفٍ 3.94**
    (‏تكسب 4.55 وتدفع 18.0 · `shipped-D` · ن=479) ⇒ **والسؤالُ الوحيدُ الباقي: أيهبط
    الصرفُ دون الواحد على التفريغِ المقطَّع؟** — وهذا الجدولُ يجيبه، ⛔ **ولا يُقرأ حكماً
    بلا مادّةٍ محقونة**: المادّةُ الصحيحةُ لا كشفَ فيها فتُظهر الكسبَ وحدَه (‏نصفَ ميزان).

    ترجع صفوفاً لكلّ (ذراعٍ · باب) فيها الكشفُ والاتّهامُ والصرف.
    """
    import unheard_ab as UA
    import v2_gate as G
    plan_all = json.load(open(plan_path, encoding="utf-8"))
    plan_all = plan_all["items"] if isinstance(plan_all, dict) else plan_all
    by_id = {it["id"]: it for it in plan_all}
    lex = UA.lexicons()
    if not lex:
        raise SystemExit("⛔ لم يُبنَ معجمٌ واحد ⇒ **القاعدةُ لم تُقَس** (ولا يُقرأ هذا «لا أثر»)")
    out = []
    for arm in sorted(hyps) if arms is None else arms:
        rows = {i: {"text": t} for i, t in hyps[arm].items() if i in by_id}
        plan = [by_id[i] for i in sorted(rows)]
        if not plan:
            out.append({"arm": arm, "door": "—", "n": 0,
                        "note": "⛔ لا بندَ من الخطّة في هذه الذراع — لا يُقرأ الصفرُ نتيجةً"})
            continue
        # ⛔ **والأساسُ يُحكم مرّةً بلا معجمٍ البتّة** — وهو المشحونُ حرفاً بحرف، ومنه
        #    تُقاس كلُّ ذراعٍ (‏فلا يُقارَن بابٌ ببابٍ بلا أصلٍ في الجدول نفسِه).
        dA, faA, n, perA = UA.judge_with(plan, rows, None)
        out.append({"arm": arm, "door": "المشحون (لا باب)", "n": n, "det": dA, "fa": faA,
                    "gain": 0.0, "cost": 0.0, "d_lo": 0.0, "d_hi": 0.0, "ratio": None})
        for name, opts in UA.VARIANTS:
            dB, faB, _, perB = UA.judge_with(plan, rows, lex, **opts)
            det_pairs = [(perA[i][2], 1, perB[i][2], 1) for i in perA if i in perB]
            d_lo, d_hi, _ = G._boot_diff(det_pairs)
            gain, cost = (faA - faB) * 100, (dA - dB) * 100
            out.append({"arm": arm, "door": name, "n": n, "det": dB, "fa": faB,
                        "gain": gain, "cost": cost, "d_lo": d_lo * 100, "d_hi": d_hi * 100,
                        "ratio": None if gain <= 0 else cost / gain})
    return out


def print_detect(rows):
    print("\n| الذراع | الباب | ن | اتّهامٌ كاذب | الكسب | كشفٌ ضيّق | الثمن [95٪] | **الصرف** |")
    print("|---|---|---:|---:|---:|---:|---|---:|")
    for r in rows:
        if r.get("note"):
            print(f"| `{r['arm']}` | {r['note']} | 0 | — | — | — | — | — |")
            continue
        rt = "—" if r["ratio"] is None else f"**{r['ratio']:.2f}**"
        print(f"| `{r['arm']}` | {r['door']} | {r['n']} | {r['fa'] * 100:.2f}٪ | {-r['gain']:+.2f} | "
              f"{r['det'] * 100:.1f}٪ | {-r['cost']:+.1f} [{r['d_lo']:+.1f} .. {r['d_hi']:+.1f}] | {rt} |")
    print("\n⭐ **الصرفُ** = نقاطُ كشفٍ تُدفع لكلّ نقطةِ اتّهامٍ كاذبٍ تُكسب ⇒ **فوق الواحد يُردّ**."
          "\n⛔ ولا يُقرأ هذا الجدولُ إلا على **مادّةٍ محقونة**: الصحيحةُ لا كشفَ فيها.")


def _selftest():
    fails = []

    def ok(c, m):
        if not c:
            fails.append(m)

    blob = CT.hyps_blob({"greedy": {"x": {"text": "ا ب"}}}, {"arms": ["greedy", "greedy"]})
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "log.txt")
        open(p, "w", encoding="utf-8").write("سطرٌ\n" + blob + "\nسطرٌ\n")
        got = load(p)
        ok(got["hyps"]["greedy"]["x"] == "ا ب", "⤓ تُقرأ الكتلةُ من ملفّ سجلّ")
        p2 = os.path.join(d, "h.json")
        json.dump(got, open(p2, "w", encoding="utf-8"), ensure_ascii=False)
        ok(load(p2) == got, "⤓ ويُقرأ الـjson نفسُه بلا عَلَم")
    # ⛔ والأبوابُ تُقرأ من مصدرٍ واحدٍ مع `cli_time` فلا تتفارق مسطرتان لقاعدةٍ واحدة
    ok(CT.DOORS[0][1] == {}, "🚪 أوّلُ بابٍ هو خطُّ الأساس")

    # ⚖️⛔⛔ **وضابطان سالبان لمسطرة الصرف** — وهما سببُ وجودها: ذراعٌ موضعُ الحقن فيها
    #     **لا-كلمةٌ** يجب أن يُظهر **ثمناً** (‏البابُ يكتم الخطأ الحقيقيّ)، وذراعٌ موضعُه
    #     **كلمةٌ قرآنيّةٌ أخرى** يجب أن يُظهر **صفرَ ثمنٍ** (‏البابُ لا يمسّها بالبناء).
    #     ⛔ ومسطرةٌ تُظهر صفراً في الحالتَين **عمياءُ** وتُقرأ «القاعدةُ مجّانيّة».
    # ⛔⛔ **والتخطّي يُنطق لا يُسكت** (‏درسٌ دُفع ثمنُه في هذه الدقيقة بعينها): جرّبتُ نقضَ
    #     هذا الضابط في شجرةٍ مؤقّتةٍ **بلا نصّ المصحف** فمرّ **أخضرَ بصفرِ إخفاق** — لأنّ
    #     المعجمَ لم يُبنَ فسقط الشرطُ صامتاً. ⇒ **«لم يُقَس» تُكتب** فلا تُقرأ نجاحاً.
    _pl = os.path.join(HERE, "inject_plan_riwaya.json")
    _why = "" if os.path.isfile(_pl) else "‏لا خطّةَ حقنٍ في الشجرة"
    if not _why:
        import unheard_ab as _UA
        if not _UA.lexicons(("warsh",)).get("warsh"):
            _why = "‏لم يُبنَ معجمُ ورشٍ (نصُّ المصحف غائبٌ عن هذه الشجرة)"
    if _why:
        print(f"  ⏭️ **لم تُقَس** مسطرةُ الصرف: {_why} — وهذا «غيرُ منطبقٍ» لا «سليم»")
    else:
        _items = [it for it in json.load(open(_pl, encoding="utf-8"))["items"]
                  if it.get("riwaya") == "warsh"][:6]
        _mk = lambda sub: {it["id"]: " ".join(          # noqa: E731
            (lambda w, k: w[:k] + [sub] + w[k + 1:])(
                it["refText"].split(), min(it["wordIndex"], len(it["refText"].split()) - 1)))
            for it in _items}
        _rows = detect_table({"mangled": _mk("تسفسوا"), "clean": _mk("فرعون")}, _pl)
        _d = {(r["arm"], r["door"]): r for r in _rows}
        _base = "المشحون (لا باب)"
        _asis = _UA.VARIANTS[0][0]
        ok(_d[("mangled", _base)]["det"] > 0.9, "⚖️ الأساسُ يكشف الحقنَ في الذراعَين")
        ok(_d[("mangled", _asis)]["cost"] > 50,
           "⚖️⛔ بابٌ على لا-كلمةٍ **يكتم الكشفَ** ⇒ ثمنٌ ظاهرٌ في الجدول")
        ok(_d[("clean", _asis)]["cost"] == 0,
           "⚖️ وعلى كلمةٍ قرآنيّةٍ أخرى **صفرُ ثمنٍ** — فالبابُ لا يُعمي عن لحنٍ يُسمع كلمةً")
    print("🧪 ضوابطُ `hyps_log`: %d إخفاقاً" % len(fails))
    for m in fails:
        print("  ⛔", m)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-log", default="", help="ملفٌّ فيه سجلُّ الشوط (‏يُقتطع منه العَلَم)")
    ap.add_argument("--hyps", default="", help="‏json فرضيّاتٍ سابقٍ")
    ap.add_argument("--out", default="", help="اكتبْ الفرضيّاتِ json إلى هذا المسار")
    ap.add_argument("--doors", action="store_true", help="اطبعْ جدولَ أبواب الاتّهام")
    ap.add_argument("--detect-plan", default="",
                    help="خطّةُ حقنٍ (‏`inject_plan*.json`) ⇒ يُطبع **الصرفُ**: كشفٌ مقابل اتّهام")
    a = ap.parse_args()
    src = a.__dict__["from_log"] or a.hyps
    if not src:
        raise SystemExit("⛔ لا مصدرَ: `--from-log` أو `--hyps`")
    data = load(src)
    hyps = data.get("hyps", data)
    n = sum(len(v) for v in hyps.values())
    print(f"⤓ {len(hyps)} ذراعاً · {n} بنداً · ترويسة: {json.dumps(data.get('meta', {}), ensure_ascii=False)}")
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump(data, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"💾 {a.out}")
    if a.doors:
        print_table(door_table(hyps))
    if a.__dict__["detect_plan"]:
        print_detect(detect_table(hyps, a.__dict__["detect_plan"]))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    main()
