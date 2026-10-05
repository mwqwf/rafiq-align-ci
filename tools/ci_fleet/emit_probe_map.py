#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""طباعة خريطة السماع أو ناتج البناء كاملًا بأجزاء مرقمة وبصمة تكشف الاقتطاع.

يُفك base64 بعد جمع أجزاء CTC_COMPACT_MAP_CHUNK بالترتيب. يجب مطابقة عددها
وحجم البايتات وSHA-256 المعلنة بين BEGIN وEND قبل اعتماد الخريطة المستخرجة.
للبناء العلامات CTC_ALIGNMENT_RESULT، وتُحفظ الحدود والملاحظات كما قاسها المحاذي؛
وجودها في السجل ليس شهادة جودة أو إذناً بدمجها أو نشرها.
لا تُسقط حقول أو آيات، ولا تُكتب artifacts أو cache أو ملفات خارج الأداة.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

MAX_BYTES = 512 * 1024
CHUNK_CHARS = 3500


def map_lines(data, surah, riwaya):
    """خريطة السبر فقط؛ رفض المخرجات الكبيرة صريح ولا يُستبدل باقتطاعها."""
    if not isinstance(data, dict) or data.get("surah") != surah or data.get("riwaya") != riwaya:
        raise ValueError("هوية الخريطة لا تطابق السورة والرواية المطلوبتين")
    if data.get("engine") != "ctc-heardmap-1" or data.get("entries") != []:
        raise ValueError("المخرج ليس سبر خريطة فقط؛ لا يجوز إخراج مداخل محاذاة بهذا المسار")
    if not isinstance(data.get("heardMap"), dict) or not data["heardMap"]:
        raise ValueError("خريطة السماع غائبة أو فارغة")
    if not re.fullmatch(r"[0-9a-f]{64}", str(data.get("sha256") or "")):
        raise ValueError("بصمة مصدر الصوت الكاملة غائبة")
    yield from payload_lines(data, "CTC_COMPACT_MAP")


def alignment_lines(data, surah, riwaya, url, source_sha256):
    """ناتج المحاذي كما قاسه، مع فحص الهوية؛ لا يحكم بجودة الحدود أو يغيّرها."""
    if not isinstance(data, dict) or data.get("surah") != surah or data.get("riwaya") != riwaya:
        raise ValueError("هوية المحاذاة لا تطابق السورة والرواية المطلوبتين")
    if (not re.fullmatch(r"[0-9a-f]{64}", str(source_sha256 or ""))
            or data.get("sha256") != source_sha256 or data.get("fileRef") != url):
        raise ValueError("مصدر المحاذاة أو بصمته يخالف المصدر المقيس المطلوب")
    heard = data.get("heardMap")
    entries = data.get("entries")
    if (data.get("engine") != "ctc-heardmap-1" or not isinstance(heard, dict)
            or not heard or not isinstance(entries, list) or len(entries) != len(heard)):
        raise ValueError("المخرج ليس بناء محاذاة مع خريطة سماع كاملة")
    expected = list(range(len(entries)))
    if ([row.get("ayahIdx") if isinstance(row, dict) else None for row in entries] != expected
            or set(heard) != {str(k + 1) for k in expected}):
        raise ValueError("ترتيب آيات المحاذاة أو خريطة السماع غير كامل")
    # الحدود الغائبة والملاحظات محفوظة أيضاً؛ أداة الدمج والحراس ترفض المرشح الناقص.
    yield from payload_lines(data, "CTC_ALIGNMENT_RESULT")


def payload_lines(data, prefix):
    """المخرج كاملاً بأجزاء محدودة؛ الحجم الزائد خطأ صريح قبل أول علامة."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise ValueError(f"الخريطة تتجاوز {MAX_BYTES} بايت؛ لم تُطبع نسخة مبتورة")
    digest = hashlib.sha256(payload).hexdigest()
    encoded = base64.b64encode(payload).decode("ascii")
    chunks = [encoded[offset:offset + CHUNK_CHARS] for offset in range(0, len(encoded), CHUNK_CHARS)]
    yield f"{prefix}_BEGIN bytes={len(payload)} sha256={digest} chunks={len(chunks)}"
    for position, chunk in enumerate(chunks, 1):
        yield f"{prefix}_CHUNK {position}/{len(chunks)} {chunk}"
    yield f"{prefix}_END sha256={digest}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surah", type=int, required=True, choices=range(1, 115))
    parser.add_argument("--riwaya", required=True)
    parser.add_argument("--alignment", action="store_true", help="حفظ ناتج البناء كاملاً دون شهادة جودة")
    parser.add_argument("--url", default="")
    parser.add_argument("--source-sha256", default="")
    args = parser.parse_args()
    source = Path("out") / (f"s{args.surah:03d}.json" if args.alignment else f"heard_s{args.surah:03d}.json")
    # يُقرأ الملف المحدد وحده؛ الصوت والتقرير النصي لا يُضمّان إلى الخريطة.
    data = json.loads(source.read_text(encoding="utf-8"))
    lines = (alignment_lines(data, args.surah, args.riwaya, args.url, args.source_sha256)
             if args.alignment else map_lines(data, args.surah, args.riwaya))
    for line in lines:
        print(line, flush=True)


if __name__ == "__main__":
    main()
