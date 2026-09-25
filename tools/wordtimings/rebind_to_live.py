# -*- coding: utf-8 -*-
"""ربطٌ مبوّبٌ للتوقيت الكلمي على الفهرس الحيّ — حذفٌ بلا تخمين (البند 2، الجولة الثالثة).

**العطب:** ملفّا `wordtimings/{warsh,qalun}/husary_*.jz` مبنيّان على فهرسٍ مضى
(‏`generatedAgainst.sha256` = 5de0a957… و8680ed1f…) والفهرس الحيّ صار 717b7a5a… و6414f830….
فحارسُ النسب في التطبيق (`WordTimingsRepository.matchesIndex`) يُصمت الميزة ويحذف الملف.

**العلاج هنا (لا توليدَ لتوقيتٍ ولا تعديلَ لرقم):**
- تُبقى الآيةُ كما هي بايتاً بمعناها إن وقعت **كلُّ** كلماتها داخل حدود الآية الحيّة ±300 م.ث
  (‏`live.startMs - 300 <= w.startMs <= w.endMs <= live.endMs + 300`)، وكانت الكلمات مرتّبةً غير مقلوبة.
- ويُحذف ما سوى ذلك، وكلُّ آيةٍ غابت عن الفهرس الحيّ. ⛔ لا قصَّ ولا إزاحةَ ولا تقريب.
- ويُكتب `generatedAgainst.sha256` ببصمة الفهرس الحيّ، ويُحفظ الأصلُ القديم في `rebind.from`.

الاستعمال:
  python rebind_to_live.py build  --index <live.jz> --words <old_wt.jz> --out <new_wt.jz>
  python rebind_to_live.py verify --index <live.jz> --words <new_wt.jz> --min <N>
"""
import argparse
import gzip
import hashlib
import io
import json
import sys

TOL_MS = 300


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def read_jz_bytes(b):
    return json.loads(gzip.decompress(b).decode("utf-8"))


def live_bounds(index_doc):
    """«سورة:آية» ← (بداية، نهاية) من الفهرس الحيّ — ما له حدّان رقميّان فقط."""
    out = {}
    for e in index_doc.get("entries", []):
        s, t = e.get("startMs"), e.get("endMs")
        if isinstance(s, int) and isinstance(t, int) and t > s:
            out[e["ayahId"]] = (s, t)
    return out


def words_inside(words, bounds, tol=TOL_MS):
    """كلُّ كلمةٍ داخل الحدّين ±tol، غيرُ مقلوبة، ومرتّبةٌ بالبداية. قائمةٌ فارغة ⇒ مرفوض."""
    if not words:
        return False
    lo, hi = bounds[0] - tol, bounds[1] + tol
    prev = None
    for w in words:
        a, b = w.get("startMs"), w.get("endMs")
        if not isinstance(a, int) or not isinstance(b, int):
            return False
        if a > b or a < lo or b > hi:
            return False
        if prev is not None and a < prev:
            return False
        prev = a
    return True


def rebind(index_bytes, words_bytes, index_file_name):
    """يعيد (المستند الجديد، الإحصاء). لا يمسّ أرقام الكلمات."""
    idx = read_jz_bytes(index_bytes)
    doc = read_jz_bytes(words_bytes)
    live_sha = sha256_bytes(index_bytes)
    if doc.get("riwaya") != idx.get("riwaya") or doc.get("reciterId") != idx.get("reciterId"):
        raise SystemExit("⛔ الرواية أو القارئ لا يتطابقان بين الملف الكلمي والفهرس")
    if doc.get("indexing", "RAW_TOKENS") != "RAW_TOKENS":
        raise SystemExit("⛔ اصطلاح فهرسة غير مدعوم")
    if idx.get("sourceKind") != "SURAH_FILES" or doc.get("timeBase", "SURAH_FILE") != "SURAH_FILE":
        raise SystemExit("⛔ أساس الزمن غير ملف السورة — لا ربط مبوّب هنا")
    bounds = live_bounds(idx)
    kept, dropped_absent, dropped_out = [], 0, 0
    for e in doc["entries"]:
        b = bounds.get(e["ayahId"])
        if b is None:
            dropped_absent += 1
            continue
        if words_inside(e.get("words") or [], b):
            kept.append(e)
        else:
            dropped_out += 1
    old_ga = doc.get("generatedAgainst") or {}
    new = dict(doc)
    new["entries"] = kept
    new["timeBase"] = "SURAH_FILE"
    new["sourceIndex"] = index_file_name
    new["generatedAgainst"] = {
        "file": index_file_name,
        "sha256": live_sha,
        "generatedAt": idx.get("generatedAt"),
        "engineVersion": idx.get("engineVersion"),
        "entries": len(idx.get("entries", [])),
    }
    stats = {
        "method": "GATED_REBIND_NO_GUESS",
        "toleranceMs": TOL_MS,
        "rule": "keep an ayah only if every word lies within [live.startMs-300, live.endMs+300], "
                "words ordered and non-inverted; drop the rest; no word time is changed",
        "fromSha256": old_ga.get("sha256"),
        "fromEntries": len(doc["entries"]),
        "kept": len(kept),
        "droppedAbsentInLive": dropped_absent,
        "droppedOutOfBounds": dropped_out,
    }
    new["rebind"] = dict(stats, previousCoverageScope=doc.get("coverageScope"),
                         previousVerification=doc.get("verification"))
    new["coverageScope"] = [{"item": "المصحف كاملاً (ربطٌ مبوّب على الفهرس الحيّ)", "covered": len(kept)}]
    return new, stats


def dump_jz(doc):
    raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as g:
        g.write(raw)
    return buf.getvalue()


def verify(index_bytes, words_bytes, minimum):
    """التحقّق من الملف المنشور: البصمة المعلنة = الفهرس الحيّ · صفر كلمةٍ خارج الحدود · العدد ≥ الحدّ."""
    idx = read_jz_bytes(index_bytes)
    doc = read_jz_bytes(words_bytes)
    live_sha = sha256_bytes(index_bytes)
    declared = (doc.get("generatedAgainst") or {}).get("sha256")
    bounds = live_bounds(idx)
    out_words, bad_ayat, n_words = 0, 0, 0
    for e in doc["entries"]:
        b = bounds.get(e["ayahId"])
        ws = e.get("words") or []
        n_words += len(ws)
        if b is None:
            bad_ayat += 1
            out_words += len(ws)
            continue
        o = sum(1 for w in ws if not (b[0] - TOL_MS <= w["startMs"] <= w["endMs"] <= b[1] + TOL_MS))
        out_words += o
        if o or not words_inside(ws, b):
            bad_ayat += 1
    rep = {
        "liveSha256": live_sha,
        "declaredSha256": declared,
        "shaMatch": declared == live_sha,
        "ayat": len(doc["entries"]),
        "words": n_words,
        "wordsOutOfBounds": out_words,
        "badAyat": bad_ayat,
        "minimum": minimum,
        "ok": declared == live_sha and out_words == 0 and bad_ayat == 0 and len(doc["entries"]) >= minimum,
    }
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "verify"])
    ap.add_argument("--index", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--out")
    ap.add_argument("--min", type=int, default=1)
    ap.add_argument("--index-name", default=None)
    a = ap.parse_args()
    ib = open(a.index, "rb").read()
    wb = open(a.words, "rb").read()
    if a.mode == "build":
        name = a.index_name or a.index.rsplit("/", 1)[-1]
        doc, st = rebind(ib, wb, name)
        data = dump_jz(doc)
        open(a.out, "wb").write(data)
        st.update(bytes=len(data), sha256=sha256_bytes(data), liveSha256=sha256_bytes(ib))
        print(json.dumps(st, ensure_ascii=False))
        rep = verify(ib, data, a.min)
        print(json.dumps(rep, ensure_ascii=False))
        if not rep["ok"]:
            sys.exit("⛔ الملف المبنيّ لم يجتز التحقّق")
    else:
        rep = verify(ib, wb, a.min)
        print(json.dumps(rep, ensure_ascii=False))
        if not rep["ok"]:
            sys.exit("⛔ التحقّق فشل")


if __name__ == "__main__":
    main()
