#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختيارُ مصفوفة فحص المصدر المسجّل، مع منع إعادة ما نجح بلا سبب."""
from __future__ import annotations

ALLOWED = ("openers", "census", "rs1", "rs2", "rs3", "rs4", "heard")


def selected_checks(raw: str, has_parent: bool) -> list[str]:
    """يعيد المجموعة المطلوبة بعد تحقق مغلق؛ الفارغ يحفظ السلوك الكامل القديم."""
    if not str(raw or "").strip():
        return list(ALLOWED if has_parent else ALLOWED[:-1])
    checks = [part.strip() for part in str(raw).split(",") if part.strip()]
    if not checks or len(checks) != len(set(checks)):
        raise ValueError("فحوص فارغة أو مكررة")
    bad = [check for check in checks if check not in ALLOWED]
    if bad:
        raise ValueError(f"فحوص غير مسموحة: {bad}")
    if "heard" in checks and not has_parent:
        raise ValueError("heard يتطلب أصلاً مثبتاً")
    return checks
