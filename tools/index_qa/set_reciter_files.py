#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يضع حقل `files` (114 اسمَ ملفّ مصدرٍ) في **مدخلٍ واحدٍ** من `catalog/reciters.json`.

    python tools/index_qa/set_reciter_files.py --self-test
    python tools/index_qa/set_reciter_files.py --riwaya qalun --reciter akri_qalun \
        --map 106=108.mp3,107=106.mp3,108=107.mp3            # عرضٌ فقط
    ... --yes                                                  # يكتب (بعد نسخةٍ احتياطية)

**لماذا:** قارئٌ تختلف أسماءُ ملفّات مصدره عن رقم السورة (akri_qalun في 106–108: الملفّ
`106.mp3` هو الماعون 107 · `107.mp3` الكوثر 108 · `108.mp3` قريش 106). التطبيق يبني رابطَ
السورة `base + SSS.mp3` ما لم يحمل الدليلُ اسماً صريحاً في `files` (‏`Reciter.surahUrl`)،
وبلا فهرسٍ يثبت الملفَّ يُسمع سورةٌ أخرى. وصيغةُ الحقل كما يقرؤها التطبيق
(‏`ReciterDirectory.parseAll`) وكما تقرؤه `tools/alignment/batch_run.py`: **قائمةٌ من 114 نصّاً،
الفهرسُ سورة−1** (‏ولا يقبل batch_run غيرَ 114).

## الحُرّاس (كلٌّ منها يُختبر بحالةٍ سالبة في `--self-test`)
1. المدخلُ موجودٌ بالرواية والمعرّف، ولا `files` سابقةَ تخالف المطلوب (لا استبدالَ صامت).
2. الأسماءُ الافتراضية `SSS.mp3` لما لم يُذكر في `--map`؛ ولا اسمَ فارغاً ولا مكرَّراً ولا فيه `/`.
3. ⭐ **اتّفاقٌ مع الفهرس المنشور**: كلُّ مدخلٍ في `timings/<رواية>/<قارئ>.jz` له `fileRef` يجب أن
   يساوي `base + files[سورة−1]` — فالاسمُ الصحيح ما حوذي عليه فعلاً لا ما قيل.
4. **كلُّ الأربعة عشر ومئةٌ بـHEAD 200** عند المصدر.
5. ⛔ **لا يتغيّر في الكتالوج إلا الحقل**: بايتات الكتالوج الجديد بعد نزع الحقل المُدرَج تساوي
   القديمَ حرفاً (‏التسلسلُ المدمج نفسُه يعيد الكتالوجَ الحيَّ بايتاً ببايت).
6. نسخةٌ احتياطيةٌ للبايتات الأصلية في `catalog/backups/` (‏`IfNoneMatch=*`) **قبل** الكتابة،
   وبصمةُ الكتالوج الحيّ تُعاد قراءتُها قبل الرفع (لا كتابةَ فوق تعديلٍ متزامن)، ثمّ قراءةٌ راجعةٌ.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import copy
import datetime as dt
import gzip
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CATALOG_KEY = "catalog/reciters.json"
BACKUP_PREFIX = "catalog/backups/"
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass


def dumps(cat) -> bytes:
    """التسلسلُ المعتمد للكتالوج (‏مدمجٌ بلا ASCII-escape) — يطابق الحيَّ بايتاً ببايت."""
    return json.dumps(cat, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def parse_map(text: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for part in filter(None, (p.strip() for p in (text or "").split(","))):
        k, _, v = part.partition("=")
        s = int(k)
        if not 1 <= s <= 114:
            raise ValueError(f"رقمُ سورةٍ خارج 1..114: {s}")
        if s in out:
            raise ValueError(f"سورةٌ مكرَّرةٌ في --map: {s}")
        out[s] = v.strip()
    return out


def build_files(mapping: dict[int, str]) -> list[str]:
    files = [mapping.get(s, f"{s:03d}.mp3") for s in range(1, 115)]
    for s, n in enumerate(files, 1):
        if not n or "/" in n or n != n.strip():
            raise ValueError(f"اسمُ ملفٍّ غيرُ صالح للسورة {s}: {n!r}")
    if len(set(files)) != 114:
        dup = sorted({n for n in files if files.count(n) > 1})
        raise ValueError(f"أسماءٌ مكرَّرة في files: {dup}")
    return files


def find_row(cat, riwaya: str, reciter: str):
    rows = [x for r in cat.get("riwayat", []) if r.get("id") == riwaya
            for x in r.get("reciters", []) if x.get("id") == reciter]
    if len(rows) != 1:
        raise ValueError(f"{riwaya}/{reciter}: وُجد {len(rows)} مدخلاً لا واحد")
    return rows[0]


def apply(cat, riwaya: str, reciter: str, files: list[str]):
    """نسخةٌ من الكتالوج وفيها `files` للمدخل المطلوب وحده. تُرفض `files` سابقةٌ مختلفة."""
    new = copy.deepcopy(cat)
    row = find_row(new, riwaya, reciter)
    if "files" in row and row["files"] != files:
        raise ValueError(f"{riwaya}/{reciter} فيه files سابقةٌ تخالف المطلوب — لا استبدالَ صامت")
    row["files"] = files
    return new


def index_mismatches(entries, base: str, files: list[str]) -> list[str]:
    """مداخلُ الفهرس التي يخالف `fileRef` فيها `base + files[سورة−1]`."""
    bad = []
    for e in entries:
        ref = e.get("fileRef")
        if not ref:
            continue
        s = int(str(e["ayahId"]).split(":")[0])
        want = base + files[s - 1]
        if ref != want:
            bad.append(f"{e['ayahId']}: الفهرس {ref} ≠ {want}")
    return bad


def only_files_changed(old_raw: bytes, new_cat, riwaya: str, reciter: str) -> bool:
    """بايتات الجديد بعد نزع الحقل المُدرَج تساوي القديمَ حرفاً."""
    stripped = copy.deepcopy(new_cat)
    row = find_row(stripped, riwaya, reciter)
    row.pop("files", None)
    return dumps(stripped) == old_raw and json.loads(old_raw) == stripped


def head_ok(url: str) -> int:
    last = 0
    for _ in range(3):
        try:
            req = urllib.request.Request(url, method="HEAD", headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.status
        except urllib.error.HTTPError as ex:              # type: ignore[attr-defined]
            last = ex.code
            if ex.code in (404, 403, 410):
                return ex.code
        except Exception:                                 # noqa: BLE001
            last = -1
    return last


def read_index(cl, bucket: str, riwaya: str, reciter: str):
    raw = cl.get_object(Bucket=bucket, Key=f"timings/{riwaya}/{reciter}.jz")["Body"].read()
    try:
        d = json.loads(gzip.decompress(raw))
    except OSError:
        d = json.loads(raw)
    return d.get("entries") or d.get("items") or []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya")
    ap.add_argument("--reciter")
    ap.add_argument("--map", default="", help="‏س=اسم,… للسور المخالفة لـSSS.mp3")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    if not (a.riwaya and a.reciter and a.map):
        sys.exit("⛔ يلزم --riwaya و--reciter و--map")
    import promote                                        # noqa: PLC0415
    cl, bucket = promote.s3()
    old_raw = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    old_sha = hashlib.sha256(old_raw).hexdigest()
    cat = json.loads(old_raw)
    if dumps(cat) != old_raw:
        sys.exit("⛔ تسلسلُ الكتالوج الحيّ لا يطابق التسلسلَ المعتمد — لا كتابةَ بتغييرٍ أوسع من الحقل")
    row = find_row(cat, a.riwaya, a.reciter)
    files = build_files(parse_map(a.map))
    new = apply(cat, a.riwaya, a.reciter, files)
    if not only_files_changed(old_raw, new, a.riwaya, a.reciter):
        sys.exit("⛔ تغيّر في الكتالوج غيرُ الحقل — يُوقَف")
    bad = index_mismatches(read_index(cl, bucket, a.riwaya, a.reciter), row["base"], files)
    if bad:
        sys.exit(f"⛔ files تخالف الفهرس المنشور في {len(bad)} مدخلاً، مثلاً:\n  " + "\n  ".join(bad[:5]))
    print(f"✓ files تتّفق مع كلّ fileRef في الفهرس المنشور ({a.riwaya}/{a.reciter})")
    urls = [row["base"] + n for n in files]
    with cf.ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(head_ok, urls))
    fails = [(i + 1, urls[i], c) for i, c in enumerate(codes) if c != 200]
    if fails:
        sys.exit(f"⛔ HEAD لم يردّ 200 في {len(fails)}: {fails[:5]}")
    print("✓ HEAD 200 للأربعة عشر ومئة ملفّ")
    changed = {s: files[s - 1] for s in range(1, 115) if files[s - 1] != f"{s:03d}.mp3"}
    print(f"   الأسماء المخالفة لـSSS.mp3: {changed}")
    if not a.yes:
        print("عرضٌ فقط — أضف --yes للكتابة")
        return
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bkey = f"{BACKUP_PREFIX}reciters.{stamp}.{old_sha}.json"
    cl.put_object(Bucket=bucket, Key=bkey, Body=old_raw, ContentType="application/json",
                  Metadata={"source-key": CATALOG_KEY, "source-sha256": old_sha}, IfNoneMatch="*")
    if hashlib.sha256(cl.get_object(Bucket=bucket, Key=bkey)["Body"].read()).hexdigest() != old_sha:
        sys.exit("⛔ فشل التحقق من النسخة الاحتياطية — لا كتابة")
    print(f"✓ نسخةٌ احتياطية → {bkey}")
    live = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    if hashlib.sha256(live).hexdigest() != old_sha:
        sys.exit("⛔ تغيّر الكتالوج الحيّ أثناء العمل — أعد التشغيل (لا كتابةَ فوق تعديلٍ متزامن)")
    body = dumps(new)
    cl.put_object(Bucket=bucket, Key=CATALOG_KEY, Body=body, ContentType="application/json")
    got = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    if hashlib.sha256(got).hexdigest() != hashlib.sha256(body).hexdigest():
        sys.exit("⛔ ما نزل يخالف ما رُفع — بلاغُ حادثة")
    print(f"↑ كُتب {CATALOG_KEY} ({len(body)} بايت · كان {len(old_raw)}) → ✅")


def self_test() -> int:
    fails = []

    def ok(name, cond):
        print(("✓ " if cond else "✗ ") + name)
        if not cond:
            fails.append(name)

    def raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    cat = {"version": 1, "updated": 5, "riwayat": [
        {"id": "qalun", "reciters": [
            {"id": "akri", "name": "ع", "base": "https://h/m/", "mode": "surah"},
            {"id": "other", "name": "غ", "base": "https://h/o/", "mode": "surah"}]},
        {"id": "warsh", "reciters": [{"id": "akri", "name": "ورش", "base": "https://h/w/"}]}]}
    raw = dumps(cat)
    m = parse_map("106=108.mp3,107=106.mp3,108=107.mp3")
    files = build_files(m)
    ok("114 اسماً", len(files) == 114)
    ok("الافتراضي SSS.mp3 والمخالف كما طُلب",
       files[0] == "001.mp3" and files[105] == "108.mp3" and files[106] == "106.mp3" and files[107] == "107.mp3")
    new = apply(cat, "qalun", "akri", files)
    ok("الأصل لم يُمسّ (نسخة عميقة)", "files" not in cat["riwayat"][0]["reciters"][0])
    ok("المدخل المطلوب وحده يحمل files",
       new["riwayat"][0]["reciters"][0]["files"] == files
       and "files" not in new["riwayat"][0]["reciters"][1]
       and "files" not in new["riwayat"][1]["reciters"][0])
    ok("لا يتغيّر إلا الحقل (بايتاً)", only_files_changed(raw, new, "qalun", "akri"))
    tampered = copy.deepcopy(new)
    tampered["riwayat"][0]["reciters"][1]["name"] = "x"
    ok("حارس: تغييرٌ غير الحقل يُكشف", not only_files_changed(raw, tampered, "qalun", "akri"))
    ok("idempotent: إعادة التطبيق بالقائمة نفسها تمرّ", apply(new, "qalun", "akri", files) == new)
    ok("حارس: files سابقةٌ مختلفة تُرفض", raises(lambda: apply(new, "qalun", "akri", build_files({1: "x.mp3"}))))
    ok("حارس: قارئ غير موجود", raises(lambda: apply(cat, "qalun", "nope", files)))
    ok("حارس: معرّف القارئ مشترك بين روايتين لا يخلط", apply(cat, "warsh", "akri", files)["riwayat"][0]["reciters"][0].get("files") is None)
    ok("حارس: اسم مكرَّر", raises(lambda: build_files({106: "107.mp3"})))
    ok("حارس: اسم فيه /", raises(lambda: build_files({5: "a/b.mp3"})))
    ok("حارس: سورة خارج المدى", raises(lambda: parse_map("115=x.mp3")))
    ok("حارس: سورة مكرَّرة في map", raises(lambda: parse_map("5=a.mp3,5=b.mp3")))
    ents = [{"ayahId": "106:1", "fileRef": "https://h/m/108.mp3"},
            {"ayahId": "107:1", "fileRef": "https://h/m/106.mp3"},
            {"ayahId": "108:1", "fileRef": "https://h/m/107.mp3"},
            {"ayahId": "105:1", "fileRef": "https://h/m/105.mp3"}, {"ayahId": "1:1"}]
    ok("الفهرس يتّفق مع files الصحيحة", index_mismatches(ents, "https://h/m/", files) == [])
    ok("حارس: files بالاسم المشتقّ (غير المدوَّر) تخالف الفهرس",
       len(index_mismatches(ents, "https://h/m/", build_files({}))) == 3)
    ok("التسلسل المدمج لا يغيّر العربية", "ع".encode() in raw)
    print("— فشل:" if fails else "— كلّها نجحت", fails or "")
    return 1 if fails else 0


if __name__ == "__main__":
    main()
