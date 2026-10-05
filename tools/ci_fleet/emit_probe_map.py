#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""طباعة خريطة السماع كاملة في سجل Actions بأجزاء مرقمة وبصمة تكشف أي اقتطاع.

يُفك base64 بعد جمع أجزاء CTC_COMPACT_MAP_CHUNK بالترتيب. يجب مطابقة عددها
وحجم البايتات وSHA-256 المعلنة بين BEGIN وEND قبل اعتماد الخريطة المستخرجة.
لا تُسقط حقول أو آيات، ولا تُكتب artifacts أو cache أو ملفات خارج الأداة.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
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
    if not isinstance(data.get("sha256"), str) or len(data["sha256"]) != 64:
        raise ValueError("بصمة مصدر الصوت الكاملة غائبة")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise ValueError(f"الخريطة تتجاوز {MAX_BYTES} بايت؛ لم تُطبع نسخة مبتورة")
    digest = hashlib.sha256(payload).hexdigest()
    encoded = base64.b64encode(payload).decode("ascii")
    chunks = [encoded[offset:offset + CHUNK_CHARS] for offset in range(0, len(encoded), CHUNK_CHARS)]
    yield f"CTC_COMPACT_MAP_BEGIN bytes={len(payload)} sha256={digest} chunks={len(chunks)}"
    for position, chunk in enumerate(chunks, 1):
        yield f"CTC_COMPACT_MAP_CHUNK {position}/{len(chunks)} {chunk}"
    yield f"CTC_COMPACT_MAP_END sha256={digest}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surah", type=int, required=True, choices=range(1, 115))
    parser.add_argument("--riwaya", required=True)
    args = parser.parse_args()
    source = Path("out") / f"heard_s{args.surah:03d}.json"
    # يُقرأ الملف المحدد وحده؛ الصوت والتقرير النصي لا يُضمّان إلى الخريطة.
    data = json.loads(source.read_text(encoding="utf-8"))
    for line in map_lines(data, args.surah, args.riwaya):
        print(line, flush=True)


if __name__ == "__main__":
    main()
