#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سبرُ مصادرَ خارج archive.org — قارئٌ محض (2026-09-30).

⭐ سببُه: «ضاعفوا البحث» عن نور العكري وماعونه بحث في archive.org وحده، والويبُ فيه
مضيفون آخرون (equran.me · alkabbah.com · lifebyislam.com). وبيئةُ الجلسة تحجبهم، والعدّاءُ لا.

    python tools/ci_fleet/web_probe.py <رابط صفحة أو ملفّ mp3> [...]
      · صفحةٌ ⇒ تُطبع روابطُ الصوت فيها (‏mp3/m4a) مع ما يجاورها من نصّ.
      · ملفٌّ ⇒ يُنزَّل ويُطبع: الحجم · المدّة (ffprobe) · البصمة.

⚖️ لا يكتب في الدلو ولا يحكم: المقارنةُ بمدّة المراجع وبالتسجيل المفهرَس لمن يقرأ الأرقام.
"""
import hashlib
import html
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
AUDIO = re.compile(r"""https?://[^\s"'<>]+?\.(?:mp3|m4a)(?:\?[^\s"'<>]*)?""", re.I)


def get(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def probe_audio(url):
    data, ct = get(url, timeout=300)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(data)
        p = f.name
    try:
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", p], capture_output=True, text=True).stdout.strip()
    finally:
        os.unlink(p)
    print(f"🎧 {url}\n   {len(data):,} بايت · {ct} · مدّة {dur}ث · sha256 {hashlib.sha256(data).hexdigest()[:16]}")


def probe_page(url):
    data, ct = get(url)
    txt = data.decode("utf-8", "replace")
    links = sorted(set(html.unescape(m) for m in AUDIO.findall(txt)))
    print(f"📄 {url} · {ct} · {len(txt):,} حرفاً · روابطُ صوت: {len(links)}")
    for L in links[:200]:
        i = txt.find(L)
        ctx = re.sub(r"<[^>]+>|\s+", " ", txt[max(0, i - 160):i])[-90:]
        print(f"   {L}\n      ‹{ctx.strip()}›")
    if not links:
        for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]{0,60})', txt):
            if re.search(r"نور|ماعون|024|107|mp3", m.group(0)):
                print(f"   رابط: {html.unescape(m.group(1))} ‹{m.group(2).strip()}›")


def main():
    for u in sys.argv[1:]:
        try:
            if re.search(r"\.(mp3|m4a)(\?|$)", u, re.I):
                probe_audio(u)
            else:
                probe_page(u)
        except Exception as ex:                        # noqa: BLE001
            print(f"⛔ {u}: {type(ex).__name__}: {str(ex)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
