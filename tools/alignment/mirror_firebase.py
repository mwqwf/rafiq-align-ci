# -*- coding: utf-8 -*-
"""مرآة fallback لفهارس التوقيتات على Firebase Storage منبر (mxqp) — لأن r2.dev
يحجبه بعض مزودي الاتصال (وقع فعلاً لهاتف المالك 2026-08-31، كما وقع لمنبر).

المسار يطابق قاعدة fallback الصور: quran/timings/{riwaya}/{reciter}.jz
python mirror_firebase.py --index work/timings_qalun_husary_qalun.jz
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request

from common import read_jz

BUCKET = "mxqp-8d1e8.firebasestorage.app"
# آلية توثيق firebase-tools المجربة في migrate.py منبر (عميل CLI الرسمي العام)
_CLIENT = ("563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com",
           "j9iVZfS8kkCEFUPaAeJV0sAi")


def token():
    cfg = json.load(open(os.path.expanduser("~/.config/configstore/firebase-tools.json")))
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": cfg["tokens"]["refresh_token"],
        "client_id": _CLIENT[0], "client_secret": _CLIENT[1]}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data), timeout=60)
    return json.load(r)["access_token"]


def upload(path, object_name, ctype, tok):
    url = (f"https://firebasestorage.googleapis.com/v0/b/{BUCKET}/o"
           f"?name={urllib.parse.quote(object_name, safe='')}")
    body = open(path, "rb").read()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": "Bearer " + tok, "Content-Type": ctype})
    meta = json.load(urllib.request.urlopen(req, timeout=120))
    return meta


def public_url(object_name):
    return (f"https://firebasestorage.googleapis.com/v0/b/{BUCKET}/o/"
            f"{urllib.parse.quote(object_name, safe='')}?alt=media")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    args = ap.parse_args()
    ti = read_jz(args.index)
    tok = token()
    obj = f"quran/timings/{ti['riwaya']}/{ti['reciterId']}.jz"
    upload(args.index, obj, "application/gzip", tok)
    size = os.path.getsize(args.index)
    print(f"مرآة: {obj} ({size//1024}ك.ب)")

    # مانيفست المرآة بنفس صيغة R2
    mobj = "quran/timings/manifest.json"
    try:
        cur = json.load(urllib.request.urlopen(public_url(mobj), timeout=30))
    except Exception:
        cur = {"version": 1, "indexes": []}
    row = {"riwaya": ti["riwaya"], "reciterId": ti["reciterId"],
           "entries": len(ti["entries"]), "updatedTs": int(time.time() * 1000)}
    cur["indexes"] = [x for x in cur["indexes"]
                      if not (x["riwaya"] == row["riwaya"] and x["reciterId"] == row["reciterId"])]
    cur["indexes"].append(row)
    cur["updated"] = row["updatedTs"]
    tmp = args.index + ".manifest.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False)
    upload(tmp, mobj, "application/json", tok)
    os.remove(tmp)

    # تحقق القراءة العامة بالحجم
    got = urllib.request.urlopen(public_url(obj), timeout=60).read()
    print("تحقق عام:", "✅" if len(got) == size else f"❌ {len(got)} ≠ {size}")
    print("رابط الفهرس:", public_url(obj))


if __name__ == "__main__":
    main()
