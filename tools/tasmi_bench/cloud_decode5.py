#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎛️☁️ **الجولةُ الخامسة: مفاتيحُ الفكّ السحابيّ الثلاثة بنافذة 6ث** (‏المكلّفُ بالقياس · 2026-10-03).

يقرأ فرضيّاتِ `cloud_gate_windows.py --arm …` (‏بنصّ كلّ نافذةٍ في `parts`) على مجموعتَي g3r ويحكم لكلّ مفتاحٍ مقابل
الافتراض (‏`cloud-w6` · بلا رأس):
- `TASMI_CLOUD_DECODE_GUARD` ⇐ الذراع `cloud-w6-guard` (‏`x-tasmi-decode: nocond,hst`).
- `TASMI_CLOUD_NEUTRAL_PROMPT` ⇐ الذراع `cloud-w6-prompt` (‏`x-tasmi-decode: prompt`) — ومعه: هل يُردَّد التلقين؟
- `RECITE_CLOUD_EDGE_FRAGMENTS` ⇐ الذراع `cloud-w6-edge` **تُصنع هنا** من نصّ الافتراض نفسِه بلا نداءٍ إضافيّ: مرآةُ منطق
  `WhisperHallucination.stripEdges` (‏لا نسخُ الملفّ) تُطبَّق على **كلّ نافذةٍ** قبل الوصل كما يفعل `ReciteWithMeViewModel`.

المقاييس لكلّ (مجموعة × ذراع)، والفرقُ المزدوجُ بالبند مقابل الافتراض بمجال 95٪ (‏bootstrap عنقوديّ · بذرة 7):
- **الهلوسة** بالنافذة: كلمةٌ من عبارات القنوات ليست في الآية، أو ≥2 كلمتان بلا كلمةٍ من الآية (‏تعريفُ `cloud_report.py`)؛
  والفرقُ على «بندٌ فيه نافذةٌ مهلوِسة».
- **WER** على نصّ البند الموصول مقابل **المتلوّ فعلاً** (‏الآيةُ بعد الحقن: حذفٌ/إبدالٌ/إدخالٌ/تبديلٌ بكلمة المتبرّع).
- **الاتّهامُ الكاذب والكشف** بالحاكم المعتمد `v2_gate.score_g3r` (‏`RecitationScorer` · خارج نطاق الحقن ±1).
- **ترديدُ التلقين**: نافذةٌ فيها كلمةٌ من «تلاوة بالعربية الفصحى» ليست في الآية (‏العبارةُ كاملةً يُسقطها الخادمُ قبل الردّ،
  فأثرُها الكامل يظهر نافذةً **فارغةً** بمقاطعَ واثقة — يُعدّ أيضاً).
- **البقايا**: نوافذُ غيّرها `stripEdges` وعددُ الكلمات المحذوفة.

**معيارُ الإشعال (‏أمرُ المكلِّف):** في المجموعتَين معاً الحدُّ الأعلى لمجال فرق الاتّهام الكاذب ≤ 0 **و**الحدُّ الأدنى لمجال فرق
الكشف ≥ 0، **مع** كسبٍ مقيس (‏مجالُ الهلوسة أو WER أو الاتّهام أو الكشف كلُّه في الاتّجاه الحسن في مجموعةٍ واحدةٍ على الأقلّ).

    python cloud_decode5.py --selftest
    python cloud_decode5.py --md work/decode5_verdict.md --json work/decode5_verdict.json
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorer  # noqa: E402
from speed_ab import norm_words, edits  # noqa: E402
from cloud_report import classify  # noqa: E402

WORK = os.path.join(HERE, "work")
PATTERN = "work/hyps_{arm}_{tag}_gate_cap10.json"
SETS = ("g3r:noisy", "g3r:clean")
BASE = "cloud-w6"
KEYS = [("TASMI_CLOUD_DECODE_GUARD", "cloud-w6-guard", "`x-tasmi-decode: nocond,hst`"),
        ("TASMI_CLOUD_NEUTRAL_PROMPT", "cloud-w6-prompt", "`x-tasmi-decode: prompt`"),
        ("RECITE_CLOUD_EDGE_FRAGMENTS", "cloud-w6-edge", "`stripEdges` لكلّ نافذة (‏على نصّ الافتراض نفسِه)")]

# ── مرآةُ منطق `WhisperHallucination` (‏القوائمُ نصوصُ بياناتٍ مطابقةٌ للمحرّك والخادم؛ المنطقُ مكتوبٌ هنا بايثونياً) ──
PHRASE_TEXTS = [
    "لا تنسوا الاشتراك في القناة", "لا تنسى الاشتراك في القناة", "لا تنسوا الاشتراك", "لا تنسى الاشتراك",
    "الاشتراك في القناة", "اشتركوا في القناة", "اشترك في القناة", "اشتركوا في قناتي",
    "شكرا لكم على المشاهدة", "شكرا على المشاهدة", "شكرا للمشاهدة", "شكرا لمشاهدتكم",
    "ترجمة نانسي قنقر", "نانسي قنقر", "الموسيقى", "موسيقى", "تلاوة بالعربية الفصحى",
]
EDGE_ANCHOR_TEXTS = ["اشتركوا", "اشترك", "الاشتراك", "القناة", "قناتي",
                     "المشاهدة", "للمشاهدة", "لمشاهدتكم", "ترجمة", "نانسي", "قنقر"]
PHRASES = [[scorer.norm(w) for w in p.split(" ")] for p in PHRASE_TEXTS]
ANCHORS = {scorer.norm(w) for w in EDGE_ANCHOR_TEXTS}
PROMPT_WORDS = set(norm_words("تلاوة بالعربية الفصحى"))


def _same(heard, want, first):
    return heard == want or (first and len(heard) == len(want) + 1 and heard[0] == "و" and heard.endswith(want))


def strip(text):
    words = (text or "").split()
    n = [scorer.norm(w) for w in words]
    keep = [True] * len(words)
    i = 0
    while i < len(words):
        p = next((ph for ph in PHRASES if i + len(ph) <= len(n) and all(_same(n[i + k], ph[k], k == 0) for k in range(len(ph)))), None)
        if p is not None:
            for k in range(i, i + len(p)):
                keep[k] = False
            i += len(p)
        else:
            i += 1
    return " ".join(w for w, k in zip(words, keep) if k)


def strip_edges(text):
    words = strip(text).split()
    if not words:
        return ""
    n = [scorer.norm(w) for w in words]
    tail = 0
    for ph in PHRASES:
        for k in range(len(ph) - 1, 0, -1):
            if k > len(n) or k <= tail:
                continue
            at = len(n) - k
            if all(_same(n[at + t], ph[t], t == 0) for t in range(k)) and any(ph[t] in ANCHORS for t in range(k)):
                tail = k
    rest = len(n) - tail
    head = 0
    for ph in PHRASES:
        for k in range(len(ph) - 1, 0, -1):
            if k > rest or k <= head:
                continue
            off = len(ph) - k
            if all(n[t] == ph[off + t] for t in range(k)) and any(ph[off + t] in ANCHORS for t in range(k)):
                head = k
    return " ".join(words[head:rest])


def selftest():
    """حالاتُ `WhisperHallucinationTest` في المحرّك حرفاً — المرآةُ لا تُستعمل قبل أن تطابقها."""
    cases = [
        (strip, "اشتركوا في القناة", ""), (strip, "شكراً للمشاهدة", ""), (strip, "موسيقى", ""),
        (strip, "قل ربي أعلم بعدتهم اشتركوا في القناة", "قل ربي أعلم بعدتهم"),
        (strip, "فهم فيه شركاء", "فهم فيه شركاء"), (strip, "في القناة", "في القناة"),
        (strip, "قل ربي أعلم بعدتهم واشتركوا في القناة", "قل ربي أعلم بعدتهم"),
        (strip, "لا تنسوا الاشتراك في القناة، ترجمة نانسي قنقر", ""),
        (strip, "ولا تنسوا الفضل بينكم", "ولا تنسوا الفضل بينكم"), (strip, "اعملوا آل داوود شكرا", "اعملوا آل داوود شكرا"),
        (strip_edges, "الحمد لله رب العالمين اشتركوا في", "الحمد لله رب العالمين"),
        (strip_edges, "الحمد لله رب العالمين واشتركوا", "الحمد لله رب العالمين"),
        (strip_edges, "القناة الحمد لله رب العالمين", "الحمد لله رب العالمين"),
        (strip_edges, "في القناة الحمد لله رب العالمين", "الحمد لله رب العالمين"),
        (strip_edges, "للمشاهدة الرحمن الرحيم شكرا على", "الرحمن الرحيم شكرا على"),
        (strip_edges, "القناة", ""), (strip_edges, "اشتركوا في القناة", ""),
        (strip_edges, "الحمد القناة لله", "الحمد القناة لله"),
        (strip_edges, "فاذكروني أذكركم ولا تنسوا", "فاذكروني أذكركم ولا تنسوا"), (strip_edges, "في الأرض", "في الأرض"),
        (strip_edges, "اعملوا آل داوود شكرا", "اعملوا آل داوود شكرا"), (strip_edges, "قل هو الله أحد في", "قل هو الله أحد في"),
        (strip_edges, "شكرا على", "شكرا على"),
    ]
    bad = 0
    for f, x, want in cases:
        got = f(x)
        if got != want:
            bad += 1
            print(f"  ⛔ {f.__name__}({x!r}) = {got!r} · المتوقَّع {want!r}")
    print(f"{'✅' if not bad else '⛔'} مرآةُ WhisperHallucination: {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


# ── القياس ────────────────────────────────────────────────────────────────────
def recited(it):
    """كلماتُ المتلوّ فعلاً بعد الحقن (‏مطبَّعةً) — مرآةُ جراحة `inject_riwaya_local.py`."""
    r = norm_words(it["refText"])
    i, op = it["wordIndex"], it["op"]
    dw = norm_words(it.get("donor", {}).get("word", ""))
    if op == "OMIT":
        return r[:i] + r[i + 1:]
    if op == "SUBSTITUTE":
        return r[:i] + dw + r[i + 1:]
    if op == "INSERT":
        return r[:i] + dw + r[i:]
    if op == "SWAP" and i + 1 < len(r):
        return r[:i] + [r[i + 1], r[i]] + r[i + 2:]
    return r


def load(arm, set_name):
    import emu_sweep as E
    p = os.path.join(HERE, PATTERN.format(arm=arm, tag=E.tag_of(set_name)))
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def make_edge(set_name):
    """ذراعُ `cloud-w6-edge` من `cloud-w6` نفسِه: `stripEdges` لكلّ نافذة ثمّ الوصل (‏لا نداء)."""
    import emu_sweep as E
    j = load(BASE, set_name)
    if not j:
        return None
    out, changed, removed = {}, 0, 0
    for i, h in j["hyps"].items():
        parts = h.get("parts")
        if parts is None:
            raise SystemExit(f"⛔ {i}: لا `parts` في {BASE} — شغّل cloud_gate_windows.py بـ--arm")
        new = []
        for p in parts:
            if p is None:
                new.append(None)
                continue
            q = strip_edges(p)
            if q != p:
                changed += 1
                removed += len(p.split()) - len(q.split())
            new.append(q)
        g = dict(h)
        g["parts"] = new
        g["text"] = " ".join(p for p in new if p)
        out[i] = g
    p = os.path.join(HERE, PATTERN.format(arm="cloud-w6-edge", tag=E.tag_of(set_name)))
    json.dump({"model": j.get("model"), "window_s": j.get("window_s"), "decode": "stripEdges(device)",
               "note": "مشتقٌّ من cloud-w6 بلا نداء: stripEdges لكلّ نافذة", "hyps": out},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"changed": changed, "removed": removed}


def _boot_ratio(pairs, seed=7, boot=2000):
    """[(a_num, a_den, b_num, b_den)] بالبند ⇒ مجالُ (Σb_num/Σb_den − Σa_num/Σa_den)."""
    if not pairs:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    ds = []
    for _ in range(boot):
        pk = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
        ds.append(sum(p[2] for p in pk) / max(1, sum(p[3] for p in pk)) - sum(p[0] for p in pk) / max(1, sum(p[1] for p in pk)))
    ds.sort()
    return ds[int(0.025 * boot)], ds[int(0.975 * boot) - 1]


def per_item(h, it):
    ay = set(norm_words(it["refText"])) | set(norm_words(it.get("donor", {}).get("word", "")))
    parts = h.get("parts") or [h.get("text", "")]
    segs = h.get("segs") or [None] * len(parts)
    hall = blk = echo = empty = empty_conf = nwin = 0
    for p, sg in zip(parts, segs):
        if p is None:
            continue
        nwin += 1
        hw, ha, bl = classify(p, it["refText"])
        hall += ha
        blk += bl
        if any(w in PROMPT_WORDS and w not in ay for w in hw):
            echo += 1
        if not hw:
            empty += 1
            if sg and any(s.get("nsp", 1) < 0.5 for s in sg):
                empty_conf += 1
    rw = recited(it)
    e = edits(norm_words(h.get("text", "")), rw)
    return {"hall": hall, "blk": blk, "echo": echo, "empty": empty, "empty_conf": empty_conf, "nwin": nwin,
            "edits": e, "len": len(rw), "ms": h.get("ms", 0)}


def fmt_ci(d, lo, hi, scale=100, nd=1):
    return f"{d*scale:+.{nd}f} [{lo*scale:+.{nd}f}..{hi*scale:+.{nd}f}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--md", default=os.path.join(WORK, "decode5_verdict.md"))
    ap.add_argument("--json", default=os.path.join(WORK, "decode5_verdict.json"))
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(selftest())
    if selftest():
        raise SystemExit("⛔ المرآةُ لا تطابق المحرّك — لا قياس")
    import v2_gate as G
    G.PATTERN = PATTERN
    plan = {it["id"]: it for it in json.load(open(os.path.join(HERE, "inject_plan_riwaya.json"), encoding="utf-8"))["items"]}
    edge_stats = {s: make_edge(s) for s in SETS}
    L = ["## 🎛️ الجولةُ الخامسة — مفاتيحُ الفكّ السحابيّ بنافذة 6ث (‏g3r · `v2_gate`)", ""]
    res = {"edge_stats": edge_stats, "rows": {}}
    L += ["| المجموعة | الذراع | ن | نوافذ | هلوسة (نوافذ) | منها قناة | بنودٌ مهلوِسة | Δ بنودٍ مهلوِسة [95٪] | WER | Δ WER [95٪] | "
          "FA | Δ FA [95٪] | الكشف | Δ الكشف [95٪] | فارغة (منها بمقاطع واثقة) | ترديدُ التلقين | وسيطُ زمن البند |",
          "|---|---|---:|---:|---:|---:|---:|---|---:|---|---:|---|---:|---|---:|---:|---:|"]
    verdict = {}
    for s in SETS:
        jb = load(BASE, s)
        if not jb:
            L.append(f"| {s} | ⛔ لا فرضيّاتٍ للافتراض | | | | | | | | | | | | | | | |")
            continue
        hb = {i: h for i, h in jb["hyps"].items() if "error" not in h and i in plan}
        for arm in [BASE] + [k[1] for k in KEYS]:
            j = load(arm, s)
            if not j:
                L.append(f"| {s} | {arm} ⛔ غائب | | | | | | | | | | | | | | | |")
                continue
            ha = {i: h for i, h in j["hyps"].items() if "error" not in h and i in plan}
            ids = sorted(set(ha) & set(hb))
            A = {i: per_item(ha[i], plan[i]) for i in ids}
            B = {i: per_item(hb[i], plan[i]) for i in ids}
            n = len(ids)
            nwin = sum(v["nwin"] for v in A.values())
            hall_items = sum(1 for v in A.values() if v["hall"])
            dh = [(int(B[i]["hall"] > 0), 1, int(A[i]["hall"] > 0), 1) for i in ids]
            dh_d = (hall_items - sum(1 for v in B.values() if v["hall"])) / max(1, n)
            dh_lo, dh_hi = _boot_ratio(dh)
            wer = sum(v["edits"] for v in A.values()) / max(1, sum(v["len"] for v in A.values()))
            werb = sum(v["edits"] for v in B.values()) / max(1, sum(v["len"] for v in B.values()))
            dw = [(B[i]["edits"], B[i]["len"], A[i]["edits"], A[i]["len"]) for i in ids]
            dw_lo, dw_hi = _boot_ratio(dw)
            g = G.score_g3r(s, (BASE, arm)) if arm != BASE else G.score_g3r(s, (BASE, BASE))
            ms = sorted(v["ms"] for v in A.values())
            row = {"n": n, "nwin": nwin, "hall_win": sum(v["hall"] for v in A.values()), "blk": sum(v["blk"] for v in A.values()),
                   "hall_items": hall_items, "d_hall": (dh_d, dh_lo, dh_hi), "wer": wer, "d_wer": (wer - werb, dw_lo, dw_hi),
                   "fa": g["fa"][1] if g else None, "d_fa": (g["fa_diff"], *g["ci"]) if g else None,
                   "det": g["detect"][1] if g else None, "d_det": (g["det_diff"], *g["det_ci"]) if g else None,
                   "g_n": g["n"] if g else 0,
                   "empty": sum(v["empty"] for v in A.values()), "empty_conf": sum(v["empty_conf"] for v in A.values()),
                   "echo": sum(v["echo"] for v in A.values()), "med_ms": ms[len(ms) // 2] if ms else 0}
            res["rows"][f"{s}/{arm}"] = row
            base = arm == BASE
            L.append("| %s | %s | %d | %d | %d (%.1f%%) | %d | %d | %s | %.1f%% | %s | %s | %s | %s | %s | %d (%d) | %d | %.1fث |" % (
                s, f"**{arm}**" if base else arm, n, nwin, row["hall_win"], 100 * row["hall_win"] / max(1, nwin), row["blk"],
                hall_items, "—" if base else fmt_ci(*row["d_hall"]), 100 * wer, "—" if base else fmt_ci(*row["d_wer"]),
                f"{100*row['fa']:.2f}%" if g else "—", "—" if base or not g else fmt_ci(*row["d_fa"], nd=2),
                f"{100*row['det']:.1f}%" if g else "—", "—" if base or not g else fmt_ci(*row["d_det"]),
                row["empty"], row["empty_conf"], row["echo"], row["med_ms"] / 1000))
            if not base:
                verdict.setdefault(arm, []).append((s, row))
    L += ["", "**البقايا (‏`stripEdges` على نوافذ الافتراض):** " + " · ".join(
        f"{s}: {v['changed']} نافذةً تغيّرت · {v['removed']} كلمةً حُذفت" for s, v in edge_stats.items() if v), ""]
    L += ["### ⚖️ الحكم بالمعيار (‏FA: الحدُّ الأعلى ≤ 0 · الكشف: الحدُّ الأدنى ≥ 0 · في المجموعتَين · مع كسبٍ مقيس)", "",
          "| المفتاح | الذراع | عدمُ الدونيّة | الكسبُ المقيس | **الحكم** |", "|---|---|---|---|---|"]
    for key, arm, desc in KEYS:
        rows = verdict.get(arm, [])
        if len(rows) < len(SETS) or any(r["d_fa"] is None for _, r in rows):
            L.append(f"| `{key}` | {desc} | ⛔ قياسٌ ناقص | — | ⛔ يبقى مطفأً (‏لا حكمَ بعيّنةٍ ناقصة) |")
            continue
        noninf = all(r["d_fa"][2] <= 1e-12 and r["d_det"][1] >= -1e-12 for _, r in rows)
        gains = []
        for s, r in rows:
            if r["d_hall"][2] < 0: gains.append(f"هلوسة {s} {fmt_ci(*r['d_hall'])}")
            if r["d_wer"][2] < 0: gains.append(f"WER {s} {fmt_ci(*r['d_wer'])}")
            if r["d_fa"][2] < 0: gains.append(f"FA {s} {fmt_ci(*r['d_fa'], nd=2)}")
            if r["d_det"][1] > 0: gains.append(f"كشف {s} {fmt_ci(*r['d_det'])}")
        bad = [f"{s}: FA أعلى {100*r['d_fa'][2]:+.2f} · كشف أدنى {100*r['d_det'][1]:+.1f}" for s, r in rows]
        on = noninf and bool(gains)
        L.append(f"| `{key}` | {desc} | {'✅' if noninf else '⛔'} {' · '.join(bad)} | {' · '.join(gains) or 'لا كسبَ مقيس'} | "
                 f"{'✅ **يُشعل**' if on else '⛔ **يبقى مطفأً**'} |")
        res.setdefault("verdict", {})[key] = {"on": on, "noninferior": noninf, "gains": gains}
    md = "\n".join(L) + "\n"
    os.makedirs(os.path.dirname(a.md), exist_ok=True)
    open(a.md, "w", encoding="utf-8").write(md)
    json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(md)


if __name__ == "__main__":
    main()
