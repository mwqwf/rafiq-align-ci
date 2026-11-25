#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سياسة مصادر المراسي المساندة الخارجية — لا تُرقّى حدودها وحدها.

voltarostudio/quran-word-timings-mp3quran (CC-BY 4.0) مصدرُ **مراسٍ مساندة**
فقط. ⛔ لا تُرقّى أي بداية أو نهاية مأخوذة منه إلى فهرس منشور إلا بعد أن
يشهد شاهدا Whisper (مثل medium وlarge-v3) على الحدّ ضمن W_AGREE_MS (300م.ث)
مع القيمة المقترحة ومع بعضهما. العتبة 5٪ وصفر الاتهام الكاذب لا تُمسّ.

لا شبكة هنا ولا Whisper مدفوع: الدالة تحكم على أرقام الشهود المسجَّلة.
النسبة المطلوبة عند أي استعمال: ATTRIBUTION.
"""
from __future__ import annotations

SOURCE_ID = "voltarostudio/quran-word-timings-mp3quran"
SOURCE_URL = "https://huggingface.co/datasets/voltarostudio/quran-word-timings-mp3quran"
LICENSE = "CC-BY 4.0"
# نصّ النسبة الذي أعلنه الناشر، مع ترجمة عربية للعرض.
ATTRIBUTION = (
    "توقيتات الكلمات: quran-word-align من Voltaro Studio (CC-BY 4.0)، "
    "على تسجيلات mp3quran.net. "
    "Word timings: quran-word-align by Voltaro Studio (CC-BY 4.0), "
    "on recordings from mp3quran.net."
)
# يطابق pin_heard.W_AGREE_MS — اختبار العقد يمنع الانحراف.
W_AGREE_MS = 300
SOURCE_ALIASES = frozenset({
    SOURCE_ID,
    "voltarostudio",
    "quran-word-align",
    "voltarostudio/quran-word-align",
    SOURCE_URL,
    "https://huggingface.co/datasets/voltarostudio/quran-word-timings-mp3quran",
})


def is_external_anchor_source(name) -> bool:
    s = str(name or "").strip().lower().rstrip("/")
    if not s:
        return False
    aliases = {a.lower().rstrip("/") for a in SOURCE_ALIASES}
    if s in aliases:
        return True
    return "voltarostudio" in s or s.endswith("quran-word-align")


def _is_whisper(model) -> bool:
    return "whisper" in str(model or "").strip().lower()


def _ms(value, key="startMs"):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bound_block_reason(record: dict) -> str | None:
    """سبب رفض ترقية حدٍّ واحد، أو None إن جاز. لا يُرخى 300م.ث."""
    src = record.get("source") or record.get("anchorSource")
    if not is_external_anchor_source(src):
        return None
    ayah = record.get("ayahId") or record.get("ayah") or "?"
    start = _ms(record.get("startMs"))
    if start is None:
        return f"{ayah}: حدٌّ من {SOURCE_ID} بلا startMs — لا يُرقّى"
    wits = [w for w in (record.get("witnesses") or []) if isinstance(w, dict)]
    whisper = [w for w in wits if _is_whisper(w.get("model") or w.get("witness"))]
    if len(whisper) < 2:
        return (f"{ayah}: حدٌّ من {SOURCE_ID} لا يُرقّى إلا بعد شاهدَي Whisper "
                f"ضمن {W_AGREE_MS}م.ث (وُجد {len(whisper)})")
    starts = []
    for i, w in enumerate(whisper[:2], 1):
        ws = _ms(w.get("startMs"))
        if ws is None:
            return f"{ayah}: الشاهد {i} بلا startMs — لا يُرقّى"
        if abs(ws - start) > W_AGREE_MS:
            return (f"{ayah}: شاهد Whisper {w.get('model') or i} عند {ws} بعيدٌ "
                    f"عن الحدّ {start} (>{W_AGREE_MS}م.ث) — لا يُرقّى")
        starts.append(ws)
    if abs(starts[0] - starts[1]) > W_AGREE_MS:
        return (f"{ayah}: شاهدا Whisper يختلفان {starts} (>{W_AGREE_MS}م.ث) — لا يُرقّى")
    end = _ms(record.get("endMs"))
    if end is not None:
        ends = []
        for i, w in enumerate(whisper[:2], 1):
            we = _ms(w.get("endMs"))
            if we is None:
                return f"{ayah}: الحدّ له endMs والشاهد {i} بلا نهاية — لا يُرقّى"
            if abs(we - end) > W_AGREE_MS:
                return (f"{ayah}: نهاية الشاهد {w.get('model') or i} عند {we} بعيدةٌ "
                        f"عن الحدّ {end} (>{W_AGREE_MS}م.ث) — لا يُرقّى")
            ends.append(we)
        if abs(ends[0] - ends[1]) > W_AGREE_MS:
            return (f"{ayah}: شاهدا Whisper يختلفان في النهاية {ends} "
                    f"(>{W_AGREE_MS}م.ث) — لا يُرقّى")
    return None


def _records(idx) -> list:
    raw = (idx or {}).get("externalAnchors")
    if raw is None:
        return []
    if isinstance(raw, dict):
        out = []
        for k, v in raw.items():
            if isinstance(v, dict):
                out.append({**v, "ayahId": v.get("ayahId") or k})
        return out
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    return []


def promotion_block_reason(idx) -> str | None:
    """سبب حجب ترقية الفهرس لأجل مراسٍ خارجية غير مشهودة، أو None."""
    for rec in _records(idx):
        why = bound_block_reason(rec)
        if why:
            return why
    return None
