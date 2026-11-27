# -*- coding: utf-8 -*-
"""نافذةُ مدى السورة لخريطة السماع في heard_pub — لملفٍّ تبدأ فيه السورةُ بعد مقدّمةٍ/سورٍ سابقة.

⛔ العطبُ المقيس (2026-11-27 · laghdaf س85، المصدر المسجَّل chinguit_01/60.ogg): ملفٌّ متعدّد السور تبدأ السورةُ فيه عند 138ث؛
`ctc_heard_map --probe` يفكّ الملفَّ كلَّه فتقع مراسي الآيات 9–21 على ظهورٍ لاحقٍ في سورٍ تالية (‏−1366ث) — وهو عطبُ خريطةٍ لا فهرس.

⚖️ لا تُقاس الآياتُ بالفهرس نفسه: لا يؤخذ منه إلا **غلافُ السورة** (‏أصغرُ بدءٍ وأكبرُ نهاية) ثم يُوسَّع بهامشٍ (70ث > أكبر إزاحة حقن 60ث)؛ مراسي الآيات تأتي
من الصوت وحده، فسورةٌ مُزاحةٌ كلُّها ±5ث أو ±60ث تبقى داخل النافذة فيظهر انحرافُها كاملاً (لا إخفاء). وما كان بدؤُه < 20ث لا نافذةَ له (‏يبقى السلوكُ
كما كان حرفاً).
"""
from __future__ import annotations

MARGIN_MS = 70_000
LEAD_MS = 20_000


def span_window(ayahs: dict, margin_ms: int = MARGIN_MS, lead_ms: int = LEAD_MS):
    """`ayahs`: {رقم: (بدء، نهاية، ...)} لسورةٍ واحدة ⇒ (بدء النافذة، نهايتها) بالم.ث، أو None إن لا نافذة."""
    starts = [v[0] for v in ayahs.values() if v and v[0] is not None]
    if not starts:
        return None
    lo = min(starts)
    if lo < lead_ms:
        return None
    hi = max((v[1] if len(v) > 1 and v[1] is not None else v[0]) for v in ayahs.values() if v and v[0] is not None)
    return max(0, int(lo) - margin_ms), int(hi) + margin_ms
