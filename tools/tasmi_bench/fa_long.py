# -*- coding: utf-8 -*-
"""⚖️ **الاتّهامُ الكاذبُ على التلاوة الطويلة** — وهي بعينُها موضعُ القرار (‏D-352).

شرطُ المالك زوجٌ: «ترتفعُ الدقّةُ ولا يرتفع الاتّهامُ الكاذب». وقد قِيس الاتّهامُ على **آيةٍ
مفردة** (‏`g3r` · 319 بنداً) — ومحلُّ الشحن المقترَحُ **الحكمُ النهائيُّ على تلاوةٍ طويلة**.
⛔ **فقياسُ موضعٍ لا يُغني عن موضعِ القرار.**

والطويلُ **مجموعاتُه صحيحةٌ بالبناء** (‏`g4*` تلاواتٌ سليمةٌ موصولة) ⇒ **كلُّ كلمةٍ يُحكم عليها
بـ`MISSED`/`SUBSTITUTED` اتّهامٌ كاذبٌ بالضرورة**، فلا حاجةَ إلى حقنٍ ولا إلى نطاق ‎±1: النسبةُ
هي الاتّهامُ نفسُه. ومعها **حارسُ الانهيار** (0.60) كما في المحرك: ما كبحه لا يُتَّهم فيه أحد.

    python tools/tasmi_bench/fa_long.py --sets g4 g4n --arms shipped base-ar
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorer  # noqa: E402
import judge_cfg_probe as J  # noqa: E402

CONF = {scorer.MISSED, scorer.SUBSTITUTED}
COLLAPSE = 0.60


def plan():
    """بنودُ الطويل **والمفرد** معاً: كلتاهما تلاوةٌ **صحيحةٌ بالبناء** فالاتّهامُ فيها كاذبٌ كلُّه."""
    out = {}
    for src in (os.path.join(HERE, "work", "long_plan.json"), os.path.join(HERE, "sample.json")):
        if not os.path.exists(src):
            continue
        d = json.load(open(src, encoding="utf-8"))
        for it in (d["items"] if isinstance(d, dict) else d):
            out[it["id"]] = it
    return out


def find(set_name, arm, roots):
    """⚠️ **ولاحقةُ الشوط تُقبل:** ملفّاتُ الأذرع تحمل لاحقةَ الشوط (`…_cap_shipped-B.json`)
    كي لا يدوس شوطٌ شوطاً، فالمطابقةُ بالبادئة لا بالاسم التامّ — وإلّا قيل «ناقصٌ» وهو حاضر."""
    pref = f"hyps_emu_{set_name}_cap_{arm}"
    hits = []
    for r in roots:
        r = r if os.path.isabs(r) else os.path.join(HERE, r)
        for dirpath, _dn, fn in os.walk(r):
            for f in fn:
                if f.endswith(".json") and (f[:-5] == pref or f[:-5].startswith(pref + "-")):
                    hits.append(os.path.join(dirpath, f))
    if len(hits) > 1:
        # ⛔ لا يُختار أحدُهما اعتباطاً: ذراعان من شوطَين مختلفَين لا يُقارَنان.
        raise SystemExit("⛔ أكثرُ من ملفٍّ لـ" + pref + " في: " + " | ".join(hits)
                         + " ⇒ سَمِّ الجذرَ بدقّة: ذراعان من شوطَين لا يُقارَنان.")
    return hits[0] if hits else None


def judge(items, hyps):
    per = {}
    for it in items:
        h = hyps.get(it["id"])
        if not h or "error" in h or not h.get("text"):
            continue
        ws = scorer.score(it["refText"].split(), h["text"], J.cfg(it.get("riwaya"), True))["words"]
        acc = sum(1 for w in ws if w[1] in CONF)
        if acc / max(len(ws), 1) > COLLAPSE:
            per[it["id"]] = (0, 0, 1)          # كبحه الحارس: لا اتّهامَ — ولا حكمَ للمستخدم
            continue
        per[it["id"]] = (acc, len(ws), 0)
    return per


def boot(pairs, seed=7, n=4000):
    rng = random.Random(seed)
    d = []
    for _ in range(n):
        p = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
        a = sum(x[0] for x in p) / max(sum(x[1] for x in p), 1)
        b = sum(x[2] for x in p) / max(sum(x[3] for x in p), 1)
        d.append((b - a) * 100)
    d.sort()
    return d[int(0.025 * n)], d[int(0.975 * n)], sum(1 for x in d if x > 0) / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", required=True)
    ap.add_argument("--arms", nargs=2, default=["shipped", "base-ar"])
    ap.add_argument("--roots", nargs="+", default=["work"])
    a = ap.parse_args()
    P = plan()
    miss = []
    print("| المجموعة | ن | " + a.arms[0] + " | **" + a.arms[1] + "** | **الفرق** | مجال 95٪ | احتمالُ الارتفاع | كبحَ الحارسُ |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    pooled = []
    for s in a.sets:
        fa, fb = find(s, a.arms[0], a.roots), find(s, a.arms[1], a.roots)
        if not fa or not fb:
            miss.append(s)
            print(f"| `{s}` | ⛔ ناقصٌ ({'المشحون' if not fa else 'المرشَّح'}) | | | | | | |")
            continue
        ha = json.load(open(fa, encoding="utf-8"))["hyps"]
        hb = json.load(open(fb, encoding="utf-8"))["hyps"]
        ids = sorted(set(ha) & set(hb) & set(P))
        items = [P[i] for i in ids]
        pa, pb = judge(items, ha), judge(items, hb)
        k = [i for i in pa if i in pb]
        if len(k) < 20:
            raise SystemExit(f"⛔ `{s}`: {len(k)} بنداً فقط — لا يُقرأ الصفرُ نتيجةً")
        pairs = [(pa[i][0], pa[i][1], pb[i][0], pb[i][1]) for i in k]
        pooled += [(s + "/" + i, pa[i], pb[i]) for i in k]
        A = sum(x[0] for x in pairs) / max(sum(x[1] for x in pairs), 1) * 100
        B = sum(x[2] for x in pairs) / max(sum(x[3] for x in pairs), 1) * 100
        lo, hi, p = boot(pairs)
        print(f"| `{s}` | {len(k)} | {A:.2f}٪ | **{B:.2f}٪** | **{B-A:+.2f}** | [{lo:+.2f} .. **{hi:+.2f}**] | "
              f"{p*100:.1f}٪ | {sum(x[1][2] for x in pooled if x[0].startswith(s+'/'))} ⇒ {sum(x[2][2] for x in pooled if x[0].startswith(s+'/'))} |")
    if len(pooled) > 40:
        pairs = [(x[1][0], x[1][1], x[2][0], x[2][1]) for x in pooled]
        A = sum(x[0] for x in pairs) / max(sum(x[1] for x in pairs), 1) * 100
        B = sum(x[2] for x in pairs) / max(sum(x[3] for x in pairs), 1) * 100
        lo, hi, p = boot(pairs)
        ok = "✅" if hi <= 0 else "⛔"
        print(f"| **المضمومة** | **{len(pairs)}** | **{A:.2f}٪** | **{B:.2f}٪** | **{B-A:+.2f}** | "
              f"[{lo:+.2f} .. **{hi:+.2f}**] | **{p*100:.1f}٪** | {ok} |")
    # ⛔ **جدولٌ كلُّه «ناقص» بخروجٍ ناجحٍ عطبٌ لا نتيجة** — وقع هذا الليلةَ في `emu-gate`
    # مرّتين (جدولٌ فارغٌ بخروجٍ ناجح) فصار الخروجُ يشهد لما طُبع: ما نقص يُعلَن رقماً.
    if not pooled:
        raise SystemExit("⛔ لم تُقَس مجموعةٌ واحدة (الناقص: " + " · ".join(miss or a.sets)
                         + ") — لا يُقرأ الجدولُ الفارغُ نتيجةً")
    if miss:
        print(chr(10) + "⚠️ **نقصت " + str(len(miss)) + " مجموعة:** " + " · ".join(miss)
              + " — المضمومةُ دونها.")


if __name__ == "__main__":
    sys.exit(main())
