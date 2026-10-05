#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""طريقٌ ثانٍ إلى بايتات archive.org نفسِها — **عقدةُ التخزين مباشرةً، بتحقّقٍ أقوى**.

⭐ **سببُه مقيس (‏fixV 2026-10-05 · `qalun/fakhfakh` 5bad920f):** رُدّت الترقيةُ بخمس نوافذَ
«تعذّر تفريغُها»، وعلّتُها كلُّها واحدة: `تعذّر تنزيل …/003El-imran.mp3: HTTP Error` — أي أنّ
طبقةَ `archive.org/download/…` تردّ 500 متقطّعاً، وثماني محاولاتٍ بتراجعٍ أُسّيٍّ ومحاولاتٍ
بترويسة `Range` لم تكفِ أربعةَ ملفّات. والمادّةُ سليمةٌ حاضرةٌ (‏سُبرت بياناتُها الوصفيّة
ونُزّل 033 كاملاً 12011310 بايتاً) — فالعطبُ في الطريق لا في الملفّ.

⇒ `https://archive.org/metadata/<البند>` يعطي **عقدةَ التخزين** (`server`/`d1`/`d2`) و`dir`
ومعها **حجمُ كلّ ملفّ وبصمتُه md5**. فيُطلب الملفُّ من العقدة مباشرةً — بايتاتُ البند نفسُها
بلا طبقة التحويل التي تخفق — **ويُتحقّق الناتجُ بحجم البند وبصمته**.

⛔ **وهذا تشديدٌ لا تليين:** الطريقُ البديلُ لا يُقبل منه ملفٌّ إلا إن طابق **حجمَ البند
وmd5 الناشر**، فصار القبولُ أضيقَ من قبول الطريق الأصليّ (‏الذي يقبل بالطول المعلَن وحده).
ولا يُستعمل إلا لروابط `archive.org/download/`، ولا يمسّ عتبةً ولا حكماً ولا حارساً.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
_META_CACHE = {}

_DL = re.compile(r"^https?://(?:www\.)?archive\.org/download/([^/]+)/(.+)$")


def parse_download_url(url):
    """(‏البند، مسارُ الملفّ داخله) أو None لرابطٍ ليس من `archive.org/download/`."""
    m = _DL.match(str(url or ""))
    if not m:
        return None
    return urllib.parse.unquote(m.group(1)), urllib.parse.unquote(m.group(2))


def file_record(meta, name):
    """صفُّ الملفّ في البيانات الوصفيّة (‏بالاسم كما هو) أو None."""
    for f in (meta or {}).get("files") or []:
        if isinstance(f, dict) and f.get("name") == name:
            return f
    return None


def node_candidates(meta, item, name):
    """روابطُ العقدة للملفّ نفسِه، مرتّبةً (‏`d1` ثمّ `d2` ثمّ `server`) — بلا تكرار."""
    if not meta:
        return []
    d = (meta.get("dir") or "").strip("/")
    if not d:
        return []
    hosts, out = [], []
    for k in ("d1", "d2", "server"):
        h = (meta.get(k) or "").strip()
        if h and h not in hosts:
            hosts.append(h)
    quoted = urllib.parse.quote(name)
    for h in hosts:
        out.append(f"https://{h}/{d}/{quoted}")
    return out


def expected_size_md5(meta, name):
    """(‏الحجم، md5) من بيانات البند — أو (None, None) إن لم تُعلن."""
    rec = file_record(meta, name) or {}
    size = rec.get("size")
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = None
    md5 = (rec.get("md5") or "").strip().lower() or None
    return size, md5


def matches(blob_size, blob_md5, want_size, want_md5):
    """أيُقبل ما نُزّل من العقدة؟ — **لا يُقبل إلا بمطابقةٍ معلنة** (‏دالّةٌ صِرفةٌ مختبَرة).

    ⛔ غيابُ الحجم أو البصمة في بيانات البند ⇒ **لا قبول** من هذا الطريق (‏يُترك للطريق
    الأصليّ بحارسه)، فلا تُقبل بايتاتٌ لا شاهدَ لها."""
    if not want_size or not want_md5:
        return False
    return int(blob_size) == int(want_size) and str(blob_md5).lower() == want_md5


def metadata(item, timeout=60):
    """بياناتُ البند (‏مخبَّأةٌ للعمليّة) أو None عند أيّ تعذّر."""
    if item in _META_CACHE:
        return _META_CACHE[item]
    doc = None
    try:
        rq = urllib.request.Request(f"https://archive.org/metadata/{urllib.parse.quote(item)}",
                                    headers=UA)
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            doc = json.loads(r.read().decode("utf-8", "replace"))
        if not isinstance(doc, dict) or not doc.get("files"):
            doc = None
    except Exception:                                  # noqa: BLE001
        doc = None
    _META_CACHE[item] = doc
    return doc


def fetch_verified(url, out_path, timeout=90, deadline_s=900):
    """يُنزّل الملفَّ من عقدة التخزين ويقبله **إن طابق حجمَ البند وmd5 الناشر** وحدَه.

    يُرجع (‏الرابطَ الذي نجح، الحجم) أو None — ولا يترك ملفّاً غيرَ متحقَّقٍ في مكانه."""
    import os
    import time
    got = parse_download_url(url)
    if not got:
        return None
    item, name = got
    meta = metadata(item)
    want_size, want_md5 = expected_size_md5(meta, name)
    if not (want_size and want_md5):
        return None
    for cand in node_candidates(meta, item, name):
        tmp = f"{out_path}.node.{os.getpid()}.part"
        try:
            h = hashlib.md5()                          # noqa: S324 — بصمةُ الناشر نفسُها
            n = 0
            with urllib.request.urlopen(urllib.request.Request(cand, headers=UA),
                                        timeout=timeout) as r, open(tmp, "wb") as f:
                t_end = time.monotonic() + deadline_s
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    n += len(chunk)
                    if time.monotonic() > t_end:
                        raise TimeoutError(f"تجاوز التنزيلُ {deadline_s}ث ({n} من {want_size})")
            if matches(n, h.hexdigest(), want_size, want_md5):
                os.replace(tmp, out_path)
                return cand, n
        except Exception:                              # noqa: BLE001
            pass
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return None
