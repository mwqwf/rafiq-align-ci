#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""آياتٌ غائبةٌ مسمّاةٌ في وضع السماع (`ctc_heard_map --absent-ayahs`) — منطقٌ محضٌ بلا نموذجٍ ولا صوت.

⭐ **سببُه مقيس (nasser_almajed · س6 · 2026-11-07):** المصدرُ البديلُ المسجَّل (aa11a56b) تسجيلٌ ينقصه 74–94
(‏بين ≈1312.5ث و1321.1ث تُسمع بسملةٌ ثمّ تبدأ 6:95)، وخريطتا السماع (العامّةُ ونموذجُ التلاوة) تسمعان 1–73 و95–165
رتيبةً وتجدان 74–94 غائبةً. ومحاذاةُ السورة كاملةً تنجرف (‏mode=full) وmode=window يردّه حارسُه وmode=heard
يشترط حدوداً لكلّ آية. فهذا الباب يبني **مداخلَ المسموعةِ وحدها** من المراسي المتّفقة بين الخريطتين،
ويترك المسمّاةَ غائبةً بلا مدخل (‏لا عصرَ ولا استيفاءَ بين جارتَيها)، ويُنتج دليلَ الغياب لـ`drop_ayahs`.

⛔ **ما لا يفعله ولا يُرخيه:**
 - كلُّ آيةٍ **غيرِ مسمّاةٍ** يجب أن تكون مسموعةً في الخريطتين معاً (‏مِرساةٌ عامّةٌ جودتُها ≥ ANCHOR_Q
   أو أداءٌ منفردٌ بجودة ≥ SOLO_MIN) ومتّفقةً بين الخريطتين بفرقِ بدءٍ ≤ AGREE_MS — وإلا تُردّ السورةُ كلُّها
   (‏لا «غائبَ غيرَ مسمّى» يمرّ صامتاً).
 - كلُّ آيةٍ **مسمّاةٍ** يجب ألّا يكون لها في أيٍّ من الخريطتين مِرساةٌ ولا أداءٌ منفرد، ولا مطابقةٌ قويّةٌ
   (‏≥ ABSENT_BEST_MAX) في أيّ موضعٍ من الملفّ — وإلا فهي مسموعةٌ لا غائبة.
 - لا الأولى ولا الأخيرة، ولا أكثرُ من ربع السورة (‏بابا الصدر والذيل / الإسقاطُ الكامل — كحارس `drop_ayahs`).
 - مدخلٌ لا يمتدّ ليغطّيَ فجوةَ الغائبات: نهايةُ المسموعة قبل الفجوة ≤ نهايةِ مِرساتها المتّفقةِ + TAIL_MS.
 - بدءُ كلّ مسموعةٍ يسنده بدءٌ في إحدى الخريطتين بفرقٍ ≤ SUPPORT_MS.
⚖️ والحكمُ الحاسمُ للبوّابة الصوتيّة (مطالع · سماع · إحصاءٌ شامل · أربعةُ ملوح · عتبة 5%) ولا يُعفى منها شيء.

    python tools/alignment_v3/heard_absent.py expand "6:74-94" --surah 6   # ⇒ 74,75,…,94
"""
from __future__ import annotations

import argparse
import re
import sys

ANCHOR_Q = 0.3            # أدنى جودةٍ لمِرساةٍ عامّة (‏كما في ctc_heard_map.ANCHOR_Q)
SOLO_MIN = 0.5            # أدنى جودةٍ لأداءٍ منفردٍ يقوم مقامَ المِرساة العامّة
AGREE_MS = 1000           # أقصى فرقِ بدءٍ بين الخريطتين لتُعدّ المِرساةُ متّفقةً
SUPPORT_MS = 1500         # أقصى بُعدٍ لبدء المدخل النهائيّ عن أقرب بدءٍ مقيسٍ في أيٍّ من الخريطتين
ABSENT_BEST_MAX = 0.70    # فوقه مطابقةٌ قويّةٌ لنصّ الآية في الملفّ = مسموعةٌ (‏STRONG في ctc_heard_map)
TAIL_MS = 800             # ذيلُ آخر مسموعةٍ قبل الفجوة بعد نهاية مِرساتها (‏كما في ctc_heard_map.TAIL_MS)

COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99,
          128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60,
          34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38,
          29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18,
          12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29,
          19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8,
          11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]


class HeardAbsentError(ValueError):
    """ردٌّ بسببٍ مقيس — لا يُخفَّف ولا يُلتفّ عليه."""


# ───────────────────────── الصيغة ─────────────────────────
def expand_spec(spec: str, surah: int) -> list:
    """«6:74-94» أو «6:74,6:80» أو «74-94» ⇒ [74،…،94] مرتّبةً بلا تكرار؛ وسورةٌ غيرُ `surah` تُردّ."""
    out: list = []
    for item in [x for x in re.split(r"[,\s،]+", str(spec or "")) if x]:
        m = re.fullmatch(r"(?:(\d{1,3}):)?(\d{1,3})(?:-(?:(\d{1,3}):)?(\d{1,3}))?", item)
        if not m:
            raise HeardAbsentError(f"صيغةٌ غيرُ صالحة {item!r} (‏سورة:آية أو سورة:من-إلى)")
        s1, a, s2, b = m.groups()
        for s_ in (s1, s2):
            if s_ is not None and int(s_) != int(surah):
                raise HeardAbsentError(f"الغائباتُ لسورةٍ واحدةٍ ({surah}) لا {item!r}")
        lo, hi = int(a), int(b) if b else int(a)
        if hi < lo:
            raise HeardAbsentError(f"مدىً مقلوب {item!r}")
        for v in range(lo, hi + 1):
            if v in out:
                raise HeardAbsentError(f"آيةٌ مكرّرة {surah}:{v}")
            out.append(v)
    if not out:
        raise HeardAbsentError("قائمةُ الغائبات فارغة")
    return sorted(out)


def check_named(n: int, absent: list) -> None:
    """حرّاسُ التسمية وحدها (‏كحارس `drop_ayahs`): لا الأولى ولا الأخيرة · ≤ ربع السورة · داخل المصحف."""
    if not absent or len(set(absent)) != len(absent):
        raise HeardAbsentError("قائمةُ الغائبات فارغةٌ أو مكرّرة")
    if min(absent) < 1 or max(absent) > n:
        raise HeardAbsentError(f"آيةٌ خارج السورة (1..{n}): {sorted(absent)}")
    if min(absent) < 2 or max(absent) > n - 1:
        raise HeardAbsentError(f"لا تُحجب أولى السورة ولا آخرتها (2..{n - 1}) — ذاك بابُ الصدر/الذيل")
    if len(absent) * 4 > n:
        raise HeardAbsentError(f"المحجوب {len(absent)} يتجاوز ربع آيات السورة ({n}) — الإسقاطُ الكامل")


# ───────────────────────── المرشّحات والاتّفاق ─────────────────────────
def candidates(h: dict | None) -> list:
    """[(نوع، بدء، نهاية، جودة)] لآيةٍ في خريطةٍ واحدة: مِرساةٌ عامّةٌ جودتُها ≥ ANCHOR_Q ثمّ أداءٌ منفردٌ ≥ SOLO_MIN."""
    h = h or {}
    out = []
    a, q = h.get("anchorMs"), h.get("anchorQuality")
    if a and q is not None and float(q) >= ANCHOR_Q:
        out.append(("global", int(a[0]), int(a[1]), float(q)))
    m, sc = h.get("heardMs"), h.get("score")
    if m and sc is not None and float(sc) >= SOLO_MIN:
        out.append(("solo", int(m[0]), int(m[1]), float(sc)))
    return out


_PAIR_ORDER = (("global", "global"), ("solo", "solo"), ("global", "solo"), ("solo", "global"))


def agree(cg: list, cr: list):
    """أفضلُ زوجٍ (‏من العامّة ثمّ من الأخرى) يتّفق بدءاه ≤ AGREE_MS ⇒ (بدء، نهاية، النوع) أو None.
    البدءُ من العامّة (‏خريطةِ البناء) والنهايةُ الأدنى من النهايتين (‏فلا تُمدّ المِرساةُ إلى زيادةٍ في إحداهما)."""
    for kg, kr in _PAIR_ORDER:
        best = None
        for a in (c for c in cg if c[0] == kg):
            for b in (c for c in cr if c[0] == kr):
                d = abs(a[1] - b[1])
                if d <= AGREE_MS and (best is None or d < best[0]):
                    best = (d, a, b)
        if best:
            _d, a, b = best
            return a[1], min(a[2], b[2]), f"{kg}/{kr}"
    return None


def agreed_anchors(gm: dict, rm: dict, n: int, absent: list, witnessed=None):
    """⇒ (anchor_ms[n]، ملاحظات). مِرساةٌ (بدء، نهاية) لكلّ مسموعةٍ اتّفقت عليها الخريطتان، و`None` للمسمّاة غائبةً.
    ‏`gm`/`rm` = `heardMap` للعامّة ولنموذج التلاوة. ويُرفع HeardAbsentError عند أيّ ردٍّ مقيس (‏تُجمع كلُّها في رسالةٍ واحدة).
    الآيةُ التي اختلف عليها المِرساتان بأكثر من AGREE_MS (‏مع وجود مرشّحاتٍ في الخريطتين) تبقى بلا مِرساةٍ
    ويُسجَّل اسمُها في `disputed` — يحسمها حدُّ المحاذاة بين جارتين متّفقتين ثمّ حارسُ الدعم `check_support`."""
    # ⭐ `witnessed` (ctc-absent-witnessed-1 · اختياريّ): مجموعةُ آياتٍ مسمّاةٍ غائبةٍ أثبت غيابَها `witnessed_exemptions` بشروطها كلِّها —
    #    يُستثنى بها وحدَها ردُّ «مسمّاةٌ غائبةٌ لكنّها مسموعة»؛ وفحصُ المطابقة القويّة في الملفّ كلِّه يبقى كما هو. بلاها السلوكُ القديمُ حرفاً.
    check_named(n, absent)
    ab = set(absent)
    wit_ok = set(witnessed or ())
    if not wit_ok <= ab:
        raise HeardAbsentError(f"غيابٌ مشهودٌ لآياتٍ غيرِ مسمّاة: {sorted(wit_ok - ab)}")
    errors, disputed, kinds = [], [], {}
    out = [None] * n
    for k in range(1, n + 1):
        hg, hr = (gm or {}).get(str(k)), (rm or {}).get(str(k))
        cg, cr = candidates(hg), candidates(hr)
        if k in ab:
            for tag, c in (("العامّة", cg), ("نموذج التلاوة", cr)):
                if c and k not in wit_ok:
                    errors.append(f"الآية {k} مسمّاةٌ غائبةٌ لكنّها مسموعةٌ في خريطة {tag} ({c[0][0]} {c[0][1]}–{c[0][2]} جودة {c[0][3]})")
            for tag, h in (("العامّة", hg), ("نموذج التلاوة", hr)):
                strong = [o for o in ((h or {}).get("occurrences") or []) if o[2] >= ABSENT_BEST_MAX]
                if strong:
                    errors.append(f"الآية {k} مسمّاةٌ غائبةٌ وفي خريطة {tag} مطابقةٌ قويّةٌ {strong[0]}")
            continue
        if not cg and not cr:
            errors.append(f"الآية {k} غيرُ مسمّاةٍ غائبةً ولا مِرساةَ لها ولا أداءً منفرداً ≥ {SOLO_MIN} في الخريطتين — غائبٌ غيرُ مسمّى")
            continue
        if not cg or not cr:
            who = "العامّة" if not cg else "نموذج التلاوة"
            errors.append(f"الآية {k} مسموعةٌ في خريطةٍ واحدةٍ وبلا مِرساةٍ عامّةٍ ولا أداءٍ منفردٍ بجودة ≥ {SOLO_MIN} في خريطة {who}")
            continue
        got = agree(cg, cr)
        if got is None:
            disputed.append(k)
            continue
        out[k - 1] = (got[0], got[1])
        kinds[k] = got[2]
    if errors:
        raise HeardAbsentError("⛔ " + " | ".join(errors))
    return out, {"disputed": disputed, "kinds": kinds}


def witnessed_exemptions(surah: int, n: int, absent: list, gm: dict, rm: dict, wits: dict, meta: dict, want_sha: str,
                         ref_words=None):
    """⭐ (‏ctc-absent-witnessed-1 · قرار القائد 2026-11-10) ⇒ ({آية: دليل}، {آية: سببُ الرفض}) لكلّ آيةٍ مسمّاةٍ غائبةٍ **مسموعةٍ في إحدى الخريطتين**.
    يُحكم بـ`heard_gate.witnessed_absent_one` (‏الشروط ١–٥ كلُّها) على الخريطتين معاً؛ وما رُفض يبقى لردّ `agreed_anchors` القديم حرفاً.
    ‏`wits` {تشغيلة: شاهدٌ محمَّلٌ من مصدره} · `meta` = {sha256، fileRef} للملفّ · `want_sha` بصمتُه.
    المدّةُ المتوقَّعةُ من مدى المراسي العامّة المتّفق عليها لأقران السورة (‏الغائباتُ مستثناة)."""
    import sys as _sys
    from pathlib import Path
    ix = str(Path(__file__).resolve().parent.parent / "index_qa")
    if ix not in _sys.path:
        _sys.path.insert(0, ix)
    import heard_gate as HG                                          # noqa: PLC0415
    ref_words = ref_words or (lambda s_, a_: HG.disputed_ref_words("hafs", s_, a_))
    chars_of = lambda a_: sum(len(w) for w in ref_words(surah, a_))  # noqa: E731
    ab = set(absent)
    durs = {}
    for k in range(1, n + 1):
        g, r = (gm or {}).get(str(k)), (rm or {}).get(str(k))
        if k in ab:
            continue
        got = agree(candidates(g), candidates(r))
        if got:
            durs[k] = (got[0], got[1])
    src = {str(run): HG.disputed_src_rec(w) for run, w in sorted((wits or {}).items())}
    ok, refused = {}, {}
    for k in absent:
        g, r = (gm or {}).get(str(k)), (rm or {}).get(str(k))
        if not (candidates(g) or candidates(r)):
            continue                                                 # لا مسموعةَ في الخريطتين: لا استثناءَ مطلوب
        why, det = HG.witnessed_absent_one(surah, k, n, g, r, src, src, ref_words, meta, want_sha,
                                           HG.witnessed_expected_ms(durs, k, chars_of))
        if why:
            refused[k] = why
        else:
            ok[k] = det
    return ok, refused


def check_support(entries: list, gm: dict, rm: dict, absent: list) -> None:
    """بدءُ كلّ مسموعةٍ في المخرَج يُسنده بدءٌ مقيسٌ (‏مِرساةٌ أو أداءٌ منفرد) في إحدى الخريطتين ≤ SUPPORT_MS."""
    ab = set(absent)
    bad = []
    for e in entries:
        k = int(e["ayahIdx"]) + 1
        if k in ab or e.get("startMs") is None:
            continue
        starts = [c[1] for h in ((gm or {}).get(str(k)), (rm or {}).get(str(k))) for c in candidates(h)]
        if not starts or min(abs(e["startMs"] - s) for s in starts) > SUPPORT_MS:
            bad.append(f"{k} (بدءٌ {e['startMs']} والمقيسُ {sorted(set(starts))[:4]})")
    if bad:
        raise HeardAbsentError("⛔ بدءٌ لا يسنده قياسٌ في أيٍّ من الخريطتين ≤ "
                               f"{SUPPORT_MS}م.ث: " + " · ".join(bad[:8]))


# ───────────────────────── النوافذ والنهايات ─────────────────────────
def plan_groups(anchor_ms: list, n: int, absent_idx: set, plan_windows) -> list:
    """نوافذُ المحاذاة لكلّ مقطعٍ متّصلٍ من المسموعات **لا تعبر غائبةً**؛ `plan_windows` = دالةُ ctc_heard_map."""
    wins, i = [], 0
    while i < n:
        if i in absent_idx:
            i += 1
            continue
        j = i
        while j + 1 < n and (j + 1) not in absent_idx:
            j += 1
        for a, b in plan_windows(anchor_ms[i:j + 1], j - i + 1):
            wins.append((i + a, i + b))
        i = j + 1
    return wins


def end_before_gap(k: int, start: int, nxt, anchor_ms: list) -> int:
    """نهايةُ آخر مسموعةٍ قبل فجوة غائبات (‏k صفريّ): نهايةُ مِرساتها المتّفقة + TAIL_MS مسقوفةً ببدء التالية المسموعة —
    ⛔ لا تمتدّ ليغطّيَ الفجوة."""
    a = anchor_ms[k]
    if a is None:
        raise HeardAbsentError(f"الآية {k + 1} قبل فجوة الغائبات بلا مِرساةٍ متّفقة — لا نهايةَ مقيسةً لها")
    end = int(a[1]) + TAIL_MS
    if nxt is not None:
        end = min(end, int(nxt))
    if end <= start:
        raise HeardAbsentError(f"الآية {k + 1}: نهايتُها {end} ≤ بدئها {start} قبل فجوة الغائبات")
    return end


def validate_built(entries: list, anchor_ms: list, absent: list, n: int) -> None:
    """الحارسُ الأخير على المخرَج: المسمّاةُ بلا حدود · كلُّ مسموعةٍ بحدودٍ صاعدة · لا امتدادَ يغطّي فجوةً."""
    ab = set(absent)
    if len(entries) != n:
        raise HeardAbsentError(f"المداخل {len(entries)} والرواية {n}")
    prev = -1
    for e in entries:
        k = int(e["ayahIdx"]) + 1
        st, en = e.get("startMs"), e.get("endMs")
        if k in ab:
            if st is not None or en is not None:
                raise HeardAbsentError(f"الآية {k} مسمّاةٌ غائبةٌ ولها حدود {st}→{en}")
            continue
        if st is None or en is None:
            raise HeardAbsentError(f"الآية {k} مسموعةٌ بلا حدود")
        if not (0 <= st < en) or st < prev:
            raise HeardAbsentError(f"الآية {k} حدودٌ غيرُ صاعدة {st}→{en} بعد {prev}")
        prev = en
        if (k + 1) in ab:
            a = anchor_ms[k - 1]
            if a is None or en > int(a[1]) + TAIL_MS:
                raise HeardAbsentError(
                    f"الآية {k} تمتدّ إلى {en} لتغطّي فجوة الغائبات والمِرساةُ تنتهي {None if a is None else a[1]} (+{TAIL_MS})")


def clusters(absent: list) -> list:
    """عناقيدُ الغائبات المتّصلة ⇒ [(lo، hi، [غائباتها])] حيث lo/hi جارتان مسموعتان."""
    out, cur = [], [absent[0]]
    for a in absent[1:]:
        if a == cur[-1] + 1:
            cur.append(a)
        else:
            out.append(cur)
            cur = [a]
    out.append(cur)
    return [(g[0] - 1, g[-1] + 1, g) for g in out]


# ───────────────────────── الدليل ─────────────────────────
def build_evidence(surah: int, absent: list, ents: dict, t_of, rate: float, align, scan_g: dict, scan_r: dict) -> dict:
    """دليلُ الغياب لكلّ آيةٍ مسمّاة ⇒ {«س:آ»: {method: ctc_window، detail}} — وإلا HeardAbsentError.

    ثلاثةُ شواهد معاً: ① نافذةُ الجارتين المسموعتين بنصوص الغائبات (‏`ctc_gapsplit.judge_absent`: ثقةُ CTC
    ≥0.45 · مدّةٌ بين 0.5× و2× · انكماشُ الجارة) تردّها الحرّاس ② أفضلُ مطابقةٍ لنصّ الآية في الملفّ كلِّه
    تحت ABSENT_BEST_MAX في الخريطتين ③ لا مِرساةَ ولا أداءَ منفرداً لها في أيٍّ منهما (‏تحقّقه agreed_anchors).
    ‏`ents`: {آية: {startMs, endMs}} للجارات المسموعة؛ `align(ws, we, texts)` يُحقن."""
    import ctc_gapsplit as G
    evidence = {}
    exp_of = lambda k: G.chars(t_of(k)) * rate                          # noqa: E731
    for lo, hi, g in clusters(absent):
        if lo not in ents or hi not in ents:
            raise HeardAbsentError(f"جارةُ النافذة {lo}/{hi} بلا حدود — لا دليلَ نافذة")
        ks_all = list(range(lo, hi + 1))
        ws, we = int(ents[lo]["startMs"]), int(ents[hi]["endMs"])
        segs = align(ws, we, [G.norm(t_of(k)) for k in ks_all])
        ok, ev, why = G.judge_absent(surah, ws, we, ks_all, g, segs, ents, exp_of)
        if not ok:
            raise HeardAbsentError(f"⛔ {why}")
        for key, rec in ev.items():
            evidence[key] = rec
    out = {}
    for k in absent:
        sg, sr = (scan_g or {}).get(str(k)), (scan_r or {}).get(str(k))
        if not sg or not sr:
            raise HeardAbsentError(f"الآية {k}: لا مسحَ ملفٍّ كاملٍ في إحدى الخريطتين — لا دليلَ على الملفّ كلِّه")
        for tag, s in (("العامّة", sg), ("نموذج التلاوة", sr)):
            if float(s["bestScore"]) >= ABSENT_BEST_MAX:
                raise HeardAbsentError(f"⛔ الآية {k}: مطابقةٌ {s['bestScore']} عند {s['bestAtMs']}م.ث في خريطة {tag} "
                                       f"(≥ {ABSENT_BEST_MAX}) — مسموعةٌ لا غائبة")
        rec = evidence.get(f"{surah}:{k}")
        if rec is None:
            raise HeardAbsentError(f"الآية {k}: لم تُنتج نافذةُ الجارتين دليلاً")
        out[f"{surah}:{k}"] = {
            "method": "ctc_window",
            "detail": (rec["detail"] + " · وعلى الملفّ كلِّه: أفضلُ مطابقةٍ لنصّها "
                       f"{sg['bestScore']} عند {sg['bestAtMs']}م.ث (العامّة) و{sr['bestScore']} عند {sr['bestAtMs']}م.ث "
                       f"(نموذج التلاوة) وكلتاهما دون {ABSENT_BEST_MAX} · ولا مِرساةَ ولا أداءَ منفرداً لها في الخريطتين")}
    return out


def _main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("expand")
    ex.add_argument("spec")
    ex.add_argument("--surah", type=int, required=True)
    a = ap.parse_args()
    try:
        print(",".join(str(v) for v in expand_spec(a.spec, a.surah)))
    except HeardAbsentError as e:
        print(f"⛔ {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_main())
