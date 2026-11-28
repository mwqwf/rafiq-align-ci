#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""الشاهدُ الأقوى لنوافذ المداخل — محاذاةٌ قسريّةٌ بنموذجَي CTC (‏2026-11-08 · قرار القائد: «شاهدٌ أقوى لا إرخاء»).

المدخلُ الذي يردّه إحصاءُ النوافذ بـ«نقص» **وحدَه** (‏ثقةُ Whisper في الكلمات الطرفيّة أو عددُها دون الحدّ، وتشابهُ الآية
بالتفريغ ≥ `SIM_FLOOR`) يمرّ إن تحقّق **الثلاثةُ مجتمعةً في النموذجين معاً** (‏العامّ `jonatasgrosman` والقرآنيّ `rabah2026`،
مثبَّتا البصمة، float32، خيطان — كما `window_census_witness`):
 ١. المحاذاةُ القسريّة لنصّ الآية وحدَها في نافذة مدخلها (‏[بدء − START_TOL، نهاية + END_TOL] من صوت السورة) بثقة
    ≥ `TARGET_CONF` (‏الثابتُ نفسُه في `window_census_witness`، لا عتبةً جديدة).
 ٢. حدودُها داخل النافذة: بدؤها ≥ بدء المدخل − `START_TOL` ونهايتُها ≤ نهايته + `END_TOL`
    (‏ثابتان من `window_census_witness`؛ ويُسمح أن تبدأ بعد بدء المدخل أو تنتهي قبل نهايته لصمتٍ فيه)، **ولا تلتصق بحافّة الصوت المقصوص** (‏أقلّ من إطارَين: النصُّ قد يمتدّ خارجها —
    نافذةٌ مبتورة؛ وتُعفى الحافّةُ التي قصّها بدءُ الملفّ أو نهايتُه فعلاً).
 ٣. ولا تفوز عليها جارةٌ ±2 بالمحاذاة نفسِها: كلُّ جارةٍ نصُّها يخالف الآية تُحاذى في النافذة نفسِها بالنموذج نفسِه،
    وثقتُها ليست أعلى من ثقة الآية (‏الأعلى تفوز). والجارةُ المطابقةُ نصّاً **منافِسةٌ** (‏تشديد ج): لا تفرّقها المحاذاةُ، فتُحسم
    بالموضع (‏نافذتان غيرُ متقاطعتين بترتيب الآيات) وإلا تُردّ.
وأمّا «زيادة» و«آية أخرى» فلا يحسمها هذا الشاهدُ ولا تمرّ به، ولا يكفي نموذجٌ واحد.

⛔ قارئٌ محض: لا يحجب ولا يرقّي ولا يكتب في `timings/`، ولا يمسّ `heard_gate.py` ولا `promote.py` ولا عتبةً قائمة.
والتفريغُ والمحاذاةُ مرشّحان للحكم وحدَه، ولا يُكتب منهما نصٌّ في أيّ فهرس.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
for _p in (ROOT / "tools" / "alignment_v3", ROOT / "tools" / "alignment", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import window_census_witness as WCW                                    # noqa: E402

TARGET_CONF = WCW.TARGET_CONF          # 0.60 — ثقةُ الآية المعنيّة في كلّ نموذج (‏لا عتبةَ جديدة)
START_TOL = WCW.START_TOL              # 500 م.ث
END_TOL = WCW.END_TOL                  # 800 م.ث
EDGE_FRAMES = 2                        # التصاقُ الحدّ بحافّة الصوت: أقلّ من إطارَين (‏≈40 م.ث)
MODELS = ("generic", "quran")
NEIGHBOURS = 2


# ───────────────────────── الحكم (‏منطقٌ خالص — يُختبر بقياساتٍ مصطنعة) ─────────────────────────
def window_of(start_ms: int, end_ms: int, total_ms: int) -> tuple[int, int, bool, bool]:
    """(بدءُ الصوت المقصوص، نهايتُه، قُصّ البدءُ عند 0؟، قُصّت النهايةُ عند طول الملفّ؟)."""
    lo, hi = int(start_ms) - START_TOL, int(end_ms) + END_TOL
    return max(0, lo), min(int(total_ms), hi), lo <= 0, hi >= int(total_ms)


def model_check(name: str, m: dict, entry: tuple[int, int]) -> list[str]:
    """أسبابُ رفض نموذجٍ واحد (‏فارغةٌ = يجتاز). `m` = {own:[بدء،نهاية،ثقة]، rivals:{آية:ثقة}، frameMs، audioMs:[أ،ب]،
    clipLo، clipHi}."""
    why = []
    try:
        s, e, conf = (float(x) for x in m["own"])
        frame = float(m["frameMs"])
        a, b = (float(x) for x in m["audioMs"])
    except (KeyError, TypeError, ValueError):
        return [f"{name}: لا قياسَ صالحٌ للآية"]
    if not all(math.isfinite(x) for x in (s, e, conf, frame, a, b)) or not 0 <= conf <= 1 or e <= s:
        return [f"{name}: قياسٌ غيرُ صالح"]
    if conf < TARGET_CONF:
        why.append(f"{name}: ثقةُ الآية {conf:.2f} دون TARGET_CONF={TARGET_CONF}")
    # حدودُها داخل النافذة: [بدء المدخل − START_TOL، نهايته + END_TOL] (‏نافذةُ الصوت المقصوص نفسُها). ولا يُشترط التطابقُ
    # مع حدّي المدخل: يمتدّ المدخلُ عادةً على صمتٍ قبل الآية أو بعدها (‏قِيس في الدخان: نهايةٌ أبكرُ بـ1.2–2.4ث وثقةٌ ≥0.65).
    if s < entry[0] - START_TOL or e > entry[1] + END_TOL:
        why.append(f"{name}: حدودُ الآية المحاذاة [{s:.0f},{e:.0f}] خارج نافذة المدخل [{entry[0] - START_TOL},{entry[1] + END_TOL}]")
    edge = EDGE_FRAMES * frame
    if (not m.get("clipLo") and s <= a + edge) or (not m.get("clipHi") and e >= b - edge):
        why.append(f"{name}: الحدُّ ملتصقٌ بحافّة النافذة المقصوصة (‏نافذةٌ مبتورة أو آيةٌ تمتدّ خارجها)")
    for r, c in sorted((m.get("rivals") or {}).items(), key=lambda kv: int(kv[0])):
        try:
            c = float(c)
        except (TypeError, ValueError):
            why.append(f"{name}: قياسٌ غيرُ صالحٍ للجارة {r}")
            continue
        if not math.isfinite(c) or c > conf:
            why.append(f"{name}: الجارة {r} تفوز بالمحاذاة ({c:.2f} > {conf:.2f})")
    return why


def judge_witness(entry: tuple[int, int], measures: dict, undecided_identical: list[int] | None = None) -> dict:
    """حكمُ الشاهد على مدخلٍ نافذتُه `entry`=(بدء، نهاية): يلزم قياسُ النموذجين معاً (‏نموذجٌ واحدٌ لا يكفي).
    `undecided_identical`: جاراتٌ مطابقةٌ نصّاً لم يحسمها الموضعُ ⇒ تُردّ."""
    why: list[str] = []
    if set(measures) != set(MODELS):
        why.append(f"شاهدٌ بنموذجٍ واحدٍ أو ناقص ({sorted(measures)}) — يلزم {list(MODELS)} معاً")
    for name in MODELS:
        if name in measures:
            why += model_check(name, measures[name], entry)
    if undecided_identical:
        why.append(f"الآية {undecided_identical[0]} مطابقةٌ نصّاً ولم يُحسم الموضع")
    return {"pass": not why, "why": why}


def classify(entry: tuple[int, int], measures: dict | None) -> dict:
    """تصنيفُ مدخلٍ ردّه الإحصاءُ «آية أخرى» (‏للقائد — لا يحجب ولا يُعلن عطباً):
    «الآيةُ نفسُها مسموعة» = اجتاز الشاهدُ كلَّ شروطه في النموذجين؛
    «غيرها مسموع» = في **كلا النموذجين** جارةٌ تفوز على الآية بالمحاذاة (‏وسُمّيت)؛
    وما عدا ذلك «غير محسوم» (‏نموذجٌ ناقصٌ · ثقةٌ دون العتبة بلا جارةٍ فائزة · تباينُ النموذجين…)."""
    if not measures or set(measures) != set(MODELS):
        return {"class": "غير محسوم", "why": ["قياسُ نموذجٍ ناقص"]}
    res = judge_witness(entry, measures)
    if res["pass"]:
        return {"class": "الآيةُ نفسُها مسموعة", "why": []}
    winners = {}
    for name in MODELS:
        own = float(measures[name]["own"][2])
        winners[name] = {r: float(c) for r, c in (measures[name].get("rivals") or {}).items() if float(c) > own}
    common = set(winners["generic"]) & set(winners["quran"])
    if winners["generic"] and winners["quran"] and common:
        return {"class": "غيرها مسموع", "winners": sorted(common, key=int), "why": res["why"]}
    return {"class": "غير محسوم", "why": res["why"]}


def apply_witness(row: dict, measures: dict | None, windows: dict | None = None, texts: dict | None = None) -> dict:
    """يُرجع الصفَّ بعد الشاهد: «نقص» مؤهَّلٌ + شاهدٌ ناجٍ ⇒ يمرّ (‏`witnessRescued`)، وإلا الصفُّ كما هو مع أثر الشاهد.
    «زيادة» و«آية أخرى» وغيرُ المؤهَّل لا يمرّون به أبداً."""
    out = dict(row)
    if row.get("verdict") != "reject" or row.get("reason") != "نقص" or not row.get("witnessEligible") or measures is None:
        return out
    res = judge_witness((int(row["startMs"]), int(row["endMs"])), measures)
    out["witness"] = {"pass": res["pass"], "why": res["why"], "models": {k: {"own": v.get("own"), "rivals": v.get("rivals")}
                                                                       for k, v in measures.items()}}
    if res["pass"]:
        out.update({"verdict": "pass", "reasonBeforeWitness": row["reason"], "reason": "", "witnessRescued": True,
                    "detail": "نقصٌ في تفريغ Whisper حسمه الشاهدُ الأقوى (‏محاذاةٌ قسريّةٌ بنموذجَي CTC): " + row["detail"]})
    return out


# ───────────────────────── القياس (‏CI فقط — يحتاج النماذج المثبَّتة) ─────────────────────────
def _models():
    import ci_spoken_census as S                                       # noqa: PLC0415
    return S


def entry_texts(riwaya: str, surah: int, ayah: int, texts_by_surah: dict | None = None) -> dict[int, str]:
    """نصوصُ المحاذاة {آية: نص} للآية وجاراتِها ±2 المخالفة نصّاً (‏`alignment_text` كما `window_census_witness.plan`)."""
    from common import load_index, load_text, norm, surah_slice          # noqa: PLC0415
    from spoken_letters import alignment_text                             # noqa: PLC0415
    start, end, _ = surah_slice(load_index(), surah)
    refs = load_text(riwaya)[start:end]
    own_norm = norm(refs[ayah - 1])
    out = {ayah: alignment_text(surah, ayah, refs[ayah - 1])}
    for b in range(max(1, ayah - NEIGHBOURS), min(len(refs), ayah + NEIGHBOURS) + 1):
        if b != ayah and norm(refs[b - 1]) != own_norm:
            out[b] = alignment_text(surah, b, refs[b - 1])
    return out


def measure_candidates(cands: list[dict], name: str) -> None:
    """يقيس لكلّ مرشَّحٍ بنموذجٍ واحدٍ ويكتب `c['measures'][name]`.
    `cands[i]` = {pcm: f32 16k للنافذة المقصوصة، audioMs:[أ،ب]، clipLo، clipHi، texts:{آية:نص}، ayah}."""
    S = _models()
    model = S.configure_generic() if name == "generic" else S.Q.configure()
    for c in cands:
        pcm = c["pcm"]
        a = c["audioMs"][0]
        try:
            lpz = S.C._emissions(pcm)
            frame = len(pcm) / 16 / lpz.shape[0]
            res = {}
            for ay, t in c["texts"].items():
                txt = t if name == "generic" else S.Q.reference_text(t)
                (b, e, sc), = S.C._segment(lpz, len(pcm), [txt])
                res[ay] = [a + int(b * 1000), a + int(e * 1000), S.C._conf(sc)]
            m = {"own": res.pop(c["ayah"]), "rivals": {str(k): v[2] for k, v in res.items()},
                 "rivalSpans": {str(k): v[:2] for k, v in res.items()},
                 "frameMs": frame, "audioMs": c["audioMs"], "clipLo": c["clipLo"], "clipHi": c["clipHi"],
                 "model": model}
        except Exception as ex:                                        # noqa: BLE001
            m = {"error": str(ex)[:200]}
        c.setdefault("measures", {})[name] = m
    S.C._M.clear()
    import gc                                                          # noqa: PLC0415
    gc.collect()


def usable(measures: dict | None) -> dict | None:
    """يُسقط قياساً فيه خطأٌ (‏يبقى النموذجُ ناقصاً فيُردّ الشاهد) ويُخرج حقل `model` من الأثر المحكوم."""
    if not measures:
        return None
    return {k: {kk: vv for kk, vv in v.items() if kk != "model"} for k, v in measures.items() if "error" not in v}


def errors(measures: dict | None) -> dict:
    """أخطاءُ القياس لكلّ نموذج (‏تُحفظ في الصفّ للتشخيص؛ ونموذجٌ بخطأٍ ⇒ الشاهدُ ناقصٌ فيُردّ)."""
    return {k: v["error"] for k, v in (measures or {}).items() if "error" in v}
