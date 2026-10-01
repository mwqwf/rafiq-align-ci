"""أسماء الحروف المقطعة لمدخل المحاذاة وحده؛ أصل القرآن يبقى كما هو."""
from __future__ import annotations

from common import norm

_OPENERS = {
    **{s: "الم" for s in (2, 3, 29, 30, 31, 32)},
    7: "المص", 13: "المر", 19: "كهيعص", 20: "طه",
    **{s: "الر" for s in (10, 11, 12, 14, 15)},
    26: "طسم", 28: "طسم", 27: "طس", 36: "يس", 38: "ص",
    **{s: "حم" for s in (40, 41, 42, 43, 44, 45, 46)},
    50: "ق", 68: "ن",
}
_NAMES = dict(zip("المرصكهيعطسحقن", (
    "الف", "لام", "ميم", "را", "صاد", "كاف", "ها", "يا",
    "عين", "طا", "سين", "حا", "قاف", "نون",
)))


def alignment_text(surah: int, ayah: int, canonical: str) -> str:
    """يوسع مطلعًا معلومًا فقط، لا كلمةً مشابهة داخل آيةٍ أخرى.

    الموضع والنص كلاهما حارسان: التطبيع والتهجئة مخرجان جديدان للمحاذي،
    لا تعديل للأصل ولا تفريغ مولد، والثقة والبوابات الصوتية باقية.
    """
    normalized = norm(canonical)
    letters = "عسق" if (surah, ayah) == (42, 2) else (
        _OPENERS.get(surah) if ayah == 1 else None)
    if not letters:
        return normalized
    first, separator, rest = normalized.partition(" ")
    if first != letters:
        raise ValueError(f"مطلع {surah}:{ayah} لا يطابق الحروف المرجعية المتوقعة")
    spoken = " ".join(_NAMES[ch] for ch in letters)
    return spoken + (separator + rest if separator else "")
