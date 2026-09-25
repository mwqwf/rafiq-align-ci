#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🚪 بوّابة المتعلّم الحقيقي (g5 · الطبقة أ) — **مسطرةٌ واحدةٌ** لكل رقمٍ على مادّة المتعلّمين.

لماذا وُجدت: رقمُ D-813 (2.98٪) حُسب على مقامٍ ثلثُه ليس سالباً موثوقاً — صفوفٌ صوتُها منزاح
(‏`audio_offset≠0` · D-726) وكلماتٌ سليمةٌ جارةٌ لخطأٍ في تسجيلٍ موجب (خلاف D-724). فهذه الأداة
تجعل المسطرة في مكانٍ واحد، وكلُّ مقايسةٍ لاحقةٍ على المتعلّمين تمرّ بها.

**المسطرة الموحّدة** (تُطبَّق قبل أيّ عدّ، وتُعَدّ أسبابُ الإسقاط وتُطبع):
1. يُسقط كلُّ صفٍّ `audio_offset` فيه غيرُ صفرٍ أو مجهول (D-726).
2. يُسقط كلُّ صفٍّ لا يساوي فيه عددُ الوسوم `n_ref` وعددَ كلمات النصّ.
3. يُسقط صفٌّ نوعُه يناقض وسومه (سالبٌ فيه وسمُ خطأ، أو موجبٌ بلا وسم).
4. يُسقط صفٌّ ينقصه تفريغُ أيّ شاهدٍ مطلوب، فتبقى العيّنةُ واحدةً لكل الأذرع (مقارنةٌ زوجية).
5. **الاتّهامُ الكاذب من التسجيلات السليمة وحدها** (`kind=سالب`، D-724)؛ الكلماتُ السليمةُ في
   تسجيلٍ موجب لا تُعدّ سالباً ولا موجباً، ويُطبع عددُها.
6. **الكشف** على الكلمات الموسومة خطأً في التسجيلات الموجبة. والاتّهامُ = `MISSED` أو `SUBSTITUTED`.
7. ⛔ نصُّ الآية في الملفّ يُطابَق حرفاً بـ`text_<riwaya>.jz` الموثَّق في المستودع، وإلا توقّفت الأداة.

**الإحصاء:** مجالُ Wilson، وbootstrap عنقوديٌّ **بالتسجيل** (2000 عيّنة، بذرة ثابتة)، وMcNemar
الدقيق على الكلمة عينها بين ذراعين. **شرطُ عدم الدونيّة** (`--gate A B`): الحدُّ الأعلى لمجال 95٪
لفرق الاتّهام الكاذب الزوجي (B−A) ≤ +0.5 نقطة، والكشفُ لا يهبط أكثر من كلمتين.
⚠️ بـ51 كلمةً خاطئة لا يُميَّز تحسّنُ الكشف دون نحو 15 نقطة: البوّابةُ تحمي من التراجع ولا تُثبت القفزة.

**مرآةُ إعداد المحرك (خطة الحَكَم 2026-09-25 §٣ · الافتراض):** كلُّ حكمٍ بـ`detect_score.engine_cfg_for`
(‏`strict_short=True` مع فهرس `critical_long` مشتقّاً من النصّ الموثَّق) كما يحكم التطبيقُ المشحون؛ و`--no-engine-cfg`
يعيد مرآةَ `cfg_for` القديمة للمقارنة وحدَها. ويُكتب الإعدادُ في خطّ الأساس، **وخطٌّ بإعدادٍ غيرِ إعداد الشوط يوقف الأداة**.
وثلاثةُ أعمدةٍ تُطبع بجانب الاتّهام والكشف ولا تدخل البوّابة:
- **الشكّ:** كلماتٌ سليمةٌ لم تُتّهم وحكمُ الشاهد الأوّل عليها `UNCERTAIN` (‏تُعرض ولا تُحسب زلّة · D-231).
- **الكشفُ بحسب وسم الصفّ** (‏`error_tags`، وهي على الصفّ لا على الكلمة): فطبقةُ «التجويد وحده» تُطبع مستقلّةً لا تُحذف.
- **تسرّبُ الإبدال عند مسافة 2** (‏`--leak`): كلُّ كلمةٍ من التسجيلات السليمة تُبدَّل في **المرجع** بكلمةٍ قرآنيةٍ
  مسافتُها 2، والتفريغُ كما هو (‏فالقارئُ قرأ غيرَ المطلوب)؛ التسرّبُ = لا اتّهامَ ولا شكّ. ⛔ دراسةٌ داخليةٌ
  لا يُعرض فيها نصٌّ محرَّفٌ ولا يُشحن، والبدائلُ كلماتٌ من المصحف نفسِه لا مولَّدة.

الأذرع: `tiny` · `base` · `turbo` (شاهدٌ واحد)، و`A+B:veto` (قاعدة D-813: يُتّهم ما اتّهمه A ما لم
يسمعه B صحيحاً)، و`A+B:and` و`A+B:or`.

    python tools/tasmi_bench/learner_gate.py                       # الجدول كلّه
    python tools/tasmi_bench/learner_gate.py --gate base tiny+base:veto --out work/learner_gate.json
    python tools/tasmi_bench/learner_gate.py --scorer-dir ../QuranRafiq/tools/tasmi_bench   # مرآةٌ أخرى
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import random
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, "core", "quran", "src", "main", "assets", "quran")
ACCUSE = {"MISSED", "SUBSTITUTED"}
NI_FA_MAX = 0.5      # نقطة مئوية: أعلى مجال 95٪ لفرق الاتّهام الكاذب الزوجي
NI_DET_MAX_DROP = 2  # كلمات: أقصى هبوطٍ في الكشف

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 2), round(100 * (c + h), 2)]


def mcnemar_p(b: int, c: int) -> float:
    """McNemar الدقيق ثنائيُّ الذيل على الأزواج المتنافرة."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def load_gold(path: str):
    meta, rows = None, []
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        x = json.loads(line)
        if x.get("type") == "meta":
            meta = x
        else:
            rows.append(x)
    return meta, rows


def check_text(rows: list) -> dict:
    """⛔ حارسُ النصّ: كلُّ `ref_text` يطابق حرفاً آيتَه في `text_<riwaya>.jz`."""
    texts, bad = {}, []
    for r in rows:
        rw = r["riwaya"]
        if rw not in texts:
            p = os.path.join(ASSETS, f"text_{rw}.jz")
            if not os.path.exists(p):
                # ⛔ غيابُ النصّ الموثَّق يوقف الأداة (كما يقول رأسُها) ولا يمرّ بـ«checked: False» صامتاً.
                raise SystemExit("⛔ لا نصَّ موثَّقاً في المستودع لمطابقة ملفّ الذهب: " + p)
            texts[rw] = json.loads(zlib.decompress(open(p, "rb").read(), 47))
        if texts[rw][r["flat"]] != r["ref_text"]:
            bad.append(r["key"])
    if bad:
        raise SystemExit(f"⛔ نصُّ الآية في ملفّ الذهب لا يطابق النصَّ الموثَّق في {len(bad)} صفّاً: {bad[:5]}")
    return {"checked": True, "rows": len(rows)}


def apply_ruler(rows: list, need: set) -> tuple:
    kept, why = [], {"audio_offset_nonzero_or_unknown": 0, "len_mismatch": 0,
                     "kind_contradicts_labels": 0, "missing_witness": 0}
    for r in rows:
        if r.get("audio_offset") != 0:
            why["audio_offset_nonzero_or_unknown"] += 1
            continue
        if not (len(r["labels"]) == r["n_ref"] == len(r["ref_text"].split())):
            why["len_mismatch"] += 1
            continue
        has = "1" in r["labels"]
        if (r["kind"] == "سالب" and has) or (r["kind"] == "موجب" and not has) or r["kind"] not in ("سالب", "موجب"):
            why["kind_contradicts_labels"] += 1
            continue
        if any(not isinstance(r["hyp"].get(w), str) for w in need):
            why["missing_witness"] += 1
            continue
        kept.append(r)
    return kept, why


def parse_arm(name: str) -> tuple:
    if ":" in name:
        ws, rule = name.split(":")
        ws = ws.split("+")
        if rule not in ("veto", "and", "or") or len(ws) < 2:
            raise SystemExit("ذراعٌ غير معروفة: " + name)
        return ws, rule
    return [name], None


def verdicts(sc, cfg_for, rows: list, witness: str) -> list:
    out = []
    for r in rows:
        ref = r["ref_text"].split()
        res = sc.score(ref, r["hyp"][witness], cfg_for(r["riwaya"]))
        st = [t[1] if isinstance(t, (list, tuple)) else str(t) for t in res["words"]]
        if len(st) != len(ref):
            raise SystemExit(f"⛔ المسجّل أعاد {len(st)} حكماً لـ{len(ref)} كلمة في {r['key']}")
        out.append(st)
    return out


def arm_uncertain(per_w: dict, ws: list, acc: list) -> list:
    """لكل كلمة: لم تتّهمها الذراعُ وحكمُ شاهدها الأوّل `UNCERTAIN` (‏كما يعرضها التطبيق)."""
    return [[(not a) and s == "UNCERTAIN" for a, s in zip(ar, sr)] for ar, sr in zip(acc, per_w[ws[0]])]


def tag_of(r: dict) -> str:
    return "+".join(sorted(r.get("error_tags") or [])) or "بلا وسم"


def by_tag(rows: list, acc: list) -> dict:
    """الكشفُ مقسوماً بوسوم الصفّ (‏كلُّ كلمةٍ خاطئةٍ تُنسب إلى وسوم صفّها)."""
    out = {}
    for r, a in zip(rows, acc):
        if r["kind"] != "موجب":
            continue
        d = out.setdefault(tag_of(r), [0, 0])
        for j, l in enumerate(r["labels"]):
            if l == "1":
                d[1] += 1
                d[0] += a[j]
    return {t: {"det": d, "marked": m, "det_pct": round(pct(d, m), 1)} for t, (d, m) in sorted(out.items(), key=lambda kv: -kv[1][1])}


LEAK_SEED = 7


def leak_d2(sc, cfg_for, base_cfg_for, rows: list, witnesses: list, arms: dict) -> dict:
    """تسرّبُ الإبدال عند مسافة 2 (‏منقولٌ عن `drill.py` فئة d2): على السليم وحده، كلُّ كلمةٍ تُبدَّل في المرجع
    بصورةٍ قرآنيةٍ مسافتُها 2 (‏الرسمُ الأوّلُ لها في مصحف الرواية)، ويُعاد الحكمُ بالتفريغ المخزّن نفسِه.
    ‏`base_cfg_for` يطبّع المفردات (‏`cfg_for` كما في `drill.py`)، و`cfg_for` يحكم (‏إعدادُ الشوط)."""
    texts, vocab, bylen, cand = {}, {}, {}, {}

    def voc(rw):
        if rw not in vocab:
            if rw not in texts:
                texts[rw] = json.loads(zlib.decompress(open(os.path.join(ASSETS, f"text_{rw}.jz"), "rb").read(), 47))
            c, v = base_cfg_for(rw), {}
            for ay in texts[rw]:
                for t in ay.split():
                    n = sc.norm(t, c)
                    if n and n not in v:
                        v[n] = t
            vocab[rw] = v
            bl = {}
            for n in v:
                bl.setdefault(len(n), []).append(n)
            bylen[rw] = bl
        return vocab[rw]

    def pick(rw, word, rng):
        n0 = sc.norm(word, base_cfg_for(rw))
        if not n0:
            return None
        v = voc(rw)
        if (rw, n0) not in cand:
            cs = [n for l in range(max(1, len(n0) - 2), len(n0) + 3) for n in bylen[rw].get(l, ())
                  if n != n0 and sc._edit(n0, n) == 2]
            cand[(rw, n0)] = sorted(cs)
        cs = cand[(rw, n0)]
        return v[rng.choice(cs)] if cs else None

    rng = random.Random(LEAK_SEED)
    res = {a: {"n": 0, "acc": 0, "unc": 0, "pass": 0} for a in arms}
    none = 0
    for r in rows:
        if r["kind"] != "سالب":
            continue
        ref, cf = r["ref_text"].split(), cfg_for(r["riwaya"])
        for j in range(len(ref)):
            sub = pick(r["riwaya"], ref[j], rng)
            if sub is None:
                none += 1
                continue
            ref2 = ref[:j] + [sub] + ref[j + 1:]
            st = {w: [t[1] for t in sc.score(ref2, r["hyp"][w], cf)["words"]] for w in witnesses}
            for a, (ws, rule) in arms.items():
                acc = arm_accusations({w: [st[w]] for w in ws}, ws, rule)[0][j]
                unc = (not acc) and st[ws[0]][j] == "UNCERTAIN"
                d = res[a]
                d["n"] += 1
                d["acc"] += acc
                d["unc"] += unc
                d["pass"] += (not acc) and not unc
    for d in res.values():
        d["leak_pct"] = round(pct(d["pass"], d["n"]), 1)
        d["leak_wilson95"] = wilson(d["pass"], d["n"])
    return {"seed": LEAK_SEED, "no_substitute": none, "arms": res}


def arm_accusations(per_w: dict, ws: list, rule) -> list:
    """قائمةٌ لكلّ صفّ: لكل كلمة هل اتُّهمت (bool)."""
    if rule is None:
        return [[s in ACCUSE for s in row] for row in per_w[ws[0]]]
    out = []
    for i in range(len(per_w[ws[0]])):
        rows = [per_w[w][i] for w in ws]
        acc = []
        for j in range(len(rows[0])):
            a = [r[j] in ACCUSE for r in rows]
            if rule == "veto":
                acc.append(a[0] and not any(r[j] == "CORRECT" for r in rows[1:]))
            elif rule == "and":
                acc.append(all(a))
            else:
                acc.append(any(a))
        out.append(acc)
    return out


def counts(rows: list, acc: list, idx=None) -> tuple:
    """(fa, clean, det, marked) على صفوف `idx` (افتراضاً كلّها)."""
    fa = cl = de = mk = 0
    for i in (range(len(rows)) if idx is None else idx):
        r, a = rows[i], acc[i]
        if r["kind"] == "سالب":
            cl += len(a)
            fa += sum(a)
        else:
            for j, l in enumerate(r["labels"]):
                if l == "1":
                    mk += 1
                    de += a[j]
    return fa, cl, de, mk


def pct(k, n):
    return 100.0 * k / n if n else 0.0


class Boot:
    """bootstrap عنقوديٌّ بالتسجيل: تُعاد عيّنةُ التسجيلات (rec) بالإحلال، بذرةٌ ثابتة."""

    def __init__(self, rows: list, n: int = 2000, seed: int = 20260925):
        byrec = {}
        for i, r in enumerate(rows):
            byrec.setdefault(r["rec"], []).append(i)
        recs = sorted(byrec)
        rng = random.Random(seed)
        self.samples = []
        for _ in range(n):
            idx = []
            for _k in range(len(recs)):
                idx.extend(byrec[recs[rng.randrange(len(recs))]])
            self.samples.append(idx)
        self.n_recordings = len(recs)

    def ci(self, fn) -> list:
        v = sorted(fn(s) for s in self.samples)
        # مئينان متناظران: كان الأعلى `v[int(0.975n)-1]` يقع دون المتناظر بمرتبةٍ حين لا يكون 0.025n صحيحاً،
        # فيخفض الحدَّ الأعلى الذي يُحكم عليه شرطُ عدم الدونيّة (أيسرُ خداعاً). الآن `v[n-1-k]` مع `v[k]`.
        k = int(0.025 * len(v))
        lo, hi = v[k], v[len(v) - 1 - k]
        return [round(lo, 2), round(hi, 2)]


def summarize(rows, acc, boot, unc=None) -> dict:
    fa, cl, de, mk = counts(rows, acc)
    un = sum(sum(u) for r, u in zip(rows, unc) if r["kind"] == "سالب") if unc is not None else None
    rec_acc = sum(1 for r, a in zip(rows, acc) if r["kind"] == "سالب" and any(a))
    by = {}
    for rw in sorted({r["riwaya"] for r in rows}):
        ix = [i for i, r in enumerate(rows) if r["riwaya"] == rw]
        f, c, d, m = counts(rows, acc, ix)
        by[rw] = {"fa": f, "clean": c, "fa_pct": round(pct(f, c), 2), "det": d, "marked": m,
                  "det_pct": round(pct(d, m), 1)}
    return {
        "fa": fa, "clean_words": cl, "fa_pct": round(pct(fa, cl), 2), "fa_wilson95": wilson(fa, cl),
        "fa_cluster95": boot.ci(lambda s: pct(*counts(rows, acc, s)[:2])),
        "det": de, "marked_words": mk, "det_pct": round(pct(de, mk), 1), "det_wilson95": wilson(de, mk),
        "det_cluster95": boot.ci(lambda s: pct(*counts(rows, acc, s)[2:])),
        "clean_recordings_accused": rec_acc,
        "clean_recordings": sum(1 for r in rows if r["kind"] == "سالب"),
        "by_riwaya": by,
        "uncertain_clean": un, "uncertain_clean_pct": None if un is None else round(pct(un, cl), 2),
        "det_by_row_tag": by_tag(rows, acc),
    }


def paired(rows, a1, a2, boot) -> dict:
    fb = fc = db = dc = 0
    for r, x, y in zip(rows, a1, a2):
        for j in range(len(x)):
            if r["kind"] == "سالب":
                fb += x[j] and not y[j]
                fc += y[j] and not x[j]
            elif r["labels"][j] == "1":
                db += x[j] and not y[j]
                dc += y[j] and not x[j]
    f1, c1, d1, m1 = counts(rows, a1)
    f2, c2, d2, m2 = counts(rows, a2)

    def dfa(s):
        p = counts(rows, a1, s)
        q = counts(rows, a2, s)
        return pct(q[0], q[1]) - pct(p[0], p[1])

    def ddet(s):
        p = counts(rows, a1, s)
        q = counts(rows, a2, s)
        return pct(q[2], q[3]) - pct(p[2], p[3])

    fa_ci = boot.ci(dfa)
    res = {
        "fa_delta_pts": round(pct(f2, c2) - pct(f1, c1), 2), "fa_delta_cluster95": fa_ci,
        "fa_mcnemar": {"a_only": fb, "b_only": fc, "p": float(f"{mcnemar_p(fb, fc):.3g}")},
        "det_delta_words": d2 - d1, "det_delta_pts": round(pct(d2, m2) - pct(d1, m1), 1),
        "det_delta_cluster95": boot.ci(ddet),
        "det_mcnemar": {"a_only": db, "b_only": dc, "p": float(f"{mcnemar_p(db, dc):.3g}")},
    }
    res["non_inferior"] = fa_ci[1] <= NI_FA_MAX and (d2 - d1) >= -NI_DET_MAX_DROP
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=os.path.join(HERE, "learner_gold_v1.jsonl"))
    ap.add_argument("--scorer-dir", default=HERE, help="مجلّد scorer.py وdetect_score.py (المرآة المقيسة)")
    ap.add_argument("--arms", nargs="*", default=["tiny", "base", "turbo", "tiny+base:veto", "base+tiny:veto",
                                                  "turbo+tiny:veto", "turbo+base:veto", "tiny+base:and"])
    ap.add_argument("--compare", nargs=2, action="append", default=[], metavar=("A", "B"),
                    help="مقارنةٌ زوجية (تُطبع ولا تُسقط البوّابة)")
    ap.add_argument("--gate", nargs=2, action="append", default=[], metavar=("A", "B"),
                    help="شرطُ عدم الدونيّة: B لا يدون A، وإلا خرجت الأداة برمز 1")
    ap.add_argument("--baseline", help="ملفُّ خطِّ أساسٍ (اتّهاماتُ كلّ ذراعٍ كلمةً كلمة): كلُّ ذراعٍ فيه تُحكم بعدم الدونيّة زوجياً")
    ap.add_argument("--write-baseline", help="يكتب اتّهاماتِ الأذرع الحالية خطَّ أساسٍ")
    ap.add_argument("--selftest", action="store_true", help="اختبارٌ ذاتيّ: حساباتٌ معروفة + المسطرة + خطُّ الأساس المودَع")
    ap.add_argument("--engine-cfg", action=argparse.BooleanOptionalAction, default=True,
                    help="مرآةُ إعداد المحرك (strict_short + critical_long) — الافتراض؛ --no-engine-cfg لمرآة cfg_for القديمة")
    ap.add_argument("--leak", action=argparse.BooleanOptionalAction, default=True,
                    help="عمودُ تسرّب الإبدال عند مسافة 2 (بلا صوت · دقيقةٌ تقريباً)")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--out")
    ap.add_argument("--md")
    x = ap.parse_args()
    if x.selftest:
        return selftest(x)

    sys.path.insert(0, os.path.abspath(x.scorer_dir))
    sc = importlib.import_module("scorer")
    ds = importlib.import_module("detect_score")
    if x.engine_cfg and not hasattr(ds, "engine_cfg_for"):
        raise SystemExit(f"⛔ {ds.__file__} بلا engine_cfg_for: مرآةُ المحرك غيرُ متاحة (‏--no-engine-cfg للقديمة صراحةً)")
    cfg_for = ds.engine_cfg_for if x.engine_cfg else ds.cfg_for
    cfg_name = "engine" if x.engine_cfg else "gate_mirror"
    scorer_sha = hashlib.sha256(open(sc.__file__, "rb").read()).hexdigest()[:12]

    meta, rows0 = load_gold(x.gold)
    text_check = check_text(rows0)
    arms = list(dict.fromkeys(x.arms + [a for p in x.compare + x.gate for a in p]))
    parsed = {a: parse_arm(a) for a in arms}
    need = {w for ws, _ in parsed.values() for w in ws}
    rows, why = apply_ruler(rows0, need)
    neighbours = sum(r["labels"].count("0") for r in rows if r["kind"] == "موجب")
    boot = Boot(rows, x.boot)
    per_w = {w: verdicts(sc, cfg_for, rows, w) for w in sorted(need)}
    acc = {a: arm_accusations(per_w, *parsed[a]) for a in arms}
    unc = {a: arm_uncertain(per_w, parsed[a][0], acc[a]) for a in arms}

    res = {
        "gold": os.path.basename(x.gold), "gold_rows": len(rows0), "gold_meta": meta and meta.get("name"),
        "scorer": os.path.relpath(sc.__file__, ROOT) if sc.__file__.startswith(ROOT) else sc.__file__,
        "scorer_sha256_12": scorer_sha, "cfg": cfg_name, "text_check": text_check,
        "ruler": {"kept_rows": len(rows), "recordings": boot.n_recordings, "dropped": why,
                  "neighbour_clean_words_in_positive_rows_excluded": neighbours},
        "bootstrap": {"n": x.boot, "unit": "recording"},
        "arms": {a: summarize(rows, acc[a], boot, unc[a]) for a in arms},
        "compare": {}, "gate": {},
    }
    for a, b in x.compare:
        res["compare"][f"{a} → {b}"] = paired(rows, acc[a], acc[b], boot)
    ok = True
    for a, b in x.gate:
        p = paired(rows, acc[a], acc[b], boot)
        res["gate"][f"{a} → {b}"] = p
        ok &= p["non_inferior"]
    if x.leak:
        res["leak_d2"] = leak_d2(sc, cfg_for, ds.cfg_for, rows, sorted(need), parsed)
    if x.baseline:
        bl = json.load(open(x.baseline, encoding="utf-8"))
        if bl.get("cfg", "gate_mirror") != cfg_name:
            raise SystemExit(f"⛔ خطُّ الأساس بإعداد {bl.get('cfg', 'gate_mirror')} والشوطُ بإعداد {cfg_name}: "
                             "المقارنةُ بين إعدادَين تُخفي الفرقَ في الإعداد نفسِه")
        for a, bits in bl["arms"].items():
            if a not in acc:
                continue
            if any(r["key"] not in bits for r in rows):
                raise SystemExit(f"⛔ خطُّ الأساس لا يغطّي صفوف المسطرة الحالية للذراع {a}")
            prev = [[c == "1" for c in bits[r["key"]]] for r in rows]
            p = paired(rows, prev, acc[a], boot)
            res["gate"][f"baseline:{a} → {a}"] = p
            ok &= p["non_inferior"]
    if x.write_baseline:
        json.dump({"gold": res["gold"], "scorer_sha256_12": scorer_sha, "cfg": cfg_name, "kept_rows": len(rows),
                   "arms": {a: {r["key"]: "".join("1" if v else "0" for v in acc[a][i]) for i, r in enumerate(rows)}
                            for a in arms},
                   "uncertain": {a: {r["key"]: "".join("1" if v else "0" for v in unc[a][i]) for i, r in enumerate(rows)}
                                 for a in arms}},
                  open(x.write_baseline, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    res["gate_pass"] = ok if res["gate"] else None

    lines = [f"### 🚪 بوّابة المتعلّم g5 · {res['gold']} · scorer {scorer_sha} · الإعداد {cfg_name}",
             f"المسطرة: {len(rows)} صفّاً من {len(rows0)} ({boot.n_recordings} تسجيلاً) · أُسقط: "
             + " · ".join(f"{k}={v}" for k, v in why.items())
             + f" · جاراتٌ مستبعَدة {neighbours}", "",
             "| الذراع | الاتّهام الكاذب | Wilson 95٪ | عنقودي 95٪ | الكشف | Wilson 95٪ | تسجيلاتٌ سليمة متّهَمة | الشكّ على السليم |"
             + (" تسرّبُ الإبدال (مسافة 2) |" if x.leak else ""),
             "|---|---|---|---|---|---|---|---|" + ("---|" if x.leak else "")]
    for a in arms:
        s = res["arms"][a]
        lk = res["leak_d2"]["arms"][a] if x.leak else None
        lines.append(f"| {a} | {s['fa']}/{s['clean_words']} = {s['fa_pct']}٪ | {s['fa_wilson95']} | {s['fa_cluster95']} "
                     f"| {s['det']}/{s['marked_words']} = {s['det_pct']}٪ | {s['det_wilson95']} "
                     f"| {s['clean_recordings_accused']}/{s['clean_recordings']} "
                     f"| {s['uncertain_clean']}/{s['clean_words']} = {s['uncertain_clean_pct']}٪ |"
                     + (f" {lk['pass']}/{lk['n']} = {lk['leak_pct']}٪ |" if lk else ""))
    tags = list(res["arms"][arms[0]]["det_by_row_tag"])
    lines += ["", "**الكشف بحسب وسم الصفّ** (‏الوسمُ على الصفّ لا على الكلمة):", "",
              "| الذراع | " + " | ".join(f"{t} ({res['arms'][arms[0]]['det_by_row_tag'][t]['marked']})" for t in tags) + " |",
              "|---|" + "---|" * len(tags)]
    for a in arms:
        bt = res["arms"][a]["det_by_row_tag"]
        lines.append(f"| {a} | " + " | ".join(f"{bt[t]['det']}" for t in tags) + " |")
    if x.leak:
        lines += ["", f"تسرّبُ الإبدال: {res['leak_d2']['arms'][arms[0]]['n']} حالةً لكل ذراع (بذرة {LEAK_SEED}) · "
                  f"بلا بديلٍ بمسافة 2: {res['leak_d2']['no_substitute']} كلمة · التسرّب = لا اتّهامَ ولا شكّ"]
    lines.append("")
    for title, d in (("مقارنة", res["compare"]), ("بوّابة", res["gate"])):
        for k, p in d.items():
            lines.append(f"- {title} {k}: Δاتّهام {p['fa_delta_pts']:+} نقطة {p['fa_delta_cluster95']} "
                         f"(McNemar {p['fa_mcnemar']['a_only']}↔{p['fa_mcnemar']['b_only']} p={p['fa_mcnemar']['p']}) · "
                         f"Δكشف {p['det_delta_words']:+} كلمة {p['det_delta_cluster95']} "
                         f"(McNemar {p['det_mcnemar']['a_only']}↔{p['det_mcnemar']['b_only']} p={p['det_mcnemar']['p']}) · "
                         f"عدمُ دونيّة: {'✅' if p['non_inferior'] else '❌'}")
    md = "\n".join(lines)
    print(md)
    if x.out:
        os.makedirs(os.path.dirname(os.path.abspath(x.out)), exist_ok=True)
        json.dump(res, open(x.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if x.md:
        open(x.md, "w", encoding="utf-8").write(md + "\n")
    return 0 if ok else 1


def selftest(x) -> int:
    """حساباتٌ معروفة، ثم المسطرةُ على الذهب، ثم عدمُ الدونيّة أمام خطّ الأساس المودَع."""
    assert wilson(0, 0) == [0.0, 0.0]
    assert wilson(5, 10) == [23.66, 76.34], wilson(5, 10)
    assert mcnemar_p(0, 0) == 1.0 and abs(mcnemar_p(17, 3) - 0.002577) < 1e-5, mcnemar_p(17, 3)
    per = {"a": [["SUBSTITUTED", "MISSED", "CORRECT"]], "b": [["CORRECT", "UNCERTAIN", "SUBSTITUTED"]]}
    assert arm_accusations(per, ["a", "b"], "veto") == [[False, True, False]]
    assert arm_accusations(per, ["a", "b"], "and") == [[False, False, False]]
    assert arm_accusations(per, ["a", "b"], "or") == [[True, True, True]]
    toy = [{"key": "k", "rec": "r", "kind": "سالب", "audio_offset": 1, "n_ref": 1, "labels": "0", "ref_text": "x", "hyp": {"a": "x"}},
           {"key": "k2", "rec": "r", "kind": "سالب", "audio_offset": 0, "n_ref": 2, "labels": "0", "ref_text": "x", "hyp": {"a": "x"}},
           {"key": "k3", "rec": "r", "kind": "سالب", "audio_offset": 0, "n_ref": 1, "labels": "1", "ref_text": "x", "hyp": {"a": "x"}},
           {"key": "k4", "rec": "r", "kind": "موجب", "audio_offset": 0, "n_ref": 2, "labels": "10", "ref_text": "x y", "hyp": {"a": "x"}},
           {"key": "k5", "rec": "r", "kind": "موجب", "audio_offset": None, "n_ref": 1, "labels": "1", "ref_text": "x", "hyp": {"a": "x"}},
           {"key": "k6", "rec": "r", "kind": "سالب", "audio_offset": 0, "n_ref": 1, "labels": "0", "ref_text": "x", "hyp": {}}]
    kept, why = apply_ruler(toy, {"a"})
    assert [r["key"] for r in kept] == ["k4"] and why == {"audio_offset_nonzero_or_unknown": 2, "len_mismatch": 1,
                                                          "kind_contradicts_labels": 1, "missing_witness": 1}, why
    # الجارةُ السليمةُ في التسجيل الموجب لا تُعدّ اتّهاماً كاذباً
    assert counts(kept, [[True, True]]) == (0, 0, 1, 1)
    # الشكُّ: غيرُ متّهَمةٍ وحكمُ الشاهد الأوّل UNCERTAIN — والمتّهَمةُ لا تُعدّ شكّاً ولو شكّ فيها الثاني.
    per_u = {"a": [["UNCERTAIN", "SUBSTITUTED", "CORRECT"]], "b": [["CORRECT", "UNCERTAIN", "UNCERTAIN"]]}
    acc_u = arm_accusations(per_u, ["a", "b"], "veto")
    assert acc_u == [[False, True, False]] and arm_uncertain(per_u, ["a", "b"], acc_u) == [[True, False, False]]
    # الكشفُ بوسم الصفّ: كلُّ كلمةٍ خاطئةٍ تُنسب إلى وسوم صفّها، والسالبُ خارجٌ.
    tr = [{"kind": "موجب", "labels": "110", "error_tags": ["Tajweed", "Letters"]},
          {"kind": "موجب", "labels": "01", "error_tags": ["Letters"]},
          {"kind": "سالب", "labels": "00", "error_tags": []}]
    assert by_tag(tr, [[True, False, True], [False, True], [True, True]]) == {
        "Letters+Tajweed": {"det": 1, "marked": 2, "det_pct": 50.0}, "Letters": {"det": 1, "marked": 1, "det_pct": 100.0}}
    bl = os.path.join(HERE, "learner_gate_baseline_v1.json")
    blj = json.load(open(bl, encoding="utf-8"))
    # ⛔ خطُّ أساسٍ بإعدادٍ غيرِ إعداد الشوط يوقف الأداة (‏لا مقارنةَ صامتةً بين إعدادَين).
    other = "--no-engine-cfg" if blj.get("cfg", "gate_mirror") == "engine" else "--engine-cfg"
    sys.argv = [sys.argv[0], "--baseline", bl, "--boot", "50", "--no-leak", other, "--arms", "tiny"]
    try:
        main()
        raise AssertionError("خطُّ أساسٍ بإعدادٍ آخر مرّ صامتاً")
    except SystemExit as e:
        assert "خطُّ الأساس بإعداد" in str(e), e
    sys.argv = [sys.argv[0], "--baseline", bl, "--boot", "500", "--no-leak", "--arms", *blj["arms"]]
    rc = main()
    print("selftest: حساباتٌ معروفة ✅ · المسطرة ✅ · الشكّ والوسم ✅ · حارسُ الإعداد ✅ · خطُّ الأساس", "✅" if rc == 0 else "❌")
    return rc


if __name__ == "__main__":
    sys.exit(main())
