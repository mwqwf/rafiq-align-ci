#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعفاءُ الفحص البنيويّ (‏`run.py --struct-only`) من عتبة الغياب 2% للحجب المؤقّت `TIMING_UNDER_REPAIR` وحدَه.

السند: إذنُ المالك 2026-11-05 (الحجبُ المؤقّت المعلَن) و2026-11-07 (بابُ الإسقاط المعلَن)؛ وشروطُ القائد 2026-11-10.

سورةٌ ثبت بشاهدَين أنّ توقيتها يُسمع على صوت غيرها تُحجب مؤقّتاً بإعلانٍ، والحجبُ ليس فقداً؛ فلا يُحسب على الفهرس
في عتبة 2%. ولا يُعفى شيءٌ إلا باجتماع ما يلي، وكلُّه يُتحقَّق من **مضمونه** لا من وجوده:

  (أ) رمزُ السورة في الترويسة `TIMING_UNDER_REPAIR` نفسُه — لا OTHER ولا SOURCE_TRUNCATED ولا غيرُهما.
  (ب) صفٌّ في `ops/OWNER_DROP_APPROVALS.json` لمفتاح المرشّح **سورُه = `declaredDrops` تماماً** (‏لا جزءٌ منها ولا أكبر)،
      والموروثُ منها (‏`transform.dropSurah`) داخلٌ فيها.
  (ج) لكلّ سورةٍ معفاة سجلُّ `transform.timingRepair[س]` فيه شاهدا Whisper مستقلّان من تشغيلتين متمايزتين
      (‏كلُّ شاهدٍ بصيغة `witnessedAbsent`/`disputedAnchors`: {تشغيلة: سجلُّ DISPUTED_SRC_KEYS}) يُحمَّلان من مصدر
      التشغيلة (‏`pin_heard.load_witness`) ويطابقان المكتوبَ حرفاً، وبصمةُ الصوت فيهما = `audioSha256[س-1]` للفهرس،
      ويسمع كلٌّ منهما، لكلٍّ من ثلاثِ آياتٍ مسبورةٍ على الأقلّ (مختلفةٍ غيرِ متجاورة)، عند بدء الآية نصَّ آيةٍ أخرى (‏W_K كلماتٍ متّصلةً بثقة `_span_ok`، وليست من نصّ الآية نفسها).
  (د) ما سوى المعفى من الغياب يبقى محسوباً بعتبة 2%؛ والمعفى يُطبع عدداً وسوراً.

⛔ لا يمسّ عتبةَ 5% ولا حكمَ الملوح ولا الإحصاء.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

CODE = "TIMING_UNDER_REPAIR"
REASON_KEY = "timing_under_repair"
FIELD = "timingRepair"
MIN_WITNESSES = 2
MIN_PROBES = 3          # ثلاثُ آياتٍ مختلفةٍ غيرِ متجاورة، ويشهد كلٌّ منها الشاهدان معاً


def _canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _default_loader():
    import pin_heard as PH                                            # noqa: PLC0415
    return PH.load_witness


def _default_ref_words():
    import heard_gate as HG                                           # noqa: PLC0415
    return HG.disputed_ref_words


def drift_error(src, surah, probe, riwaya, ref_words):
    """سببُ ردّ المسبار عند شاهدٍ واحد، أو None إن سمع الشاهدُ عند بدء الآية نصَّ آيةٍ أخرى بثقةٍ كافية."""
    import heard_gate as HG                                           # noqa: PLC0415
    import pin_heard as PH                                            # noqa: PLC0415
    if not isinstance(probe, dict):
        return "مسبارٌ ليس سجلاً"
    a, o, t = probe.get("ayah"), probe.get("heardAyah"), probe.get("startMs")
    if type(a) is not int or type(o) is not int or type(t) is not int or t < 0:
        return f"مسبارٌ غيرُ سويّ {probe}"
    if a == o:
        return "الآيةُ المسموعةُ هي الآيةُ نفسُها — لا انحراف"
    own, oth = ref_words(riwaya, surah, a), ref_words(riwaya, surah, o)
    k = PH.W_K
    if len(own) < k or len(oth) < k:
        return "نصُّ الآية أو الآية المسموعة أقصرُ من W_K"
    own_grams = {tuple(own[i:i + k]) for i in range(len(own) - k + 1)}
    why = None
    for rec in (src.get("ayahs") or {}).values():
        win = rec.get("windowMs") or [None, None]
        tk = HG._wtoks(rec)
        for i in range(len(tk) - k + 1):
            span = tk[i:i + k]
            if not span[0][1] <= t < span[-1][2]:
                continue
            words = tuple(x[0] for x in span)
            if words in own_grams:
                why = "ما سُمع عند البدء من نصّ الآية نفسِها — لا انحراف"
            elif not any(list(words) == oth[j:j + k] for j in range(len(oth) - k + 1)):
                why = why or f"ما سُمع عند البدء «{' '.join(words)}» ليس من نصّ {surah}:{o}"
            else:
                bad = HG._span_ok(span, win)
                if bad:
                    why = bad
                else:
                    return None
    return why or f"لا يُسمع عند {t}م.ث نصُّ {surah}:{o}"


def evidence_error(idx, surah, rec, loader=None, ref_words=None):
    """سببُ ردّ سجلّ `timingRepair[س]` أو None إن اجتاز الشروطَ كلَّها (ج)."""
    import pin_heard as PH                                            # noqa: PLC0415
    loader = loader or _default_loader()
    ref_words = ref_words or _default_ref_words()
    if not isinstance(rec, dict):
        return "لا سجلَّ دليلٍ للسورة"
    probes, wits = rec.get("probes"), rec.get("witnesses")
    ayat_n = _ayah_count(surah)
    if ayat_n is None:
        return f"رقمُ السورة {surah} خارج المصحف"
    # ⭐ (قرار القائد 2026-11-10) المسابيرُ ثلاثٌ فأكثر لآياتٍ **مختلفةٍ غيرِ متجاورة**: مسبارٌ واحدٌ أو آيتان متجاورتان
    #    قد تصادفان تكراراً في الصوت. وعنقودٌ دون ذلك (‏لا يتّسع لثلاثٍ غيرِ متجاورة، أي أقلُّ من 5 آيات) بابُه
    #    `drop_ayahs` لا `drop_surah`.
    if ayat_n < 2 * MIN_PROBES - 1:
        return (f"السورة {surah} ({ayat_n} آيات) أقصرُ من أن تتّسع لـ{MIN_PROBES} مسابير غيرِ متجاورة — "
                "عنقودٌ دون ذلك بابُه drop_ayahs لا drop_surah")
    if not isinstance(probes, list) or len(probes) < MIN_PROBES:
        return f"يلزم {MIN_PROBES} مسابير على الأقلّ لآياتٍ مختلفةٍ غيرِ متجاورة (‏وجد {len(probes) if isinstance(probes, list) else 0})"
    ays = [p.get("ayah") if isinstance(p, dict) else None for p in probes]
    if any(type(a) is not int or not 1 <= a <= ayat_n for a in ays):
        return f"مسابيرُ بآياتٍ غيرِ سويّة {ays}"
    if len(set(ays)) != len(ays):
        return f"مسابيرُ مكرّرةُ الآية {sorted(ays)} — يلزم آياتٌ مختلفة"
    srt = sorted(ays)
    if any(b - a < 2 for a, b in zip(srt, srt[1:])):
        return f"مسابيرُ متجاورة {srt} — يلزم ألّا تكون آيتان منها متتاليتين"
    if not isinstance(wits, dict) or len(wits) < MIN_WITNESSES:
        return f"يلزم {MIN_WITNESSES} شاهدان من تشغيلتين متمايزتين"
    # الصيغةُ القانونية وحدَها (‏بلا أصفارٍ بادئة ولا مسافات) مع تفرّد مفاتيح القاموس = تشغيلاتٌ متمايزة؛
    # فـ«1234567» و«01234567» لا يُقبلان معاً بوصفهما تشغيلتين وهما واحدة.
    for r in wits:
        if not re.fullmatch(r"[1-9]\d{5,14}", str(r)):
            return f"معرّفُ التشغيلة {r!r} ليس رقماً قانونياً (‏تشغيلةٌ واحدة بصيغتين؟)"
    shas = idx.get("audioSha256") or []
    want = shas[surah - 1] if 1 <= surah <= len(shas) else None
    if not want:
        return "لا audioSha256 للسورة في الفهرس"
    riwaya = idx.get("riwaya") or "hafs"
    for run, written in sorted(wits.items()):
        try:
            src = loader(run, surah)
        except (SystemExit, Exception) as e:                          # noqa: BLE001
            return f"الشاهد {run}: تعذّر تحميلُه من مصدره: {str(e)[:160]}"
        if not isinstance(src, dict):
            return f"الشاهد {run}: مصدرٌ غيرُ سويّ"
        if _canon(_src_rec(written)) != _canon(_src_rec(src)):
            return f"الشاهد {run}: المكتوبُ يخالف مصدرَه حرفاً"
        if int(src.get("surah") or 0) != surah:
            return f"الشاهد {run}: لسورة {src.get('surah')} لا {surah}"
        if src.get("sha256") != want:
            return f"الشاهد {run}: بصمةُ الصوت {str(src.get('sha256'))[:8]} غيرُ audioSha256 للسورة {want[:8]}"
        if src.get("model") not in PH.W_MODELS or src.get("computeType") != "float32":
            return f"الشاهد {run}: النموذج {src.get('model')}/{src.get('computeType')} غيرُ مقبول"
        for p in probes:
            why = drift_error(src, surah, p, riwaya, ref_words)
            if why:
                return f"الشاهد {run}: {why}"
    return None


def _ayah_count(surah):
    import promote                                                    # noqa: PLC0415
    n = promote._AYAH_COUNTS
    return n[surah - 1] if isinstance(surah, int) and 1 <= surah <= len(n) else None


def _src_rec(w):
    import heard_gate as HG                                           # noqa: PLC0415
    return HG.disputed_src_rec(w)


def excused(idx, key, declared, approvals=None, loader=None, ref_words=None):
    """{count, surahs, rejected} — الغيابُ المعفى من عتبة 2% بالشروط (أ)–(ج).

    `declared`: `declaredDrops` (‏السورُ الغائبةُ كلّياً المعلَنة). `approvals`: {مفتاح: frozenset(سور)}، وإلا من الملفّ."""
    out = {"count": 0, "surahs": [], "rejected": {}}
    tr = idx.get("transform") if isinstance(idx.get("transform"), dict) else {}
    import promote                                                    # noqa: PLC0415
    codes = promote.declared_surah_codes(tr)
    cand = sorted(s for s in declared if codes.get(s) == CODE)
    if not cand:
        return out
    if approvals is None:
        approvals = promote.load_drop_approvals()
    row = approvals.get(key)
    if row != frozenset(declared):
        out["rejected"] = {s: "لا صفَّ موافقةٍ يطابق declaredDrops تماماً لهذا المفتاح" for s in cand}
        return out
    inherited = {x for x in (tr.get("dropSurah") or []) if type(x) is int}
    if not inherited <= set(declared):
        out["rejected"] = {s: f"موروثٌ خارج declaredDrops: {sorted(inherited - set(declared))}" for s in cand}
        return out
    miss = idx.get("missing") if isinstance(idx.get("missing"), dict) else {}
    ev = tr.get(FIELD) if isinstance(tr.get(FIELD), dict) else {}
    for s in cand:
        why = evidence_error(idx, s, ev.get(str(s)), loader, ref_words)
        if why:
            out["rejected"][s] = why
            continue
        out["surahs"].append(s)
    ids = [i for i in (miss.get("ids") or []) if str(i).split(":", 1)[0].isdigit()
           and int(str(i).split(":", 1)[0]) in set(out["surahs"])]
    counted = int((miss.get("byReason") or {}).get(REASON_KEY, 0) or 0)
    out["count"] = min(len(ids), counted)
    if not out["count"]:
        out["surahs"] = []
    return out


# ═══ دليلُ «نهاية المدخل» (‏kind="end") — نوعٌ صريحٌ مستقلٌّ عن دليل البدء أعلاه، لحجب آيةٍ وحدها بـ`drop_ayahs` ═══
# ⭐ (‏موافقةُ القائد 2026-11-10 بشروطه): عناقيدُ end_other عند a_abdl وnufais عطبُها أنّ **نهايةَ المدخل** المنشور تقع في
#    صوت آيةٍ أخرى، وبدؤها سليم؛ فلا يثبتها `drift_error` (‏البدء). والشروطُ حرفاً:
#    ١) شاهدا Whisper مستقلّان (‏تشغيلتان متمايزتان بصيغةٍ قانونيّة، وبصمةُ الصوت = audioSha256 للسورة في الفهرس) يسمعان
#       **عند نهاية المدخل** (‏آخرِ لحظةٍ منه: endMs−1) نصّاً **ليس من الآية** — W_K كلماتٍ متّصلةً من آيةٍ أخرى مسمّاة.
#    ٢) يُتحقَّق منه بدوالّ البوّابة نفسِها (‏`heard_gate.disputed_ref_words` · `_wtoks` · `_span_ok` · `pin_heard.W_K`)
#       على تفريغ الشاهد، ولا يُقرأ حكمٌ مكتوب.
#    ⛔ وأشدُّ من البدء في أمرٍ واحد: أيُّ W_K كلماتٍ من نصّ الآية نفسِها تُسمع عند تلك اللحظة تردّ الدليل (‏لا يكفي أن يُسمع
#       معها غيرُها). ولا يمسّ هذا البابُ `drift_error` ولا `evidence_error` ولا `excused`: دليلٌ بلا kind يبقى على حكمه القديم.
END_KIND = "end"
_RUN_RE = re.compile(r"[1-9]\d{5,14}")


def end_drift_error(src, surah, probe, riwaya, ref_words):
    """سببُ ردّ مسبار النهاية عند شاهدٍ واحد، أو None إن سمع عند آخر لحظةٍ من المدخل نصَّ `heardAyah` لا نصَّ الآية.

    `probe` = {ayah, heardAyah, endMs}: المدخلُ المنشور [بدء، endMs) فآخرُ لحظةٍ منه endMs−1، والمقطعُ يغطّيها إذا
    بدأ قبل endMs وانتهى عنده أو بعده."""
    import heard_gate as HG                                           # noqa: PLC0415
    import pin_heard as PH                                            # noqa: PLC0415
    if not isinstance(probe, dict):
        return "مسبارُ النهاية ليس سجلاً"
    a, o, e = probe.get("ayah"), probe.get("heardAyah"), probe.get("endMs")
    if type(a) is not int or type(o) is not int or type(e) is not int or e <= 0:
        return f"مسبارُ نهايةٍ غيرُ سويّ {probe}"
    if a == o:
        return "الآيةُ المسموعةُ هي الآيةُ نفسُها — لا عطبَ في النهاية"
    own, oth = ref_words(riwaya, surah, a), ref_words(riwaya, surah, o)
    k = PH.W_K
    if len(own) < k or len(oth) < k:
        return "نصُّ الآية أو الآية المسموعة أقصرُ من W_K"
    own_grams = {tuple(own[i:i + k]) for i in range(len(own) - k + 1)}
    hit, why = False, None
    for rec in (src.get("ayahs") or {}).values():
        win = rec.get("windowMs") or [None, None]
        tk = HG._wtoks(rec)
        for i in range(len(tk) - k + 1):
            span = tk[i:i + k]
            if not span[0][1] < e <= span[-1][2]:
                continue
            words = tuple(x[0] for x in span)
            if words in own_grams:
                return f"ما سُمع عند نهاية المدخل «{' '.join(words)}» من نصّ الآية نفسِها — لا يثبت أنّ النهاية في صوت غيرها"
            if not any(list(words) == oth[j:j + k] for j in range(len(oth) - k + 1)):
                why = why or f"ما سُمع عند نهاية المدخل «{' '.join(words)}» ليس من نصّ {surah}:{o}"
                continue
            bad = HG._span_ok(span, win)
            if bad:
                why = why or bad
            else:
                hit = True
    if hit:
        return None
    return why or f"لا يُسمع عند نهاية المدخل {e}م.ث نصُّ {surah}:{o}"


def end_record_error(idx, surah, ayah, rec, ref_words=None):
    """سببُ ردّ سجلّ دليل النهاية لآيةٍ واحدة **من مضمونه المكتوب** (‏بلا شبكة)، أو None.

    يُستعمل في `drop_ayahs` (‏مع تحقّق المصدر في `end_evidence_error`) وفي `promote.declared_truncated_gaps` على المرشّح."""
    import pin_heard as PH                                            # noqa: PLC0415
    ref_words = ref_words or _default_ref_words()
    if not isinstance(rec, dict) or rec.get("kind") != END_KIND:
        return f"ليس سجلَّ دليلٍ من نوع {END_KIND!r}"
    if rec.get("method") != "whisper":
        return "دليلُ النهاية لا يكون إلا بـmethod=whisper"
    probe = rec.get("probe")
    if not isinstance(probe, dict) or type(probe.get("ayah")) is not int or probe.get("ayah") != ayah:
        return f"المسبارُ لا يسمّي الآيةَ المحجوبة {surah}:{ayah} نفسَها"
    wits = rec.get("witnesses")
    if not isinstance(wits, dict) or len(wits) < MIN_WITNESSES:
        return f"يلزم {MIN_WITNESSES} شاهدان من تشغيلتين متمايزتين"
    for r in wits:
        if not _RUN_RE.fullmatch(str(r)):
            return f"معرّفُ التشغيلة {r!r} ليس رقماً قانونياً (‏تشغيلةٌ واحدة بصيغتين؟)"
    heard = rec.get("heard") if isinstance(rec.get("heard"), dict) else {}
    if str(heard.get("runId")) not in {str(r) for r in wits}:
        return f"heard.runId {heard.get('runId')!r} ليس من الشاهدَين المسمّيَين"
    shas = idx.get("audioSha256") or []
    want = shas[surah - 1] if isinstance(surah, int) and 1 <= surah <= len(shas) else None
    if not want:
        return "لا audioSha256 للسورة في الفهرس"
    riwaya = idx.get("riwaya") or "hafs"
    for run, w in sorted(wits.items()):
        src = _src_rec(w)
        if not isinstance(src, dict):
            return f"الشاهد {run}: سجلٌّ غيرُ سويّ"
        if src.get("surah") != surah:
            return f"الشاهد {run}: لسورة {src.get('surah')} لا {surah}"
        if src.get("sha256") != want:
            return f"الشاهد {run}: بصمةُ الصوت {str(src.get('sha256'))[:8]} غيرُ audioSha256 للسورة {want[:8]}"
        if src.get("model") not in PH.W_MODELS or src.get("computeType") != "float32":
            return f"الشاهد {run}: النموذج {src.get('model')}/{src.get('computeType')} غيرُ مقبول"
        why = end_drift_error(src, surah, probe, riwaya, ref_words)
        if why:
            return f"الشاهد {run}: {why}"
    return None


def end_evidence_error(idx, surah, ayah, rec, loader=None, ref_words=None):
    """سببُ ردّ دليل النهاية لآيةٍ في **الفهرس المنشور** (‏الأصلِ قبل الحجب)، أو None.

    فوق `end_record_error`: `endMs` في المسبار = نهايةُ مدخل الآية المنشور حرفاً، وكلُّ شاهدٍ مكتوبٍ يطابق مصدرَه المحمَّل
    (‏`pin_heard.load_witness`) حرفاً — فالحكمُ على المحمَّل لا على ما كتبه المُطلِق."""
    loader = loader or _default_loader()
    why = end_record_error(idx, surah, ayah, rec, ref_words)
    if why:
        return why
    ent = [x for x in (idx.get("entries") or []) if x.get("ayahId") == f"{surah}:{ayah}"]
    if len(ent) != 1:
        return f"لا مدخلَ منشورٌ وحيدٌ للآية {surah}:{ayah} — دليلُ النهاية لمدخلٍ منشورٍ فقط"
    if ent[0].get("endMs") != rec["probe"].get("endMs"):
        return f"endMs في المسبار {rec['probe'].get('endMs')} غيرُ نهاية المدخل المنشور {ent[0].get('endMs')}"
    for run, written in sorted(rec["witnesses"].items()):
        try:
            src = loader(run, surah)
        except (SystemExit, Exception) as e:                          # noqa: BLE001
            return f"الشاهد {run}: تعذّر تحميلُه من مصدره: {str(e)[:160]}"
        if not isinstance(src, dict) or _canon(_src_rec(written)) != _canon(_src_rec(src)):
            return f"الشاهد {run}: المكتوبُ يخالف مصدرَه حرفاً"
    return None
