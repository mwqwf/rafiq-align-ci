#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محرّك `ctc-heardmap-1`: خريطةُ «أيُّ آيةٍ تُسمع أين» للملفّ كلِّه، ثمّ محاذاةٌ قسريّةٌ
بنوافذَ ضيّقةٍ على مراسٍ **مسموعة** — لتسجيلٍ فيه مادّةٌ زائدة أو مقاطعُ مكرّرة.

⭐ **سببُه مقيسٌ (‏عاصم اللحيدان · س38 · 2026-09-28/10-02):** مصدرُ ص البديلُ تسجيلُ
تراويح طولُه 946ث (‏1.58× المتوقَّع)، ومحاذاةُ السورة كاملةً بـ`ctc_seg` (‏رتيبةٌ على
الملفّ كلِّه) كبست النصَّ في أوّل 597ث، فجاء الإحصاءُ الشامل 81/88 نافذةً «غير حاسم»
والنوافذُ تسمع آياتٍ قبلها بفارقٍ يكبر حتى ~20 آية. المحاذاةُ الرتيبةُ تفترض أنّ الملفَّ
= النصُّ مرّةً واحدةً بلا زيادة؛ وتسجيلُ التراويح لا يفي بهذا (‏دعاءٌ · سجدةُ تلاوة ·
إعادةُ مقطع).

## الطريقة
1. **فكٌّ جشع** لمخرَج CTC على الملفّ كلِّه ⇒ نصٌّ مسموعٌ تقريبيٌّ **مع زمنِ كلّ حرف**.
   ⛔ هذا النصُّ **لا يُشحن ولا يُنشر** — هو مِرساةُ بحثٍ فقط؛ النصُّ المنشور نصُّ الرواية.
2. **خريطةُ السماع:** لكلّ آيةٍ من نصّ الرواية مواضعُ ظهورها في المسموع (‏تشابهٌ جزئيٌّ
   بالمسافة التحريريّة)، فتُكشف الزيادةُ والتكرار، لا تُخمَّن.
3. **سلسلةٌ رتيبة:** لكلّ آيةٍ أداءٌ واحدٌ، وعند التكرار يُعتمد **الأداءُ الأخيرُ المتّصلُ بما
   بعده**، والمقطعُ المكرّرُ يبقى **خارجَ المداخل** (‏لا يُنسب إلى آيةٍ غيرِه).
4. **محاذاةٌ قسريّة** (‏`ctc_segmentation` نفسُه) على نوافذَ من ≤12 آيةً بين مرساتين
   مسموعتين، مع آيةِ سياقٍ من كلّ طرفٍ تُهمل حدودُها.

## الحُرّاس (‏كما في `ctc_seg` ولا أضعف)
- لا HIGH بلا برهان صمت (‏D-025) — الثقةُ تُسقَف 0.74 ما لم يقع الحدُّ في صمت.
- آيةٌ لم تُسمع في الخريطة (‏لا موضعَ لها ≥ العتبة) تُوسم `heard=false` في الدليل وتُحاذى
  بين جارتيها فقط إن كانتا مسموعتين — وإلا تبقى بلا حدود فتُردّ السورةُ كلُّها في الدمج.
- فحوصُ `validate.check_surah` (‏رتابة · تداخل · فجوات · مدّة شاذّة) تُكتب في `issues`.
- والحكمُ الحاسمُ للبوّابة الصوتيّة (‏مطالع · أربعةُ ملوح · إحصاءٌ شامل · عتبة 5%).

    python tools/alignment_v3/ctc_heard_map.py --url https://…/038.mp3 --surah 38 \
        --riwaya hafs --out-dir tools/alignment/work/batch_asim [--probe --report r.txt]

النموذج: `jonatasgrosman/wav2vec2-large-xlsr-53-arabic` (Apache-2.0) عبر `ctc_seg`.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))

ENGINE = "ctc-heardmap-1"
MIN_OCC = 0.55          # أدنى تشابهٍ يُعدّ به الموضعُ «سماعاً» للآية
STRONG = 0.70           # مِرساةٌ قويّة
MAX_WIN_AYAT = 12       # أقصى آياتٍ في نافذة محاذاة
PAD_MS = 1500           # هامشُ النافذة حول المسموع
REPEAT_GAP_MS = 6000    # فجوةٌ بعد آيةٍ تُفحص عن تكرارٍ قبل أن تُضمّ إلى مدخلها
TAIL_MS = 800           # ذيلُ آخر آية بعد آخر حرفٍ مسموع
_SUB1 = {"ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ؤ": "و", "ئ": "ي", "ى": "ي", "ة": "ه",
         "ے": "ي", "ء": ""}


# ───────────────────────── دوالٌ محضة (‏تُختبر بلا نموذج) ─────────────────────────
def skeleton(chars):
    """[(حرف، زمن م.ث)] ⇒ (هيكلٌ بلا مسافاتٍ ولا همزة، أزمنةُ حروفه)."""
    sk, ts = [], []
    for c, t in chars:
        c = _SUB1.get(c, c)
        if not c or c == " " or not ("ء" <= c <= "ي"):
            continue
        sk.append(c)
        ts.append(int(t))
    return "".join(sk), ts


def greedy_decode(lpz, frame_ms, char_list, blank, delimiter="|"):
    """أرجحُ رمزٍ في كلّ إطار، مع طيّ التكرار والفراغ ⇒ [(حرف، زمنُ بدءِ الحرف م.ث)]."""
    out, prev = [], blank
    ids = lpz.argmax(axis=-1)
    for i, k in enumerate(ids.tolist()):
        if k != blank and k != prev:
            ch = char_list[k] if k < len(char_list) and char_list[k] is not None else ""
            if ch == delimiter:
                ch = " "
            if ch:
                out.append((ch, int(i * frame_ms)))
        prev = k
    return out


def _partial(ayah, seg):
    """(‏بدءٌ، نهايةٌ، تشابهٌ) لأفضل موضعٍ للآية داخل `seg` — rapidfuzz إن وُجد وإلا difflib."""
    try:
        from rapidfuzz import fuzz
        al = fuzz.partial_ratio_alignment(ayah, seg)
        if al is None:
            return None
        return al.dest_start, al.dest_end, al.score / 100.0
    except ImportError:                       # تقريبٌ أخشن بلا اعتمادٍ ثنائيّ — للاختبار المحلّيّ
        sm = difflib.SequenceMatcher(None, ayah, seg, autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        if not blocks:
            return None
        matched = sum(b.size for b in blocks)
        return blocks[0].b, blocks[-1].b + blocks[-1].size, min(1.0, matched / max(len(ayah), 1))


def occurrences(ayah_sk, heard_sk, min_score=MIN_OCC, max_hits=6):
    """كلُّ مواضع سماعِ الآية في الهيكل المسموع: [(a، b، تشابه)] مرتّبةً بالموضع، بلا تداخل."""
    L = len(ayah_sk)
    if L < 3 or not heard_sk:
        return []
    win = int(L * 1.6) + 8
    step = max(4, L // 3)
    hits = []
    for s0 in range(0, max(1, len(heard_sk) - L // 2), step):
        seg = heard_sk[s0:s0 + win]
        if len(seg) < max(3, L // 2):
            break
        r = _partial(ayah_sk, seg)
        if r is None:
            continue
        a, b, sc = r
        if sc >= min_score and b > a:
            hits.append((s0 + a, s0 + b, round(float(sc), 3)))
    hits.sort(key=lambda h: (-h[2], h[0]))
    keep = []
    for h in hits:
        if all(h[1] <= k[0] or h[0] >= k[1] for k in keep):
            keep.append(h)
    keep.sort()
    return keep[:max_hits] if len(keep) <= max_hits else sorted(sorted(keep, key=lambda h: -h[2])[:max_hits])


def choose_chain(occ, min_score=MIN_OCC, slack=6):
    """أداءٌ واحدٌ لكلّ آية، رتيبٌ: يُمشى من الآخِر إلى الأوّل فيُختار **آخرُ** أداءٍ ينتهي قبل
    بدءِ ما اختير للآية التالية (‏«الأداءُ الأخيرُ المتّصلُ بما بعده»)، ما لم يكن أضعفَ من
    أفضل أداءٍ بأكثر من 0.15 فيُقدَّم الأفضل. يُرجع قائمةً بالطول نفسِه: (a، b، تشابه) أو None."""
    n = len(occ)
    chosen = [None] * n
    bound = None
    for k in range(n - 1, -1, -1):
        cands = [o for o in occ[k] if o[2] >= min_score and (bound is None or o[1] <= bound + slack)]
        if not cands:
            continue
        best = max(c[2] for c in cands)
        good = [c for c in cands if c[2] >= best - 0.15]
        c = max(good, key=lambda o: o[0])
        chosen[k] = c
        bound = c[0]
    return chosen


def plan_windows(chosen_ms, n, max_ayat=MAX_WIN_AYAT, split_gap_ms=25000):
    """يقسم الآيات 0..n-1 إلى نوافذَ [i، j] متتالية: تُقطع النافذةُ عند بلوغ `max_ayat` أو عند
    فجوةٍ مسموعةٍ > `split_gap_ms` بين أداءين متتاليين. `chosen_ms[k]` = (بدءٌ، نهايةٌ) أو None."""
    wins, i = [], 0
    for k in range(1, n + 1):
        cut = k == n or (k - i) >= max_ayat
        if not cut and chosen_ms[k] and chosen_ms[k - 1]:
            cut = chosen_ms[k][0] - chosen_ms[k - 1][1] > split_gap_ms
        if cut:
            wins.append((i, k - 1))
            i = k
    return wins


def chunk_map(heard_sk, times, ayah_sks, chunk_ms=15000):
    """لكلّ قطعةٍ زمنيّةٍ من المسموع: أقربُ آيةٍ إليها وتشابهُها — يكشف ما في الزيادة."""
    out = []
    if not heard_sk:
        return out
    t_end = times[-1] + chunk_ms
    for t0 in range(0, t_end, chunk_ms):
        lo = next((i for i, t in enumerate(times) if t >= t0), len(times))
        hi = next((i for i, t in enumerate(times) if t >= t0 + chunk_ms), len(times))
        seg = heard_sk[lo:hi]
        if len(seg) < 8:
            out.append((t0, t0 + chunk_ms, None, 0.0, len(seg)))
            continue
        best, bsc = None, 0.0
        for k, a in enumerate(ayah_sks):
            r = _partial(a, seg)
            if r and r[2] > bsc:
                best, bsc = k, r[2]
        out.append((t0, t0 + chunk_ms, best, round(bsc, 3), len(seg)))
    return out


# ───────────────────────── التنفيذ (‏يحتاج النموذج) ─────────────────────────
def _char_list():
    from ctc_seg import _model
    tok = _model()["proc"].tokenizer
    vocab = tok.get_vocab()
    cl = [None] * (max(vocab.values()) + 1)
    for ch, i in vocab.items():
        cl[i] = ch
    return cl, tok.pad_token_id, (tok.word_delimiter_token if hasattr(tok, "word_delimiter_token") else "|")


def run(audio, surah, riwaya, log=print, probe=False):
    import numpy as np
    from ctc_seg import SR, _conf, _emissions, _segment
    from common import ffprobe_duration_ms, load_index, load_text, norm, surah_slice, to_wav16k
    from vad import read_wav, silences, snap_to_silence
    from validate import band, check_surah

    index = load_index()
    a, b, _ = surah_slice(index, surah)
    canonical = load_text(riwaya)[a:b]
    refs = [norm(t) for t in canonical]
    sks = [r.replace(" ", "") for r in refs]
    n = len(refs)
    wav = to_wav16k(audio)
    total_ms = ffprobe_duration_ms(audio)
    x = read_wav(wav).astype(np.float32)
    log(f"س{surah}: {n} آية · الملفّ {total_ms / 1000:.0f}ث · فكّ CTC للملفّ كلِّه…")
    lpz = _emissions(x)
    frame_ms = len(x) / lpz.shape[0] * 1000.0 / SR
    cl, blank, delim = _char_list()
    chars = greedy_decode(lpz, frame_ms, cl, blank, delim)
    heard_sk, times = skeleton(chars)
    log(f"المسموع: {len(heard_sk)} حرفاً هيكليّاً على {len(lpz)} إطاراً ({frame_ms:.1f}م.ث/إطار)")

    occ = [occurrences(sk, heard_sk) for sk in sks]
    chosen = choose_chain(occ)
    chosen_ms = [(times[c[0]], times[min(c[1], len(times)) - 1] + int(frame_ms)) if c else None
                 for c in chosen]
    heard_map = {}
    for k in range(n):
        c = chosen[k]
        heard_map[str(k + 1)] = {
            "heard": c is not None,
            "heardMs": list(chosen_ms[k]) if c else None,
            "score": c[2] if c else None,
            "occurrences": [[times[o[0]], times[min(o[1], len(times)) - 1] + int(frame_ms), o[2]]
                            for o in occ[k]]}
    chunks = chunk_map(heard_sk, times, sks)
    report = [f"# خريطةُ السماع س{surah} · {total_ms}م.ث · {len(heard_sk)} حرفاً مسموعاً",
              "# آية\tبدء\tنهاية\tتشابه\tأداءاتٌ أخرى"]
    for k in range(n):
        h = heard_map[str(k + 1)]
        others = [o for o in h["occurrences"] if not h["heardMs"] or o[0] != h["heardMs"][0]]
        report.append(f"{surah}:{k + 1}\t{h['heardMs'][0] / 1000:.1f}\t{h['heardMs'][1] / 1000:.1f}\t{h['score']}\t"
                      f"{' · '.join(f'{o[0] / 1000:.0f}–{o[1] / 1000:.0f}s({o[2]})' for o in others)}"
                      if h["heardMs"] else f"{surah}:{k + 1}\t—\t—\t—\tلم تُسمع ≥{MIN_OCC}")
    report.append("# قطعُ الملفّ (15ث): أقربُ آيةٍ وتشابهُها — ما لا يقارب شيئاً مادّةٌ زائدة · ثمّ المسموعُ نفسُه")
    words = "".join(c for c, _ in chars)
    wtimes = [t for _, t in chars]
    for t0, t1, k, sc, nch in chunks:
        lo = next((i for i, t in enumerate(wtimes) if t >= t0), len(wtimes))
        hi = next((i for i, t in enumerate(wtimes) if t >= t1), len(wtimes))
        report.append(f"{t0 / 1000:.0f}–{t1 / 1000:.0f}s\t{(str(surah) + ':' + str(k + 1)) if k is not None else '—'}\t{sc}\t{nch}حرفاً\t«{words[lo:hi].strip()}»")
    unheard = [k + 1 for k in range(n) if chosen[k] is None]
    log(f"مسموعةٌ: {n - len(unheard)}/{n}" + (f" · لم تُسمع: {unheard}" if unheard else ""))
    result = {"surah": surah, "riwaya": riwaya, "engine": ENGINE, "totalMs": total_ms,
              "heardMap": heard_map, "chunkMap": [list(c) for c in chunks],
              "heardChars": len(heard_sk), "entries": [], "issues": [], "bands": {}}
    if probe:
        return result, "\n".join(report)

    # ── المحاذاةُ القسريّة على نوافذَ مرساتُها مسموعة ──
    sil = silences(wav)
    wins = plan_windows(chosen_ms, n)
    starts, scores = [None] * n, [0.0] * n
    for i, j in wins:
        first = next((k for k in range(i, j + 1) if chosen_ms[k]), None)
        last = next((k for k in range(j, i - 1, -1) if chosen_ms[k]), None)
        if first is None or last is None:
            result["issues"].append(f"نافذة {i + 1}–{j + 1}: لا مِرساةَ مسموعةً فيها — تُترك بلا حدود")
            continue
        lead = i - 1 if i > 0 and chosen_ms[i - 1] else None
        trail = j + 1 if j + 1 < n and chosen_ms[j + 1] else None
        ws = chosen_ms[lead][0] if lead is not None else max(0, chosen_ms[first][0] - PAD_MS)
        we = chosen_ms[trail][1] if trail is not None else min(total_ms, chosen_ms[last][1] + PAD_MS)
        ws, we = int(max(0, ws)), int(min(total_ms, we))
        texts = ([refs[lead]] if lead is not None else []) + refs[i:j + 1] + ([refs[trail]] if trail is not None else [])
        clip = x[ws * SR // 1000: we * SR // 1000]
        try:
            segs = _segment(_emissions(clip), len(clip), texts)
        except Exception as ex:                                 # noqa: BLE001
            result["issues"].append(f"نافذة {i + 1}–{j + 1}: تعذّرت المحاذاة — {str(ex)[:80]}")
            continue
        off = 1 if lead is not None else 0
        for k in range(i, j + 1):
            st, _en, sc = segs[off + (k - i)]
            starts[k], scores[k] = ws + int(st * 1000), sc
    entries = []
    for k in range(n):
        if starts[k] is None:
            entries.append({"ayahIdx": k, "startMs": None, "endMs": None, "conf": 0.0,
                            "snapped": False, "matched": 0, "total": len(refs[k].split())})
            continue
        t, on_sil = snap_to_silence(int(starts[k]), sil, tolerance_ms=700)
        entries.append({"ayahIdx": k, "startMs": int(t), "endMs": None, "conf": _conf(scores[k]),
                        "snapped": bool(on_sil), "matched": 0, "total": len(refs[k].split()),
                        "heard": chosen[k] is not None})
    # النهايات: نهايةُ الآية = بدايةُ التالية، إلا حيث يفصلهما مقطعٌ مكرَّرٌ (‏أداءٌ آخر لآيةٍ
    # سابقة) فتُحدّ بآخر حرفٍ مسموعٍ لها + ذيل، ويبقى المكرَّرُ خارجَ المداخل.
    for k in range(n):
        e = entries[k]
        if e["startMs"] is None:
            continue
        nxt = next((entries[m]["startMs"] for m in range(k + 1, n) if entries[m]["startMs"] is not None), None)
        e["endMs"] = nxt if nxt is not None else min(total_ms, (chosen_ms[k][1] if chosen_ms[k] else e["startMs"]) + TAIL_MS)
        if nxt is not None and chosen_ms[k] and nxt - chosen_ms[k][1] > REPEAT_GAP_MS:
            lo, hi = chosen_ms[k][1], nxt
            repeated = [m + 1 for m in range(0, k + 1) for o in heard_map[str(m + 1)]["occurrences"]
                        if lo - 500 <= o[0] and o[1] <= hi + 500]
            if repeated:
                e["endMs"] = min(nxt, chosen_ms[k][1] + TAIL_MS)
                e["repeatExcluded"] = sorted(set(repeated))
                result["issues"].append(f"مقطعٌ مكرَّرٌ بعد الآية {k + 1} ({lo / 1000:.0f}–{hi / 1000:.0f}ث · "
                                        f"آياتُه {sorted(set(repeated))}) أُبقي خارجَ المداخل")
    for e in entries:
        if e["startMs"] is not None and e["endMs"] <= e["startMs"]:
            e.update(startMs=None, endMs=None, conf=0.0)
        elif e["startMs"] is not None and not e["snapped"]:
            e["conf"] = min(e["conf"], 0.74)       # ⛔ D-025: لا HIGH بلا صمت
    result["issues"] += check_surah(entries, [len(sk) for sk in sks], total_ms)
    bands = {}
    for e in entries:
        kk = band(e["conf"]) if e["startMs"] is not None else "MISSING"
        bands[kk] = bands.get(kk, 0) + 1
    result.update(entries=entries, bands=bands)
    log(f"سورة {surah}: {bands} · {len(result['issues'])} ملاحظة")
    report.append("# المداخل")
    for e in entries:
        report.append(f"{surah}:{e['ayahIdx'] + 1}\t{e['startMs']}\t{e['endMs']}\t{e['conf']}\t"
                      f"{'صمت' if e['snapped'] else ''}\t{'' if e.get('heard', True) else 'غيرُ مسموعة'}")
    for i_ in result["issues"]:
        report.append("⚠️ " + i_)
    return result, "\n".join(report)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="رابطُ صوتِ السورة (‏يُنزَّل إلى out-dir)")
    ap.add_argument("--audio", help="ملفٌّ محلّيّ بدلَ الرابط")
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--probe", action="store_true", help="خريطةُ السماع وحدها بلا محاذاة ولا مداخل")
    ap.add_argument("--report", default="", help="ملفُّ تقريرٍ نصّيّ (‏افتراضه <out-dir>/heard_s<س>.txt)")
    a = ap.parse_args()
    if not a.url and not a.audio:
        ap.error("يلزم --url أو --audio")
    os.makedirs(a.out_dir, exist_ok=True)
    audio = a.audio or os.path.join(a.out_dir, f"{a.surah:03d}.mp3")
    if not a.audio and (not os.path.exists(audio) or os.path.getsize(audio) < 10_000):
        from ctc_gapsplit import fetch
        fetch(a.url, audio)
    sha = hashlib.sha256(open(audio, "rb").read()).hexdigest()
    res, report = run(audio, a.surah, a.riwaya, probe=a.probe)
    import vad as _vad
    res.update(fileRef=a.url or audio, sha256=sha, vadRel=getattr(_vad, "LAST_REL", None),
               vadVersion=getattr(_vad, "VAD_VERSION", None))
    rep_path = a.report or os.path.join(a.out_dir, f"heard_s{a.surah:03d}.txt")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    out = os.path.join(a.out_dir, f"heard_s{a.surah:03d}.json" if a.probe else f"s{a.surah:03d}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    print(report)
    print(f"كُتب: {out} · {rep_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
