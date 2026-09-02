# -*- coding: utf-8 -*-
"""يبحث عن نسخة سليمة لسورةٍ مبتورة عند خوادم mp3quran الأخرى.

المصدر واحد منطقياً (‏mp3quran) لكنه **خوادم كثيرة**، وقد يكون البتر في
نسخة خادمٍ بعينه لا في التسجيل نفسه. فنجرّب الخوادم كلها بنفس المسار،
ونقبل ما وافقت مدتُه طول السورة.

⛔ لا يكتب في الدلو شيئاً بذاته — يبحث ويقيس ويطبع الترشيح. والنسخ خطوةٌ
   تالية بأمر، وإلى مسار `fix` لا فوق الأصل.

    python3 find_intact_surah.py --riwaya hafs --reciter 3siri --surah 9
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

import requests

sys.path.insert(0, os.environ.get("RAFIQ_TOOLS",
                                  "/root/QuranRafiq/tools/alignment"))
from common import load_index, load_text, norm  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq asset mirror)"}


def words_of(riwaya, sn):
    text, index = load_text(riwaya), load_index()
    s = next(x for x in index["surahs"] if x["n"] == sn)
    return sum(len(norm(text[s["start"] + i]).split())
               for i in range(s["ayahs"]))


def duration_ms(body):
    fd, p = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", p],
            capture_output=True, text=True, timeout=120)
        return int(float(r.stdout.strip()) * 1000)
    except Exception:
        return None
    finally:
        try:
            os.remove(p)
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--source", required=True, help="رابط مجلد القارئ الأصلي")
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--rate", type=float, required=True, help="م.ث/كلمة للقارئ")
    ap.add_argument("--servers", type=int, default=20)
    a = ap.parse_args()

    w = words_of(a.riwaya, a.surah)
    expect = a.rate * w
    print("{}/{} سورة {} — {} كلمة · المتوقع {:.0f}ث".format(
        a.riwaya, a.reciter, a.surah, w, expect / 1000))

    m = re.match(r"(https?://)server(\d+)(\.mp3quran\.net/.*)", a.source)
    if not m:
        sys.exit("⛔ المصدر ليس بنمط serverN.mp3quran.net — لا بديل آلي.")
    scheme, _, tail = m.groups()
    best = []
    for i in range(1, a.servers + 1):
        url = "{}server{}{}{:03d}.mp3".format(scheme, i, tail, a.surah)
        try:
            h = requests.head(url, headers=UA, timeout=20,
                              allow_redirects=True)
            if h.status_code != 200:
                continue
            size = int(h.headers.get("Content-Length") or 0)
        except Exception:
            continue
        try:
            body = requests.get(url, headers=UA, timeout=(20, 900)).content
        except Exception:
            continue
        ms = duration_ms(body)
        if not ms:
            continue
        ratio = ms / max(expect, 1)
        mark = "✅ مرشَّح" if 0.85 <= ratio <= 1.2 else "· "
        print("  {} server{}: {:.0f}ث · {:,} بايت · نسبة {:.2f}".format(
            mark, i, ms / 1000, size, ratio))
        if 0.85 <= ratio <= 1.2:
            best.append((abs(1 - ratio), i, url, size, ms))
    if not best:
        print("\n⛔ لا نسخة سليمة في خوادم mp3quran — البتر في التسجيل نفسه "
              "لا في نسخة خادم. الطريق: مصدر آخر (archive.org) أو إسقاط "
              "السورة لهذا القارئ.")
        return
    best.sort()
    _, i, url, size, ms = best[0]
    print("\n✅ الأفضل: server{} — {:.0f}ث · {:,} بايت\n   {}".format(
        i, ms / 1000, size, url))


if __name__ == "__main__":
    main()
