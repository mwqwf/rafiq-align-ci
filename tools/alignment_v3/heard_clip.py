#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قصُّ نافذة كلّ آيةٍ على **أداءٍ مسموعٍ واحدٍ تامّ** — لقارئٍ يكرّر الآيات (‏maroush_qalun · قرار القائد 2026-11-09).

⭐ **السبب (مقيس):** مخرَجُ `ctc_heard_map` لقارئٍ يعيد الآيات تُبنى نوافذُه من مِرساةٍ إلى مِرساة، فتضمّ التكرارَ
وكلامَ التعليم؛ فرُدّت كلُّ سور maroush في `entry_window_census` بـ«زيادة · عددُ كلمات النافذة 203 فوق الحدّ 62» ونحوه
(‏47 سورةً من 47)، وجاءت المحاذاةُ الكاملةُ بـCTC (‏mode=full) أسوأَ فضغطت السورةَ في جزءٍ من الصوت.

## القاعدة (‏كما قرّر القائد)
1. **أداءٌ تامٌّ** = مقطعٌ داخل موضعٍ من خريطة السماع (‏تشابه ≥ `MIN_SIM`) يقرأ فيه Whisper float32 الآيةَ كاملةً:
   أوّلُ ثلاث كلماتٍ وآخرُ ثلاثٍ تطابقان نصَّ الرواية كلمةً بكلمة، وعددُ الكلمات بين الطرفين ضمن 0.7–1.3
   من كلمات الآية، وثقةُ الكلمات الطرفيّة ≥0.5 ومتوسّطُها ≥0.7؛ **ثمّ تثبته محاذاةُ CTC القسريّةُ** لنصّ الآية وحدها
   على نافذةٍ ضيّقةٍ حول مقطع Whisper: بدؤها ونهايتُها يوافقان بدءَ أوّل كلمةٍ ونهايةَ آخرها عند Whisper
   **بفرقٍ ≤ 300م.ث** (‏حدودُ مواضع الخريطة نفسُها فضفاضةٌ تضمّ التكرارَ فلا تصلح حدوداً).
   ⭐ **شاهدُ البدء (قرار القائد 2026-11-09 · الخيار الأوّل وحده):** تفريغُ المقطع الأوّل بنافذةٍ واسعةٍ يُلصق بدءَ أوّل
   كلمةٍ ببدء النافذة (‏قيسٌ: 1008م.ث = 1500 − 492 في 31:2). فيُعاد التفريغُ **بنافذةٍ تبدأ داخل الصمت الذي قبل الآية**
   (‏`onset_window`: صمتُ VAD ينتهي قرب بدء CTC، وبدءُ النافذة قبل أوّل الكلام بـ150م.ث)، فيبقى بدءُ **الكلمة الأولى نفسِها**
   هو المقيس، ويُقابَل ببدء CTC بفرق ≤300م.ث. ولا صمتَ قبل الآية ⇒ لا قياسَ ⇒ الآيةُ غيرُ محلولة. ⛔ لا يُقاس البدءُ على الكلمة الثانية.
   وقيدُ العطب الدائريّ: النافذةُ تُوضع من **صمتٍ صوتيّ** لا من بدء CTC مباشرة، واختبارُ التحوّر (‏`selftest`) يثبت أنّ
   إزاحةَ البدء ±400م.ث و±1ث على فهارس منشورةٍ سليمة تُردّ.
2. إن تعدّد الأداءُ التامّ فالمأخوذُ **آخرُه** (‏fixV)، بشرط أن يتّسق مع جارتيه: نهايتُه ≤ بدء تاليتها،
   والفجوةُ إلى بدء تاليتها ≤ `MAX_GAP_MS` (‏حارسٌ إضافيّ: لا تُقبل آيةٌ على بُعد دقائق من جارتها).
3. **ما لم يثبت له أداءٌ تامٌّ واحد لا يُقصّ تخميناً**: تُرجع الأداةُ سورتَه «غيرَ محلولة» بسببٍ مكتوب،
   فتبقى السورةُ محجوبةً معلَنةً كما هي في الأب (‏`splice_surah --skip-unresolved`) ولا تُرقّى.
4. **الدليلُ يُسجَّل لكلّ آية**: أيُّ أداءٍ اختير (‏k من n) وحدّاه وتشابهُه وبدءُ Whisper ونهايتُه وثقتُه،
   في `heardClip` بترويسة السورة، وتُنقل إلى ترويسة الفهرس (‏`inject_header`).

⛔ لا حارسَ يُخفَّف ولا عتبةَ تُخفَّض: القصُّ يُنتج مرشّحاً يمرّ بعدها بالبنية وبوّابة السماع
وإحصاء نوافذ المداخل والملوح كما هي. والتفريغُ مرشّحٌ للتوقيت وحده، ولا يُكتب منه نصٌّ في أيّ فهرس.

    python tools/alignment_v3/heard_clip.py clip --batch-dir D --surah 31 --url <mp3> --riwaya qalun
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "alignment"))

ENGINE = "heard-clip-1"
MIN_SIM = 0.7            # أدنى تشابهٍ لأداءٍ في الخريطة (‏= heard_gate.REPEAT_SIM)
TOL_MS = 300             # أقصى فرقٍ بين حدَّي الأداء وحدَّي Whisper (‏أمرُ القائد)
W_K = 3                  # كلماتُ الطرف المطابَقة كلمةً بكلمة
W_MIN_WORD_P = 0.5       # ثقةُ كلّ كلمةٍ طرفيّة (‏كما في pin_heard)
W_MEAN_WORD_P = 0.7
W_FUZZ_SIM = 0.8         # تشابهُ حروف الكلمات الطرفيّة (‏رسمُ Whisper حفصيٌّ والنصُّ قالونيّ: «ايه»/«ايت» «الكتاب»/«الكتب»)
W_LEN_LO, W_LEN_HI = 0.8, 1.2     # عددُ كلمات المقطع نسبةً إلى كلمات الآية (‏كالمسار المشابه في pin_heard)
PAD_MS = 1500            # هامشُ نافذة الشاهد حول الأداء
MAX_WINDOW_MS = 120_000  # حدُّ whisper_witness للنافذة الواحدة
MAX_GAP_MS = 30_000      # أقصى فجوةٍ بين نهاية أداءٍ وبدء أداء تاليتها
ONSET_BACK_MS = 600     # أبعدُ ما يسبق به انتهاءُ الصمتِ بدءَ CTC ليُعدّ «الصمتَ الذي قبل الآية»
ONSET_AHEAD_MS = 300     # وأبعدُ ما يلحقه به
LEAD_IN_MS = 150         # تبدأ نافذةُ شاهد البدء داخل الصمت قبل أوّل الكلام بهذا القدر
MAX_ROUNDS = 6           # جولاتُ الشاهد: كلُّ جولةٍ الأداءُ التالي الأقدمُ للآيات غير المحلولة


def performances(hmap, ayah):
    """أداءاتُ الآية في الخريطة بتشابه ≥ MIN_SIM مرتّبةً بالبدء بلا تكرار: [(بدء، نهاية، تشابه)]."""
    rec = (hmap.get("heardMap") or {}).get(str(ayah)) or {}
    seen, out = set(), []
    cand = [tuple(o[:3]) for o in rec.get("occurrences") or []]
    if rec.get("anchorMs") and rec.get("anchorQuality") is not None:
        cand.append((rec["anchorMs"][0], rec["anchorMs"][1], float(rec["anchorQuality"])))
    for s, e, q in cand:
        s, e, q = int(s), int(e), float(q)
        if q < MIN_SIM or not (0 <= s < e) or (s, e) in seen:
            continue
        seen.add((s, e))
        out.append((s, e, q))
    return sorted(out)


def norm_tokens(words, norm):
    """كلماتُ Whisper مطبَّعةً: [(رمز، بدء، نهاية، ثقة)]؛ الكلمةُ المتشظّية ترث زمنَها وثقتَها."""
    out = []
    for w in words or []:
        for t in norm(str(w.get("w", ""))).split():
            out.append((t, int(w["s"]), int(w.get("e", w["s"])), float(w["p"])))
    return out


def _sim(a, b):
    import difflib                                                          # noqa: PLC0415
    return difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()


def find_matches(words, ref, norm):
    """كلُّ مقطعٍ تامٍّ للآية في تفريغ Whisper: ([dict(ws, we, pmin, pmean)], سببُ آخر ردّ)."""
    n = len(ref)
    if n == 0:
        return [], "لا نصَّ مرجعيَّ للآية"
    toks = norm_tokens(words, norm)
    k = min(W_K, n)
    head, tail = ref[:k], ref[-k:]
    lo, hi = max(k, math.ceil(W_LEN_LO * n)), max(math.floor(W_LEN_HI * n), k)
    why = "أوّلُ كلماتِ الآية لا يطابق تفريغَ النافذة (الشاهد: %s | المرجع: %s)" % (
        " ".join(t[0] for t in toks[:6]), " ".join(head))
    out = []
    for i in range(len(toks) - k + 1):
        if _sim([t[0] for t in toks[i:i + k]], head) < W_FUZZ_SIM:
            continue
        ends = [j for j in range(i + k - 1, len(toks))
                if _sim([t[0] for t in toks[j - k + 1:j + 1]], tail) >= W_FUZZ_SIM and lo <= j - i + 1 <= hi]
        if not ends:
            why = "آخرُ كلماتِ الآية لا يطابق التفريغ أو عددُ كلماته خارج المدى [%d..%d]" % (lo, hi)
            continue
        j = min(ends, key=lambda e: abs((e - i + 1) - n))
        edge = toks[i:i + k] + toks[j - k + 1:j + 1]
        low = min(t[3] for t in edge)
        mean = sum(t[3] for t in edge) / len(edge)
        if low < W_MIN_WORD_P or mean < W_MEAN_WORD_P:
            why = f"ثقةُ الكلمات الطرفيّة دون العتبة (أدناها {low:.2f}، متوسّطُها {mean:.2f})"
            continue
        out.append({"ws": toks[i][1], "we": toks[j][2], "pmin": round(low, 3), "pmean": round(mean, 3)})
    return out, why


def confirm(match, ctc_bounds, check_start=True):
    """يؤكّد مقطعَ Whisper بمحاذاة CTC القسريّة: (دليل، None) أو (None، سبب). `ctc_bounds(lo, hi)` ⇒ (بدء، نهاية) أو None.

    في التفريغ الواسع لا يُقاس البدءُ (‏يلتصق ببدء النافذة)؛ يُقاس في نافذة شاهد البدء (`eval_start`). النهايةُ تُقاس هنا دائماً."""
    lo, hi = max(0, match["ws"] - PAD_MS), match["we"] + PAD_MS
    got = ctc_bounds(lo, hi)
    if not got:
        return None, "تعذّرت محاذاةُ CTC على النافذة الضيّقة"
    cs, ce = int(got[0]), int(got[1])
    ds, de = abs(cs - match["ws"]), abs(ce - match["we"])
    if de > TOL_MS or (check_start and ds > TOL_MS):
        return None, f"حدّا CTC ({cs}-{ce}) يبعدان عن حدّي Whisper ({match['ws']}-{match['we']}) بـ{ds}/{de}م.ث (>{TOL_MS})"
    return {**match, "cs": cs, "ce": ce, "ds": ds, "de": de}, None


def onset_window(sil, cs):
    """نافذةُ شاهد البدء: (lo, onset) — lo داخل صمتٍ ينتهي (‏بدءُ الكلام) في [cs−600، cs+300]؛ أو None.

    `sil`: [(بدء، نهاية)] م.ث من VAD. يُختار الصمتُ الأقربُ انتهاءً إلى cs؛ وlo = max(بدء الصمت، نهايته − 150)."""
    best = None
    for s_, e_ in sil or []:
        if cs - ONSET_BACK_MS <= e_ <= cs + ONSET_AHEAD_MS:
            if best is None or abs(e_ - cs) < abs(best[1] - cs):
                best = (int(s_), int(e_))
    if best is None:
        return None
    return max(best[0], best[1] - LEAD_IN_MS), best[1]


def eval_start(words, ref, cs, ce, norm):
    """يُقابل تفريغَ نافذة شاهد البدء بحدّي CTC: (دليل، None) أو (None، سبب). ⛔ أوّلُ كلمةٍ هي المقيسة."""
    ms, why = find_matches(words, ref, norm)
    if not ms:
        return None, why
    def d_end(m):
        return 0 if ce is None else abs(m["we"] - ce)          # ce=None: اختبارُ البدء وحدَه (selftest)
    ok = [m for m in ms if abs(m["ws"] - cs) <= TOL_MS and d_end(m) <= TOL_MS]
    if not ok:
        m = min(ms, key=lambda m: abs(m["ws"] - cs) + d_end(m))
        return None, (f"شاهدُ البدء: حدّا Whisper ({m['ws']}-{m['we']}) يبعدان عن حدّي CTC ({cs}-{ce}) "
                      f"بـ{abs(m['ws'] - cs)}/{d_end(m)}م.ث (>{TOL_MS})")
    m = min(ok, key=lambda m: abs(m["ws"] - cs) + d_end(m))
    return {**m, "ds": abs(m["ws"] - cs), "de": d_end(m)}, None


def select(verified, n_ayahs):
    """يختار لكلّ آيةٍ **آخرَ أداءٍ ثابتٍ** متّسقٍ مع جارتيه (‏من الأخيرة إلى الأولى).

    `verified`: {آية: [dict(s, e, sim, k, n, ws, we, …)]}. يُرجع ({آية: dict}، [آياتٌ بلا اختيار])."""
    chosen, missing = {}, []
    nxt = None
    for a in range(n_ayahs, 0, -1):
        pick = None
        for v in sorted(verified.get(a, []), key=lambda v: v["s"], reverse=True):
            if nxt is not None:
                # الحدُّ الأعلى لنهاية الأداء بدءُ تاليته (‏مع سماح الشاهد TOL_MS لتماسّ الحدّين)
                if v["e"] > nxt["s"] + 0:
                    continue
                if nxt["s"] - v["e"] > MAX_GAP_MS:
                    continue
            pick = v
            break
        if pick is None:
            missing.append(a)
            nxt = None          # الغيابُ يقطع السلسلة: لا قيدَ على السابقة من غائبة
        else:
            chosen[a] = pick
            nxt = pick
    return chosen, sorted(missing)


def next_windows(hmap, n_ayahs, verified, tried, unresolved):
    """نوافذُ الجولة التالية للشاهد: لكلّ آيةٍ غير محلولةٍ أحدثُ أداءٍ لم يُجرَّب. {a*1000+k: (بدء، نهاية)} + خريطةُ الأداءات."""
    wins, owners = {}, {}
    for a in unresolved:
        perfs = performances(hmap, a)
        for idx in range(len(perfs) - 1, -1, -1):
            if idx in tried.setdefault(a, set()):
                continue
            tried[a].add(idx)
            s, e, q = perfs[idx]
            hi = e + PAD_MS
            lo = max(0, s - PAD_MS, hi - MAX_WINDOW_MS + 4000)     # أخيرُ الموضع: فيه الأداءُ الأخير
            key = a * 1000 + (idx + 1)
            wins[key] = (lo, hi)
            owners[key] = (a, idx + 1, len(perfs), (s, e, q))
            break
    return wins, owners


def clip_surah(hmap, ref_words, n_ayahs, witness_runner, ctc_runner, norm, sil):
    """يقصّ سورةً واحدة. `witness_runner(wins)` ⇒ {مفتاح: {"words": [...]}}؛ و`ctc_runner(lo, hi, ayah)` ⇒ (بدء، نهاية) أو None؛
    و`sil` صمتُ VAD [(بدء، نهاية)] م.ث.

    لكلّ مقطعٍ تامٍّ عند Whisper (نافذةٌ واسعة): (1) تأكيدُ CTC القسريّ ونهايتُه تطابق نهايةَ Whisper ≤300م.ث،
    (2) شاهدُ البدء بنافذةٍ داخل الصمت قبل الآية (‏`onset_window`) وبدءُ أوّل كلمةٍ يطابق بدءَ CTC ≤300م.ث.
    يُرجع dict: ok، entries (‏صيغة batch_run)، evidence، unresolved {آية: سبب}، rounds."""
    verified, tried, reasons = {}, {}, {}
    chosen, missing = {}, list(range(1, n_ayahs + 1))
    rounds = 0
    for rounds in range(1, MAX_ROUNDS + 1):
        wins, owners = next_windows(hmap, n_ayahs, verified, tried, missing)
        if not wins:
            break
        got = witness_runner(wins)
        cands = []                                   # (آية، k، n، perf، مقطع Whisper، cs، ce)
        for key, (a, k, n, perf) in owners.items():
            rec = got.get(str(key)) or got.get(key)
            if not rec:
                reasons[a] = "لا تفريغَ للنافذة في الشاهد"
                continue
            matches, why = find_matches(rec.get("words"), ref_words(a), norm)
            if not matches:
                reasons[a] = f"الموضع {k}/{n} [{perf[0]}-{perf[1]}]: {why}"
                continue
            for m in matches:
                ev, why2 = confirm(m, lambda lo, hi, _a=a: ctc_runner(lo, hi, _a), check_start=False)
                if ev is None:
                    reasons[a] = f"الموضع {k}/{n} [{perf[0]}-{perf[1]}]: {why2}"
                    continue
                cands.append((a, k, n, perf, m, ev["cs"], ev["ce"]))
        # شاهدُ البدء: نافذةٌ داخل الصمت قبل الآية، تفريغٌ ثانٍ
        bwins, bown = {}, {}
        for i, (a, k, n, perf, m, cs, ce) in enumerate(cands):
            ow = onset_window(sil, cs)
            if ow is None:
                reasons[a] = f"الموضع {k}/{n}: لا صمتَ قبل بدء CTC {cs} (‏±{ONSET_BACK_MS}/{ONSET_AHEAD_MS}م.ث) فلا يُقاس بدءُ أوّل كلمة"
                continue
            key = 10_000_000 + i
            bwins[key] = (ow[0], ce + PAD_MS)
            bown[key] = (a, k, n, perf, m, cs, ce, ow)
        got2 = witness_runner(bwins) if bwins else {}
        for key, (a, k, n, perf, m, cs, ce, ow) in bown.items():
            rec = got2.get(str(key)) or got2.get(key)
            if not rec:
                reasons[a] = "لا تفريغَ لنافذة شاهد البدء"
                continue
            ev, why = eval_start(rec.get("words"), ref_words(a), cs, ce, norm)
            if ev is None:
                reasons[a] = f"الموضع {k}/{n} [{perf[0]}-{perf[1]}]: {why}"
                continue
            s_, e_ = min(cs, ev["ws"]), max(ce, ev["we"])
            verified.setdefault(a, []).append({
                "s": s_, "e": e_, "sim": round(perf[2], 3), "k": k, "n": n, "ws": ev["ws"], "we": ev["we"],
                "pmin": ev["pmin"], "pmean": ev["pmean"], "cs": cs, "ce": ce, "ds": ev["ds"], "de": ev["de"],
                "onset": [ow[0], ow[1]]})
        chosen, missing = select(verified, n_ayahs)
        if not missing:
            break
    unresolved = {}
    for a in missing:
        if not performances(hmap, a):
            unresolved[a] = "لا موضعَ مسموعاً بتشابه ≥ %.2f في الخريطة" % MIN_SIM
        elif verified.get(a):
            unresolved[a] = "أداءاتُها الثابتةُ لا تتّسق مع جارتيها (ترتيبٌ أو فجوةٌ >%d ث)" % (MAX_GAP_MS // 1000)
        else:
            unresolved[a] = reasons.get(a, "لم يثبت أداءٌ تامٌّ بشاهد Whisper وCTC")
    if unresolved:
        return {"ok": False, "entries": [], "evidence": {}, "unresolved": unresolved, "rounds": rounds}
    entries, evidence = [], {}
    for a in sorted(chosen):
        v = chosen[a]
        entries.append({"ayahIdx": a - 1, "startMs": v["s"], "endMs": v["e"],
                        "conf": min(float(v["sim"]), 0.74), "snapped": False, "matched": 0,
                        "total": 0, "heard": True, "boundary": "clip"})
        evidence[str(a)] = {"performance": [v["s"], v["e"]], "occurrence": [v["k"], v["n"]], "sim": v["sim"],
                            "whisper": [v["ws"], v["we"]], "ctc": [v["cs"], v["ce"]], "diffMs": [v["ds"], v["de"]],
                            "onsetSilence": v["onset"], "pMin": v["pmin"], "pMean": v["pmean"]}
    for i in range(len(entries) - 1):
        if entries[i]["endMs"] > entries[i + 1]["startMs"]:
            entries[i]["endMs"] = entries[i + 1]["startMs"]       # تماسُّ الحدّين لا تداخل
    return {"ok": True, "entries": entries, "evidence": evidence, "unresolved": {}, "rounds": rounds}


def apply_to_surah_json(rec, result):
    """يُرجع ملفَّ السورة بعد القصّ: المداخلُ المقصوصة + `heardClip` (‏الدليل لكلّ آية) و`engine` كما هو."""
    out = dict(rec)
    out["entries"] = result["entries"]
    out["heardClip"] = {"engine": ENGINE, "tolMs": TOL_MS, "minSim": MIN_SIM, "rounds": result["rounds"],
                        "rule": "آخرُ أداءٍ تامٍّ مثبَتٍ بشاهد Whisper ضمن 300م.ث (‏fixV)",
                        "ayahs": result["evidence"]}
    return out


def inject_header(idx, surah_recs):
    """ينقل `heardClip` من ملفّات السور المأخوذة إلى ترويسة الفهرس: {«س:آ»: دليل}."""
    block = dict(idx.get("heardClip") or {}) if isinstance(idx.get("heardClip"), dict) else {}
    ev = dict(block.get("ayahs") or {})
    for s, rec in surah_recs.items():
        hc = rec.get("heardClip") if isinstance(rec, dict) else None
        if not hc:
            continue
        for a, d in (hc.get("ayahs") or {}).items():
            ev[f"{int(s)}:{int(a)}"] = d
        block.update({"engine": hc.get("engine"), "tolMs": hc.get("tolMs"), "minSim": hc.get("minSim"),
                      "rule": hc.get("rule")})
    if ev:
        block["ayahs"] = dict(sorted(ev.items(), key=lambda kv: tuple(int(x) for x in kv[0].split(":"))))
        idx = dict(idx)
        idx["heardClip"] = block
    return idx


# ───────────────────────────── التشغيل ─────────────────────────────
def subprocess_witness(url, surah, riwaya, model):
    def run(wins):
        spec = ",".join(f"{k}:{s}-{e}" for k, (s, e) in sorted(wins.items()))
        out = tempfile.mkdtemp(prefix="hc_wit_")
        subprocess.run([sys.executable, str(ROOT / "tools" / "index_qa" / "whisper_witness.py"), "--url", url,
                        "--surah", str(surah), "--riwaya", riwaya, "--ayahs", spec, "--model", model,
                        "--out", out], check=True)
        data = json.load(open(os.path.join(out, f"whisper_s{surah:03d}.json"), encoding="utf-8"))
        if run.sha and data.get("sha256") and data.get("sha256") != run.sha:
            raise SystemExit(f"⛔ بصمةُ صوت الشاهد {str(data.get('sha256'))[:8]} غيرُ بصمة الخريطة {str(run.sha)[:8]}")
        return data.get("ayahs") or {}
    run.sha = None
    return run


def make_ctc_runner(url, refs, want_sha):
    """محاذاةُ CTC القسريّة لنصّ الآية وحدها على نافذةٍ ضيّقة (‏`ctc_seg._segment` نفسُه كما في ctc_heard_map)."""
    import hashlib                                                          # noqa: PLC0415
    import numpy as np                                                      # noqa: PLC0415
    from common import fetch_retry, to_wav16k                               # noqa: PLC0415
    from ctc_seg import SR, _emissions, _segment                            # noqa: PLC0415
    from vad import read_wav                                                # noqa: PLC0415
    mp3 = os.path.join(tempfile.mkdtemp(prefix="hc_ctc_"), "a.mp3")
    fetch_retry(url, mp3)
    sha = hashlib.sha256(open(mp3, "rb").read()).hexdigest()
    if want_sha and sha != want_sha:
        raise SystemExit(f"⛔ بصمةُ صوت التأكيد {sha[:8]} غيرُ بصمة الخريطة {str(want_sha)[:8]}")
    wav = to_wav16k(mp3)
    x = read_wav(wav).astype(np.float32)
    from vad import silences                                                # noqa: PLC0415
    sil = [(int(s), int(e)) for s, e in silences(wav)]

    def run(lo, hi, a):
        clip = x[int(lo) * SR // 1000: int(hi) * SR // 1000]
        if len(clip) < SR:
            return None
        try:
            st, en, _sc = _segment(_emissions(clip), len(clip), [refs[a - 1]])[0]
        except Exception:                                                   # noqa: BLE001
            return None
        return int(lo) + int(st * 1000), int(lo) + int(en * 1000)
    return run, sil


SHIFTS_MS = (0, 400, -400, 1000, -1000)


def selftest_rows(samples, ref_words, witness_runner, sil, norm):
    """يطبّق شاهدَ البدء الإنتاجيّ نفسَه على عيّناتٍ (آية، بدء، نهاية) من فهرسٍ سليم مع إزاحاتٍ للبدء.

    يُرجع [{ayah, shift, verdict, why}]. القبولُ عند إزاحة 0 غيرُ مشروط (‏يُقاس ولا يُشترط)، أمّا المزاحُ فيجب أن يُردّ."""
    wins, own, rows = {}, {}, []
    i = 0
    for a, st, en in samples:
        for d in SHIFTS_MS:
            cs = st + d
            ow = onset_window(sil, cs)
            if ow is None:
                rows.append({"ayah": a, "shift": d, "verdict": "rejected", "why": "لا صمتَ قبل البدء المرشَّح"})
                continue
            key = 20_000_000 + i
            i += 1
            wins[key] = (ow[0], en + PAD_MS)
            own[key] = (a, d, cs)
    got = witness_runner(wins) if wins else {}
    for key, (a, d, cs) in own.items():
        rec = got.get(str(key)) or got.get(key)
        if not rec:
            rows.append({"ayah": a, "shift": d, "verdict": "rejected", "why": "لا تفريغَ"})
            continue
        ev, why = eval_start(rec.get("words"), ref_words(a), cs, None, norm)
        rows.append({"ayah": a, "shift": d, "verdict": "accepted" if ev else "rejected",
                     "why": "" if ev else why, "ds": (ev or {}).get("ds")})
    return sorted(rows, key=lambda r: (r["ayah"], r["shift"]))


def selftest(a):
    import gzip                                                             # noqa: PLC0415
    from common import load_index, load_text, norm, surah_slice             # noqa: PLC0415
    idx = json.loads(gzip.decompress(open(a.index, "rb").read()).decode("utf-8"))
    ents = {int(e["ayahId"].split(":")[1]): e for e in idx["entries"] if int(e["ayahId"].split(":")[0]) == a.surah}
    if not ents:
        raise SystemExit(f"⛔ لا مداخل للسورة {a.surah} في الفهرس")
    start, _end, info = surah_slice(load_index(), a.surah)
    texts = load_text(a.riwaya)
    n = int(info["ayahs"])
    refs = [norm(texts[start + i]) for i in range(n)]
    ref = lambda ay: refs[ay - 1].split()                                      # noqa: E731
    if a.ayahs:
        pick = [int(x) for x in a.ayahs.split(",") if x]
    else:
        keys = sorted(ents)
        step = max(1, len(keys) // max(1, a.samples))
        pick = keys[::step][:a.samples]
    samples = [(k, int(ents[k]["startMs"]), int(ents[k]["endMs"])) for k in pick if k in ents]
    runner = subprocess_witness(a.url, a.surah, a.riwaya, a.model)
    _ctc, sil = make_ctc_runner(a.url, refs, None)
    rows = selftest_rows(samples, ref, runner, sil, norm)
    acc = {d: sum(1 for r in rows if r["shift"] == d and r["verdict"] == "accepted") for d in SHIFTS_MS}
    tot = {d: sum(1 for r in rows if r["shift"] == d) for d in SHIFTS_MS}
    bad = [r for r in rows if r["shift"] != 0 and r["verdict"] == "accepted"]
    out = {"surah": a.surah, "index": os.path.basename(a.index), "model": a.model, "samples": len(samples),
           "accepted": acc, "total": tot, "shiftedAccepted": bad, "rows": rows}
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"اختبار التحوّر س{a.surah}: عيّنات {len(samples)} · المقبول لكلّ إزاحة {acc} من {tot}")
    print("⛔ إزاحاتٌ قُبلت (يجب ألّا تُقبل): %d" % len(bad) if bad else "✅ كلُّ البدءات المزاحة رُدّت")
    for r in bad[:10]:
        print("   ", r)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("clip")
    c.add_argument("--batch-dir", required=True)
    c.add_argument("--surah", type=int, required=True)
    c.add_argument("--url", required=True)
    c.add_argument("--riwaya", required=True)
    c.add_argument("--model", default="small", choices=("small", "medium"))
    st = sub.add_parser("selftest", help="اختبارُ التحوّر: إزاحةُ البدء ±400م.ث و±1ث على فهرسٍ منشورٍ سليم يجب أن تُردّ")
    st.add_argument("--index", required=True)
    st.add_argument("--surah", type=int, required=True)
    st.add_argument("--url", required=True)
    st.add_argument("--riwaya", required=True)
    st.add_argument("--model", default="small", choices=("small", "medium"))
    st.add_argument("--samples", type=int, default=12)
    st.add_argument("--ayahs", default="", help="آياتٌ مسمّاة بفواصل بدل العيّنة المتباعدة")
    st.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest(a)
    from common import load_index, load_text, norm, surah_slice                 # noqa: PLC0415
    path = Path(a.batch_dir) / f"s{a.surah:03d}.json"
    if not path.exists():
        print(f"⛔ لا ملفَّ خريطةٍ للسورة {a.surah}: {path}")
        return 0
    rec = json.load(open(path, encoding="utf-8"))
    start, _end, info = surah_slice(load_index(), a.surah)
    texts = load_text(a.riwaya)
    n = int(info["ayahs"])
    refs = [norm(texts[start + i]) for i in range(n)]
    ref = lambda ay: refs[ay - 1].split()                                      # noqa: E731
    runner = subprocess_witness(a.url, a.surah, a.riwaya, a.model)
    runner.sha = rec.get("sha256")
    ctc, sil = make_ctc_runner(a.url, refs, rec.get("sha256"))
    res = clip_surah(rec, ref, n, runner, ctc, norm, sil)
    if not res["ok"]:
        # ⛔ لا قصَّ بالتخمين: السورةُ تبقى بلا مداخل (‏يُنقل الملفُّ جانباً فلا يدمجه الدمج) ويُكتب السببُ.
        report = Path(a.batch_dir) / f"clip_s{a.surah:03d}.unresolved.json"
        json.dump({"surah": a.surah, "unresolved": res["unresolved"], "rounds": res["rounds"]},
                  open(report, "w", encoding="utf-8"), ensure_ascii=False)
        path.rename(Path(a.batch_dir) / f"s{a.surah:03d}.json.unclipped")
        print(f"⛔ س{a.surah}: لم يثبت أداءٌ تامٌّ لـ{len(res['unresolved'])} آية — تبقى محجوبةً معلَنة")
        for ay, why in sorted(res["unresolved"].items())[:40]:
            print(f"   {a.surah}:{ay} — {why}")
        return 0
    out = apply_to_surah_json(rec, res)
    json.dump(out, open(str(path) + ".part", "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(str(path) + ".part", path)
    print(f"✅ س{a.surah}: قُصّت {len(res['entries'])} آيةً على أدائها الثابت ({res['rounds']} جولة)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
