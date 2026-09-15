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


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    main()
