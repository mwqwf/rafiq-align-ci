"""مصدر مسجّل لسورة بعينها؛ الاسم الرقمي لا يثبت محتوى التسجيل."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

REGISTRY = Path(__file__).with_name("source_overrides.json")


def registered_source(riwaya, reciter, surah, rows=None):
    rows = json.loads(REGISTRY.read_text(encoding="utf-8")) if rows is None else rows
    if not isinstance(rows, list):
        raise ValueError("سجل المصادر ليس قائمة")
    selected = [r for r in rows if isinstance(r, dict)
                and r.get("riwaya") == riwaya and r.get("reciter") == reciter
                and str(r.get("surah")) == str(surah)]
    if len(selected) != 1:
        raise ValueError(f"لا يوجد مصدر مسجّل وحيد ({len(selected)})")
    row = selected[0]
    if not str(row.get("evidence") or "").strip():
        raise ValueError("المصدر بلا دليل قياس")
    explicit = row.get("url")
    url = explicit or str(row.get("base") or "").rstrip("/") + f"/{int(surah):03d}.mp3"
    parts = urlsplit(url)
    if (parts.scheme != "https" or not parts.netloc or parts.username
            or parts.password or parts.fragment or re.search(r"[\s{}]", url)):
        raise ValueError("المصدر ليس رابط HTTPS صريحاً صالحاً")
    sha = row.get("audio_sha256")
    if explicit and not re.fullmatch(r"[0-9a-f]{64}", str(sha or "")):
        raise ValueError("الرابط الصريح يحتاج بصمة صوت كاملة مقيسة")
    if sha is not None and not re.fullmatch(r"[0-9a-f]{64}", str(sha)):
        raise ValueError("بصمة الصوت غير صالحة")
    return dict(row, url=url)


# قائمةُ مضيفين صريحة (بلا أحرف بدل): المضيفُ يطابق تماماً والمسار يبدأ بالبادئة، وhttps فقط.
SPLICE_ALLOWED_SOURCES = (
    ("archive.org", "/download/"),
    ("download.quranicaudio.com", "/quran/"),
)


def registered_splice_source(riwaya, reciter, surah, rows=None):
    """مصدر registered_splice: رابط https صريح على مضيفٍ في القائمة + بصمة كاملة (وإلا ValueError)."""
    row = registered_source(riwaya, reciter, surah, rows)
    if not row.get("audio_sha256") or not re.fullmatch(r"[0-9a-f]{64}", str(row["audio_sha256"])):
        raise ValueError("يلزم رابط صريح وبصمة كاملة في السجلّ")
    parts = urlsplit(row["url"])
    if parts.scheme != "https" or parts.port is not None or not any(
            parts.hostname == h and parts.path.startswith(p) for h, p in SPLICE_ALLOWED_SOURCES):
        raise ValueError("مضيف المصدر خارج القائمة المسموحة")
    return row


def assert_audio_sha(path, expected):
    """يرفض الملف إن اختلفت بصمته عن المسجَّلة."""
    got = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if got != expected:
        raise ValueError("تغيرت بصمة المصدر")
    return got
