# -*- coding: utf-8 -*-
"""محاذاة مقاطع VAD بنص الرواية (Needleman-Wunsch نطاقي) واشتقاق حدود الآي.

المرجع نص الرواية نفسها (rasm-aware) لا نص حفص — شرط D-025.
الحد يقع على حدود مقاطع الصمت؛ المقطع الممتد على آيتين يُقسم نسبياً بالكلمات.
"""
import numpy as np

from common import norm

GAP = -1.0
BAND = 250


def _sim(a, b):
    if a == b:
        return 2.0
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return 1.0 if common >= max(2, min(len(a), len(b)) - 2) else -0.8


def nw_align(hyp, ref):
    """أزواج (hyp_i, ref_j) للممر الأمثل في نطاق قطري."""
    n, m = len(hyp), len(ref)
    NEG = -1e9
    score = np.full((n + 1, m + 1), NEG, dtype=np.float32)
    ptr = np.zeros((n + 1, m + 1), dtype=np.int8)  # 1=diag 2=up 3=left
    score[0][0] = 0
    for i in range(n + 1):
        lo = max(0, int(i * m / max(n, 1)) - BAND)
        hi = min(m, int(i * m / max(n, 1)) + BAND)
        for j in range(lo, hi + 1):
            if i == 0 and j == 0:
                continue
            best, p = NEG, 0
            if i > 0 and j > 0 and score[i - 1][j - 1] > NEG / 2:
                v = score[i - 1][j - 1] + _sim(hyp[i - 1], ref[j - 1])
                if v > best:
                    best, p = v, 1
            if i > 0 and score[i - 1][j] > NEG / 2:
                v = score[i - 1][j] + GAP
                if v > best:
                    best, p = v, 2
            if j > 0 and score[i][j - 1] > NEG / 2:
                v = score[i][j - 1] + GAP
                if v > best:
                    best, p = v, 3
            score[i][j], ptr[i][j] = best, p
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        p = ptr[i][j]
        if p == 1:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif p == 2:
            i -= 1
        elif p == 3:
            j -= 1
        else:
            break
    pairs.reverse()
    return pairs


PREFIX_ISTIADHA = "اعوذ بالله من الشيطان الرجيم".split()
PREFIX_BASMALA = "بسم الله الرحمن الرحيم".split()


def derive_boundaries(segments, ref_ayahs, with_basmala_prefix=False):
    """حدود الآي من مقاطع مفرَّغة. segments: [{"s","e","words"}].

    with_basmala_prefix: للسور غير الفاتحة/التوبة — تُدرج الاستعاذة والبسملة
    آيتين افتراضيتين تمتصان كلماتهما في المحاذاة ثم تُستبعدان من المخرج
    (إصلاح 2026-09-01: 14 سورة التُهمت بسملتها في الآية الأولى — كشف QA السماعي).
    يعيد قائمة {ayahIdx, startMs, endMs, conf, snapped, matched, total}.
    """
    ref_words, owner = [], []
    n_virtual = 0
    if with_basmala_prefix:
        for w in PREFIX_ISTIADHA:
            ref_words.append(w)
            owner.append(-2)
        if with_basmala_prefix != "istiadha_only":
            for w in PREFIX_BASMALA:
                ref_words.append(w)
                owner.append(-1)
        n_virtual = 2
    for ai, t in enumerate(ref_ayahs):
        for w in norm(t).split():
            ref_words.append(w)
            owner.append(ai)
    hyp_words, hyp_seg, hyp_pos = [], [], []
    for si, seg in enumerate(segments):
        for wi, w in enumerate(seg["words"]):
            hyp_words.append(w)
            hyp_seg.append(si)
            hyp_pos.append(wi)
    pairs = nw_align(hyp_words, ref_words)

    counts = [len(norm(t).split()) for t in ref_ayahs]
    n_ayahs = len(ref_ayahs)
    matched = {ai: 0 for ai in range(n_ayahs)}
    exact = {ai: 0 for ai in range(n_ayahs)}
    # زمن تقديري لكل كلمة hyp: توزيع خطي داخل مقطعها
    def word_time(hi):
        seg = segments[hyp_seg[hi]]
        k = max(len(seg["words"]), 1)
        frac0 = hyp_pos[hi] / k
        frac1 = (hyp_pos[hi] + 1) / k
        return (seg["s"] + (seg["e"] - seg["s"]) * frac0,
                seg["s"] + (seg["e"] - seg["s"]) * frac1)

    spans = {ai: [None, None] for ai in range(n_ayahs)}  # [startMs, endMs]
    seg_owners = {}  # si -> set(ayahs)
    for hi, rj in pairs:
        ai = owner[rj]
        seg_owners.setdefault(hyp_seg[hi], set()).add(ai)  # يشمل السالبة: تمنع «نقاء» مقطع البسملة
        if ai < 0:  # استعاذة/بسملة افتراضية — تمتص كلماتها ولا تدخل أي آية
            continue
        matched[ai] += 1
        if hyp_words[hi] == ref_words[rj]:
            exact[ai] += 1
        t0, t1 = word_time(hi)
        if spans[ai][0] is None or t0 < spans[ai][0]:
            spans[ai][0] = t0
        if spans[ai][1] is None or t1 > spans[ai][1]:
            spans[ai][1] = t1

    out = []
    for ai in range(n_ayahs):
        s0, e0 = spans[ai]
        if s0 is None:
            out.append({"ayahIdx": ai, "startMs": None, "endMs": None, "conf": 0.0,
                        "snapped": False, "matched": 0, "total": counts[ai]})
            continue
        # وسّع إلى حدود المقطع متى كان المقطع خالصاً لهذه الآية
        for si, owners in seg_owners.items():
            if owners == {ai}:
                s0 = min(s0, segments[si]["s"])
                e0 = max(e0, segments[si]["e"])
        cov = matched[ai] / max(counts[ai], 1)
        acc = exact[ai] / max(matched[ai], 1)
        # حد لا يقع على حافة مقطع صمت (±80م.ث) = مشتق من توزيع خطي داخل الكلام ⇒ أدنى ثقة
        seg_edges = [seg["s"] for seg in segments] + [seg["e"] for seg in segments]
        snapped = any(abs(s0 - t) <= 80 for t in seg_edges)
        conf = round(min(1.0, (0.6 * cov + 0.4 * acc) * (1.0 if snapped else 0.6)), 3)
        out.append({"ayahIdx": ai, "startMs": int(s0), "endMs": int(e0),
                    "conf": conf, "snapped": snapped,
                    "matched": matched[ai], "total": counts[ai]})
    # لصق الحدود المتجاورة: نهاية الآية = بداية التالية عند فاصل صغير
    for k in range(len(out) - 1):
        a, b = out[k], out[k + 1]
        if a["endMs"] is not None and b["startMs"] is not None:
            gap = b["startMs"] - a["endMs"]
            if -1500 < gap <= 2500:
                mid = (a["endMs"] + b["startMs"]) // 2
                a["endMs"] = b["startMs"] = mid
    return out
