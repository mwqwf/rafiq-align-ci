# -*- coding: utf-8 -*-
"""قراءةُ حقلَي ترويسة الفهرس `audioSha256` و`timingWarnings` — مصدرٌ واحد، يقبل الصيغتين ولا يبتلع الخطأ.

⛔ **سببُه (2026-10-23):** في الفهارس المنشورة (180/180) يأتي `audioSha256` قائمةً حقيقية، ويأتي `timingWarnings`
   قائمةَ قواميس في فهارس توقيت الناشر (28 فهرساً). وشيفرةٌ خارج هذا المستودع كانت تفكّهما بـ`ast.literal_eval`
   ثمّ `except Exception: []` ⇒ يرفع `literal_eval` على القائمة نفسها `ValueError` فيُبتلع، فتصير البصماتُ `[]`
   والتحذيراتُ `{}` صامتاً (فُحصت 179 فهرساً بلا فحص بصمة، وسقطت 644 سورةً محذَّرةً من الاستبعاد).

## القاعدة
* **قائمة** (الصيغة الحقيقية) ⇒ تُقبل كما هي. و**نصُّ قائمة** (JSON أو repr بايثون) ⇒ يُفكّ بصرامة. و**غيابُ الحقل**
  (`None`) ⇒ قائمةٌ فارغة. وكلُّ ما سوى ذلك ⇒ `IndexFieldError` **عاليةً** — لا `[]` صامتة.
* الفكُّ **لا يُشغّل شيفرة**: `json.loads` ثمّ `ast.literal_eval` (حرفيّاتٌ فقط) على نصٍّ صريح.
"""
from __future__ import annotations

import ast
import json


class IndexFieldError(ValueError):
    """حقلُ ترويسةٍ مفقودُ الشكل أو معطوب — يُرفع ولا يُبتلع."""


def _listish(value, name: str) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            out = json.loads(text)
        except ValueError:
            try:
                out = ast.literal_eval(text)
            except (ValueError, SyntaxError) as exc:
                raise IndexFieldError(f"{name}: نصٌّ لا يُفكّ كقائمة ({exc})") from exc
        if isinstance(out, (list, tuple)):
            return list(out)
        raise IndexFieldError(f"{name}: النصُّ يُفكّ إلى {type(out).__name__} لا قائمة")
    raise IndexFieldError(f"{name}: نوعٌ غيرُ مدعوم {type(value).__name__}")


def audio_shas(idx) -> list:
    """بصماتُ ملفّات السور كما في الترويسة: قائمةٌ (114 موضعاً أو مضغوطة) من نصٍّ أو None. فارغةٌ إن غاب الحقل."""
    if not isinstance(idx, dict):
        raise IndexFieldError("الفهرس ليس كائناً")
    out = _listish(idx.get("audioSha256"), "audioSha256")
    for i, x in enumerate(out):
        if x is not None and not isinstance(x, str):
            raise IndexFieldError(f"audioSha256[{i}]: ليست نصّاً ({type(x).__name__})")
    return [x if x else None for x in out]


def sha_by_surah(idx, present) -> dict:
    """{سورة: بصمة} للسور في `present`: قائمةٌ من 114 موضعاً (الموضعُ = رقم السورة − 1) أو مضغوطةٌ بعدد الحاضر.

    ما لا يغطّي الحاضرَ ⇒ `IndexFieldError` (لا `{}` صامتة ⇒ لا فحصَ بصمةٍ يسقط بلا إعلان).
    """
    present = sorted(present)
    shas = audio_shas(idx)
    if len(shas) == 114:
        return {s: shas[s - 1] for s in present}
    if len(shas) == len(present) and shas:
        return dict(zip(present, shas))
    raise IndexFieldError(f"audioSha256 ({len(shas)}) لا تغطّي {len(present)} سورةً حاضرة")


def full_shas(idx) -> list:
    """القائمةُ القياسية (114 موضعاً) أو `IndexFieldError`."""
    shas = audio_shas(idx)
    if len(shas) != 114:
        raise IndexFieldError(f"audioSha256: {len(shas)} موضعاً لا 114")
    return shas


def timing_warnings(idx) -> list:
    """تحذيراتُ التوقيت: قائمةُ قواميس لكلٍّ منها `surah` صحيح. فارغةٌ إن غاب الحقل. معطوبُه يُرفع."""
    if not isinstance(idx, dict):
        raise IndexFieldError("الفهرس ليس كائناً")
    out = _listish(idx.get("timingWarnings"), "timingWarnings")
    for i, w in enumerate(out):
        if not isinstance(w, dict) or "surah" not in w:
            raise IndexFieldError(f"timingWarnings[{i}]: ليس قاموساً بحقل surah")
        try:
            int(w["surah"])
        except (TypeError, ValueError) as exc:
            raise IndexFieldError(f"timingWarnings[{i}].surah غيرُ صحيح: {w['surah']!r}") from exc
    return out


def warned_surahs(idx) -> set:
    return {int(w["surah"]) for w in timing_warnings(idx)}
