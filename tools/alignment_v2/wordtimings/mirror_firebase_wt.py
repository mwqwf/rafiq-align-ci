# -*- coding: utf-8 -*-
"""مرآة Firebase للتوقيتات الكلمية — نفس آلية tools/alignment/mirror_firebase.py
(تُستورد ولا تُعدَّل) على المسار الذي يقرأه التطبيق (WordTimingsRepository):
    quran/wordtimings/{riwaya}/{reciterId}.jz
ويتحقق بعد الرفع بقراءة عامة ومطابقة الحجم وsha256.

python mirror_firebase_wt.py --file out/wordtimings_husary_qalun.jz
"""
import argparse
import hashlib
import os
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(_HERE)), "alignment"))

from common import read_jz  # noqa: E402
from mirror_firebase import public_url, token, upload  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    args = ap.parse_args()
    doc = read_jz(args.file)
    obj = "quran/wordtimings/%s/%s.jz" % (doc["riwaya"], doc["reciterId"])
    raw = open(args.file, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    upload(args.file, obj, "application/gzip", token())
    got = urllib.request.urlopen(public_url(obj), timeout=120).read()
    ok = len(got) == len(raw) and hashlib.sha256(got).hexdigest() == sha
    print("مرآة Firebase: %s · %d بايت · sha256 %s · آيات %d" % (obj, len(raw), sha[:16], len(doc["entries"])))
    print("تحقق القراءة العامة: %s (حجم %d مقابل %d)" % ("✅" if ok else "❌", len(got), len(raw)))
    print("الرابط:", public_url(obj))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
