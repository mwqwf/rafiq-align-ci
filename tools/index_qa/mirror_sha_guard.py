#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حارسُ بصمة المرآة — يطابق ملفَّ كلِّ سورةٍ في مرآة الصوت بـ`audioSha256` للفهرس المنشور
ويحجب قصاصاتِ ما يخالفه (`clipsBlockedReason = SHA_MISMATCH`) في `audio/<riwaya>/manifest.json`.

⛔ **سببُه (مقيسٌ 2026-10-23):** التطبيق يقصّ آيات السورة المنزَّلة من ملفّ المرآة بحدود الفهرس الحيّ،
   ولا يقرأ `audioSha256` في أيّ موضع. وحكمُ `timingIndexShaMatch` يُحسب **عند نشر المرآة فقط**
   (2026-09-02) ثمّ يبقى؛ فلمّا أُعيد نشرُ الفهارس بعدها تقادم الحكم: 22 سورةً (6 قرّاء) `clipsOk:true`
   وملفُّها غيرُ ما بُني عليه الفهرس ⇒ نحو 2302 آيةٍ بصوتِ غيرها.

## الأوامر
    report  [--public] [--riwaya R] [--only riw/id …] [--verify-size] [--rehash]
        قراءةٌ محضة: يطبع ما يخالف. `--public` يقرأ من العنوان العامّ بلا اعتماد.
    apply   [--only riw/id …] [--surahs riw/id:1,2,3 …] [--verify-size] [--rehash]
        يحجب ما يخالف (حجبٌ فقط؛ لا يرفع حجباً أبداً). يحفظ نسخةً من المانيفست أوّلاً في
        `audio/_manifest_backups/<riwaya>/manifest.<ts>.json` ويتحقّق بعد الكتابة أنّه لم يمسّ غير المقصود.
    sync    --surahs riw/id:1,2,3 … [--dry]
        الجذر: لكلّ سورةٍ يُنزَّل `fileRef` من الفهرس المنشور (mp3 فقط) ويُتحقَّق أنّ sha = audioSha256، ثمّ
        يُحفظ أصلُ المرآة في `audio/_superseded/<riwaya>/<id>/<NNN>.<sha8>.mp3` ويُرفع الجديد بالاسم القياسيّ
        ويُعاد التحقّق من بصمته في الدلو، ثمّ يُحدَّث المانيفست (بصمة/حجم/clipsOk) ويُرفع حجبُ SHA_MISMATCH
        عن ما تطابق فقط. ما لم تطابق بصمتُه أو كان fileRef غيرَ mp3 يُترك محجوباً ويُسمّى.
    unregistered  [--only riw/id …] [--riwaya R …] [--list-only] [--workers N]
        مسحُ المرآة **غير المسجَّلة** (report فقط، لا يكتب شيئاً): قرّاءٌ لفهرسهم المنشور ملفّاتُ مرآةٍ في
        `audio/<riwaya>/<id>/` وليس لهم مدخلٌ في `audio/<riwaya>/manifest.json` (فلا يستعملهم التطبيق اليوم).
        يحسب sha كلِّ ملفٍّ فعلاً (بثّاً) ويقارنه بـ`audioSha256` للفهرس المنشور. الخروج 0 = كلُّها مطابقة (التسجيلُ
        مأمون)، 3 = فيها مخالفة (لا تُسجَّل قبل `sync` أو إعادة فهرسة)، 6 = فهرسٌ غيرُ قابلٍ للتحقّق. `--list-only`
        يعدّ الملفّات والأحجام بلا تنزيل. ثقيلٌ بقدر المرآة (استعمل `--only` قبل تسجيل قارئٍ بعينه).
    selftest
        اختبارٌ بلا شبكة لمنطق المقارنة والتعديل.

## القاعدة
* بصمةُ المرآة = `perFile[].sha256` في المانيفست. وتُصدَّق ما دام حجمُ الكائن في الدلو = `perFile[].bytes`
  (`--verify-size`)؛ وإن اختلف الحجمُ فالمانيفستُ متقادمٌ عن الدلو ⇒ يُحجب ما اختلف (حذرٌ) ويُسمّى.
* `--rehash` يحسب sha كلِّ ملفٍّ فعلاً من الدلو (تنزيلٌ بثّيّ) — ثقيل؛ للمسح العميق الدوريّ لا لكلّ ترقية.
* الحجبُ **رتابيّ**: لا يُزال هنا. إزالتُه تتمّ بالمزامنة بعد تطابق البصمة فعلاً.
* ⛔ لا يكتب إلا `audio/<riwaya>/manifest.json` ونسختَه الاحتياطية.
* ⛔ **لا يبتلع الخطأ (2026-10-23):** فهرسٌ لا يُقرأ أو `audioSha256` فيه معطوبةٌ/غيرُ 114 ⇒ **«غيرُ قابلٍ للتحقّق»**
  يُسمّى بسببه ويُخرج رمزاً غيرَ صفريّ (6)؛ كان يُعامَل «لا مخالفة» فيمرّ. وتُقبل الصيغتان (قائمة أو نصُّ قائمة)
  عبر `index_fields.py`.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index_fields import IndexFieldError, audio_shas, full_shas  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PUBLIC = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/"
RIWAYAT = ("hafs", "warsh", "qalun", "douri", "shuba", "sousi")
BACKUP_PREFIX = "audio/_manifest_backups"


# ───────────────────────── المنطقُ النقيّ (يُختبر بلا شبكة) ─────────────────────────

def find_mismatches(entry: dict, index_sha: list, bucket_sizes: dict | None = None,
                    real_sha: dict | None = None) -> dict:
    """يرجع {سورة: سبب} لكلّ سورةٍ في مدخل المانيفست تخالف بصمةُ مرآتها بصمةَ الفهرس.

    * entry: مدخل قارئ من المانيفست (mode == "surah").
    * index_sha: audioSha256 من الفهرس المنشور (114).
    * bucket_sizes: {سورة: حجم الكائن في الدلو} إن طُلب `--verify-size`؛ اختلافُ الحجم عن perFile.bytes ⇒ "STALE_MANIFEST".
    * real_sha: {سورة: sha محسوب فعلاً} إن طُلب `--rehash`؛ يَفضُل على perFile.sha256.
    """
    out: dict = {}
    if not isinstance(index_sha, list) or len(index_sha) != 114:
        # ⛔ كان يرجع {} صامتاً فيُحسب «لا مخالفة». الآن يُرفع ويسمّيه المسحُ «غيرَ قابلٍ للتحقّق».
        raise IndexFieldError(f"audioSha256 غيرُ صالحةٍ للمقارنة ({type(index_sha).__name__}"
                              f"{'' if not isinstance(index_sha, list) else f' · {len(index_sha)} موضعاً'})")
    for pf in entry.get("perFile") or []:
        n = pf.get("surah")
        if not isinstance(n, int) or not 1 <= n <= 114:
            continue
        want = index_sha[n - 1]
        have = (real_sha or {}).get(n) or pf.get("sha256")
        if bucket_sizes is not None and n in bucket_sizes and bucket_sizes[n] != pf.get("bytes") \
                and not (real_sha or {}).get(n):
            out[n] = "STALE_MANIFEST"
        elif have != want:
            out[n] = "SHA_MISMATCH"
    return out


def apply_blocks(entry: dict, mism: dict, index_sha: list, ts: int) -> tuple[dict, list]:
    """يرجع (مدخلاً جديداً، السورَ التي حُجبت الآن فعلاً). حجبٌ فقط."""
    e = copy.deepcopy(entry)
    reason = dict(e.get("clipsBlockedReason") or {})
    blocked = set(e.get("clipsBlockedBySurah") or [])
    ok = set(e.get("clipsOkBySurah") or [])
    newly = []
    for n, why in sorted(mism.items()):
        for pf in e.get("perFile") or []:
            if pf.get("surah") == n:
                if pf.get("clipsOk") is not False:
                    newly.append(n)
                pf["clipsOk"] = False
        blocked.add(n)
        ok.discard(n)
        if str(n) not in reason:                 # DURATION_MISMATCH القائم يبقى
            reason[str(n)] = "SHA_MISMATCH"
    e["clipsBlockedReason"] = dict(sorted(reason.items(), key=lambda kv: int(kv[0])))
    e["clipsBlockedBySurah"] = sorted(blocked)
    e["clipsOkBySurah"] = sorted(ok)
    bad_all = sorted(blocked)
    if mism:
        e["timingIndexShaMatch"] = f"MISMATCH {bad_all[:10]}"
        e["usableForClips"] = False
        e["shaGuard"] = {"ts": ts, "mismatched": sorted(mism), "reasons": {str(k): v for k, v in sorted(mism.items())}}
    return e, newly


def apply_sync(entry: dict, updates: dict, index_sha: list, ts: int) -> dict:
    """updates: {سورة: (sha, bytes)} لملفٍّ رُفع فعلاً وبصمتُه = audioSha256. يرجع مدخلاً جديداً.

    يرفع حجبَ SHA_MISMATCH عن السورة (وحدها) ويُبقي DURATION_MISMATCH وغيره؛ ويُحدّث بصمةَ الملفّ وحجمَه
    وإجماليَّ bytes وحكمَ المطابقة الكلّيّ.
    """
    e = copy.deepcopy(entry)
    reason = dict(e.get("clipsBlockedReason") or {})
    blocked = set(e.get("clipsBlockedBySurah") or [])
    ok = set(e.get("clipsOkBySurah") or [])
    for n, (sha, nbytes) in sorted(updates.items()):
        if index_sha[n - 1] != sha:
            raise ValueError(f"س{n}: بصمةٌ لا تطابق الفهرس — لا تحديث")
        for pf in e["perFile"]:
            if pf["surah"] == n:
                pf["sha256"], pf["bytes"] = sha, nbytes
                if reason.get(str(n)) in (None, "SHA_MISMATCH"):
                    pf["clipsOk"] = True
        if reason.get(str(n)) in (None, "SHA_MISMATCH"):
            reason.pop(str(n), None)
            blocked.discard(n)
            ok.add(n)
    e["clipsBlockedReason"] = dict(sorted(reason.items(), key=lambda kv: int(kv[0])))
    e["clipsBlockedBySurah"] = sorted(blocked)
    e["clipsOkBySurah"] = sorted(ok)
    e["bytes"] = sum(pf["bytes"] for pf in e["perFile"])
    still = sorted(pf["surah"] for pf in e["perFile"] if pf["sha256"] != index_sha[pf["surah"] - 1])
    e["timingIndexShaMatch"] = "MATCH" if not still else f"MISMATCH {still[:10]}"
    e["usableForClips"] = not still
    e["shaGuard"] = {"ts": ts, "mismatched": still,
                     "reasons": {str(k): "SHA_MISMATCH" for k in still}}
    return e


def _strip_volatile(m: dict) -> dict:
    d = copy.deepcopy(m)
    d.pop("updated", None)
    return d


# ───────────────────────── الإدخال والإخراج ─────────────────────────

class Src:
    """مصدر القراءة: الدلو (اعتمادٌ) أو العنوان العامّ."""

    def __init__(self, public: bool):
        self.public = public
        self.cl = self.bucket = None
        if not public:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from run import s3
            self.cl, self.bucket = s3()

    def get(self, key: str) -> bytes:
        if self.public:
            rq = urllib.request.Request(f"{PUBLIC}{key}?nc={time.time_ns()}", headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(rq, timeout=120).read()
        return self.cl.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def sizes(self, prefix: str) -> dict:
        if self.public:
            raise SystemExit("⛔ --verify-size يحتاج اعتماد الدلو (لا يعمل مع --public)")
        out = {}
        for page in self.cl.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            for o in page.get("Contents", []):
                out[o["Key"]] = o["Size"]
        return out

    def sha_of(self, key: str) -> str:
        if self.public:
            raise SystemExit("⛔ --rehash يحتاج اعتماد الدلو")
        h = hashlib.sha256()
        for chunk in self.cl.get_object(Bucket=self.bucket, Key=key)["Body"].iter_chunks(1 << 20):
            h.update(chunk)
        return h.hexdigest()


def load_manifest(src: Src, riw: str) -> dict | None:
    try:
        return json.loads(src.get(f"audio/{riw}/manifest.json"))
    except Exception as e:                                                   # noqa: BLE001
        print(f"  (لا مانيفست لـ{riw}: {e!r})")
        return None


def load_index_sha(src: Src, riw: str, rid: str) -> list:
    """بصماتُ الفهرس المنشور (114 موضعاً). ⛔ لا يبتلع: خطأُ الشبكة/الفكّ/الصيغة يُرفع إلى المسح فيسمّيه."""
    idx = json.loads(gzip.decompress(src.get(f"timings/{riw}/{rid}.jz")))
    return full_shas(idx)


def published_set(src: Src) -> set:
    man = json.loads(src.get("timings/manifest.json"))["indexes"]
    return {(x["riwaya"], x["reciterId"]) for x in man}


def scan(src: Src, riwayat, only, verify_size, rehash):
    """يرجع {riwaya: (manifest, {rid: (entry, index_sha, mism)}, {rid: سببُ عدمِ القابلية للتحقّق})} للمنشور فقط."""
    pub = published_set(src)
    res = {}
    for riw in riwayat:
        man = load_manifest(src, riw)
        if not man:
            continue
        rows = {}
        unver = {}
        for e in man.get("reciters", []):
            rid = e["id"]
            if (riw, rid) not in pub or e.get("mode") != "surah" or not e.get("complete"):
                continue
            if only and f"{riw}/{rid}" not in only:
                continue
            try:
                idx_sha = load_index_sha(src, riw, rid)
            except Exception as exc:                                        # noqa: BLE001
                unver[rid] = f"{type(exc).__name__}: {str(exc)[:160]}"
                continue
            sizes = None
            if verify_size:
                pre = f"audio/{riw}/{rid}/"
                lst = src.sizes(pre)
                sizes = {int(k[len(pre):-4]): v for k, v in lst.items() if k.endswith(".mp3") and k[len(pre):-4].isdigit()}
            real = None
            if rehash:
                with ThreadPoolExecutor(6) as ex:
                    ns = [pf["surah"] for pf in e.get("perFile") or []]
                    real = dict(zip(ns, ex.map(lambda n: src.sha_of(f"audio/{riw}/{rid}/{n:03d}.mp3"), ns)))
            rows[rid] = (e, idx_sha, find_mismatches(e, idx_sha, sizes, real))
        res[riw] = (man, rows, unver)
    return res


def _print_unverifiable(res) -> int:
    n = 0
    for riw, (_m, _rows, unver) in res.items():
        for rid, why in sorted(unver.items()):
            n += 1
            print(f"⚠️ {riw}/{rid}: غيرُ قابلٍ للتحقّق — {why}")
    return n


def cmd_report(a):
    src = Src(a.public)
    res = scan(src, a.riwaya or RIWAYAT, set(a.only or []), a.verify_size, a.rehash)
    total = unblocked = 0
    for riw, (_, rows, _u) in res.items():
        for rid, (e, _i, mism) in sorted(rows.items()):
            if not mism:
                continue
            fresh = {n: w for n, w in mism.items() if n not in (e.get("clipsBlockedBySurah") or [])}
            total += len(mism)
            unblocked += len(fresh)
            print(f"{riw}/{rid}: مخالفة {sorted(mism)} · غيرُ محجوبةٍ بعد {sorted(fresh)}")
    nun = _print_unverifiable(res)
    print(f"== الجملة: {total} سورةً مخالفة · منها {unblocked} غيرُ محجوبةٍ (clipsOk) تحتاج حجباً"
          + (f" · {nun} قارئاً غيرُ قابلٍ للتحقّق" if nun else ""))
    if unblocked:
        return 3
    return 6 if nun else 0


def cmd_apply(a):
    if a.public:
        raise SystemExit("⛔ apply يحتاج اعتماد الدلو")
    src = Src(False)
    only = set(a.only or [])
    limit = {}
    for spec in a.surahs or []:
        k, _, v = spec.partition(":")
        limit[k] = {int(x) for x in v.split(",") if x}
        only.add(k)
    res = scan(src, RIWAYAT, only, a.verify_size, a.rehash)
    ts = int(time.time())
    rc = 6 if _print_unverifiable(res) else 0     # لا يمنع حجبَ ما أمكن التحقّقُ منه، لكنّه يُخرج رمزاً غيرَ صفريّ
    for riw, (man, rows, _u) in res.items():
        new_man = copy.deepcopy(man)
        changed = []
        for i, e in enumerate(new_man["reciters"]):
            row = rows.get(e["id"])
            if not row:
                continue
            mism = row[2]
            k = f"{riw}/{e['id']}"
            if k in limit:
                mism = {n: w for n, w in mism.items() if n in limit[k]}
            fresh = {n: w for n, w in mism.items() if n not in (e.get("clipsBlockedBySurah") or [])}
            if not fresh:
                continue
            new_e, newly = apply_blocks(e, fresh, row[1], ts)
            new_man["reciters"][i] = new_e
            changed.append((e["id"], sorted(fresh), newly))
        if not changed:
            print(f"{riw}: لا جديدَ يُحجب")
            continue
        raw = src.get(f"audio/{riw}/manifest.json")
        if json.loads(raw) != man:
            print(f"⛔ {riw}: المانيفست تبدّل أثناء القراءة — لا كتابة (أعد المحاولة)")
            rc = 4
            continue
        bkey = f"{BACKUP_PREFIX}/{riw}/manifest.{ts}.json"
        src.cl.put_object(Bucket=src.bucket, Key=bkey, Body=raw, ContentType="application/json")
        got = src.cl.get_object(Bucket=src.bucket, Key=bkey)["Body"].read()
        if got != raw:
            print(f"⛔ {riw}: النسخة الاحتياطية لا تطابق الأصل — لا كتابة")
            rc = 4
            continue
        print(f"🗄️ {riw}: نسخةٌ احتياطية {bkey} ({len(raw)} بايتاً · sha {hashlib.sha256(raw).hexdigest()[:12]})")
        new_man["updated"] = ts
        src.cl.put_object(Bucket=src.bucket, Key=f"audio/{riw}/manifest.json", ContentType="application/json",
                          Body=json.dumps(new_man, ensure_ascii=False, indent=1).encode("utf-8"))
        back = json.loads(src.cl.get_object(Bucket=src.bucket, Key=f"audio/{riw}/manifest.json")["Body"].read())
        # تحقّقٌ بعديّ: ما عدا المقصودين، كلُّ مدخلٍ يطابق الأصل حرفاً
        touched = {c[0] for c in changed}
        same_rest = all(back["reciters"][i] == man["reciters"][i]
                        for i, e in enumerate(man["reciters"]) if e["id"] not in touched) \
            and len(back["reciters"]) == len(man["reciters"])
        # وفي المقصودين: لم يتغيّر شيءٌ غير حقول الحجب
        keep = ("perFile", "clipsOkBySurah", "clipsBlockedBySurah", "clipsBlockedReason",
                "timingIndexShaMatch", "usableForClips", "shaGuard")
        only_block = True
        for i, e in enumerate(man["reciters"]):
            if e["id"] in touched:
                b = {k: v for k, v in back["reciters"][i].items() if k not in keep}
                o = {k: v for k, v in e.items() if k not in keep}
                only_block &= (b == o)
        print(f"{'✅' if same_rest and only_block else '⛔'} {riw}: كُتب · غيرُ المقصودين سليمٌ={same_rest} · "
              f"المقصودون تغيّرت حقولُ الحجب وحدَها={only_block}")
        for rid, ns, newly in changed:
            print(f"   {rid}: حُجب {ns}")
        if not (same_rest and only_block):
            rc = 5
    return rc


def _plain_mp3_url(ref) -> bool:
    from urllib.parse import urlparse, unquote
    if not isinstance(ref, str) or not ref.startswith("https://"):
        return False
    return unquote(urlparse(ref).path).lower().endswith(".mp3")


def _download(url: str, dest: Path):
    """تنزيلٌ بثّيّ إلى ملفٍّ مؤقّت مع sha256. يرجع (sha, bytes)؛ يعيد المحاولة ثلاثاً."""
    last = None
    for attempt in range(3):
        try:
            rq = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 rafiq-mirror-sync/1.0"})
            h = hashlib.sha256()
            n = 0
            with urllib.request.urlopen(rq, timeout=120) as r, open(dest, "wb") as f:
                cl = r.headers.get("Content-Length")
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    h.update(b)
                    f.write(b)
                    n += len(b)
            if cl is not None and int(cl) != n:
                raise IOError(f"size mismatch {cl} != {n}")
            return h.hexdigest(), n
        except Exception as e:                                               # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise last


def cmd_sync(a):
    import tempfile
    src = Src(False)
    ts = int(time.time())
    rc = 0
    by_reciter = {}
    for spec in a.surahs:
        k, _, v = spec.partition(":")
        by_reciter.setdefault(k, set()).update(int(x) for x in v.split(",") if x)
    for k, wanted in sorted(by_reciter.items()):
        riw, rid = k.split("/")
        man = load_manifest(src, riw)
        ent = next((e for e in man["reciters"] if e["id"] == rid), None) if man else None
        if not ent:
            print(f"⛔ {k}: لا مدخلَ في المانيفست"); rc = 2; continue
        idx = json.loads(gzip.decompress(src.get(f"timings/{riw}/{rid}.jz")))
        try:
            idx_sha = full_shas(idx)
        except IndexFieldError as exc:
            print(f"⛔ {k}: الفهرس بلا 114 بصمة صالحة — {exc}"); rc = 2; continue
        refs = {}
        for en in idx["entries"]:
            refs.setdefault(int(en["ayahId"].split(":")[0]), set()).add(en.get("fileRef"))
        pf = {p["surah"]: p for p in ent["perFile"]}
        updates = {}
        for n in sorted(wanted):
            tag = f"{k} س{n}"
            rset = refs.get(n) or set()
            if len(rset) != 1:
                print(f"⏭️ {tag}: fileRef غيرُ وحيد ({len(rset)}) — يُترك محجوباً"); continue
            ref = next(iter(rset))
            if not _plain_mp3_url(ref):
                print(f"⏭️ {tag}: fileRef ليس mp3 ({ref[-40:]}) — لا يوضع في اسم .mp3؛ يُترك محجوباً لإعادة الفهرسة"); continue
            if pf[n]["sha256"] == idx_sha[n - 1]:
                print(f"✓ {tag}: المرآة تطابق الفهرس سلفاً"); continue
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / "f.mp3"
                try:
                    sha, nbytes = _download(ref, tmp)
                except Exception as e:                                       # noqa: BLE001
                    print(f"⛔ {tag}: تعذّر تنزيل fileRef: {e!r}"); rc = 3; continue
                if sha != idx_sha[n - 1] or nbytes < 10000:
                    print(f"⛔ {tag}: بصمةُ fileRef الآن {sha[:12]} ≠ audioSha256 {idx_sha[n-1][:12]} "
                          f"(المصدر تبدّل بعد الفهرسة) — لا استبدال؛ يلزم إعادة فهرسة"); rc = 3; continue
                key = f"audio/{riw}/{rid}/{n:03d}.mp3"
                old_sha, old_bytes = pf[n]["sha256"], pf[n]["bytes"]
                if a.dry:
                    print(f"🧪 {tag}: سيُستبدل {old_sha[:8]}({old_bytes}) ⇒ {sha[:8]}({nbytes})"); continue
                # الأصلُ يُحفظ أوّلاً ويُتحقَّق من نسخته
                bkey = f"audio/_superseded/{riw}/{rid}/{n:03d}.{old_sha[:8]}.mp3"
                try:
                    src.cl.head_object(Bucket=src.bucket, Key=bkey)
                except Exception:                                            # noqa: BLE001
                    src.cl.copy_object(Bucket=src.bucket, Key=bkey, CopySource={"Bucket": src.bucket, "Key": key},
                                       ContentType="audio/mpeg")
                if src.cl.head_object(Bucket=src.bucket, Key=bkey)["ContentLength"] != old_bytes:
                    print(f"⛔ {tag}: نسخة الأصل الاحتياطية لا تطابق حجمه — لا استبدال"); rc = 3; continue
                if src.sha_of(bkey) != old_sha:
                    print(f"⛔ {tag}: بصمة النسخة الاحتياطية ≠ بصمة المانيفست للأصل — لا استبدال"); rc = 3; continue
                src.cl.upload_file(str(tmp), src.bucket, key, ExtraArgs={"ContentType": "audio/mpeg"})
                if src.cl.head_object(Bucket=src.bucket, Key=key)["ContentLength"] != nbytes or src.sha_of(key) != sha:
                    print(f"⛔ {tag}: المرفوع لا يطابق بصمةَ الفهرس بعد الرفع — راجِع فوراً (الأصل في {bkey})"); rc = 5; continue
                updates[n] = (sha, nbytes)
                print(f"✅ {tag}: {old_sha[:8]}({old_bytes}) ⇒ {sha[:8]}({nbytes}) · الأصل في {bkey}")
        if not updates:
            continue
        # تحديث المانيفست: قراءةٌ طازجة فتعديلٌ فكتابة، وتحقّقٌ أنّ غيرَ المقصودين لم يتغيّروا
        for attempt in range(4):
            raw = src.get(f"audio/{riw}/manifest.json")
            cur = json.loads(raw)
            i = next(j for j, e in enumerate(cur["reciters"]) if e["id"] == rid)
            new = copy.deepcopy(cur)
            new["reciters"][i] = apply_sync(cur["reciters"][i], updates, idx_sha, ts)
            new["updated"] = ts
            bkey = f"{BACKUP_PREFIX}/{riw}/manifest.{ts}.s{attempt}.json"
            src.cl.put_object(Bucket=src.bucket, Key=bkey, Body=raw, ContentType="application/json")
            src.cl.put_object(Bucket=src.bucket, Key=f"audio/{riw}/manifest.json", ContentType="application/json",
                              Body=json.dumps(new, ensure_ascii=False, indent=1).encode("utf-8"))
            back = json.loads(src.get(f"audio/{riw}/manifest.json"))
            rest_ok = all(back["reciters"][j] == cur["reciters"][j] for j in range(len(cur["reciters"])) if j != i) \
                and len(back["reciters"]) == len(cur["reciters"])
            if rest_ok and back["reciters"][i] == new["reciters"][i]:
                e2 = back["reciters"][i]
                print(f"🧾 {k}: المانيفست حُدّث · محجوب الآن {e2['clipsBlockedBySurah']} · الحكم {e2['timingIndexShaMatch']} "
                      f"· نسخة المانيفست قبل التعديل {bkey}")
                break
            print(f"⚠️ {k}: تعارضٌ مع كاتبٍ آخر للمانيفست — إعادة ({attempt + 1})")
            time.sleep(3 + attempt * 3)
        else:
            print(f"⛔ {k}: تعذّر تحديث المانيفست بلا تعارض — الملفّات رُفعت (الأصول محفوظة) والمانيفست كما كان/يلزم تحديثه"); rc = 5
    return rc


# ───────────────────────── المرآة غير المسجَّلة (report فقط) ─────────────────────────

def find_unregistered(mirror_keys, registered: set, published: set) -> dict:
    """{(riwaya, id): {سورة: مفتاح}} لملفّات مرآةٍ لقارئٍ **منشورِ الفهرس** وليس له مدخلٌ في مانيفست المرآة.

    * mirror_keys: مفاتيحُ الدلو تحت `audio/` (النمطُ `audio/<riwaya>/<id>/NNN.mp3` وحدَه يُحسب).
    * registered: {(riwaya, id)} من مدخلات المانيفست (أيّاً كان وضعُها) — هؤلاء يغطّيهم `report/apply`.
    * published: {(riwaya, id)} من `timings/manifest.json`.
    """
    out: dict = {}
    for k in mirror_keys:
        p = k.split("/")
        if len(p) != 4 or p[0] != "audio" or not p[3].endswith(".mp3") or not p[3][:-4].isdigit():
            continue
        riw, rid, n = p[1], p[2], int(p[3][:-4])
        if riw not in RIWAYAT or not 1 <= n <= 114:
            continue
        if (riw, rid) in registered or (riw, rid) not in published:
            continue
        out.setdefault((riw, rid), {})[n] = k
    return out


def compare_files(file_sha: dict, index_sha: list) -> dict:
    """{سورة: سبب} لملفّاتٍ بصمتُها المحسوبة فعلاً `file_sha[n]`: SHA_MISMATCH إن خالفت الفهرس، NO_INDEX_SHA إن لم يسجّل
    الفهرسُ بصمةً لها (غيرُ قابلةٍ للتحقّق فتُحسب مخالفةً حذراً: لا تُسجَّل على مجهول)."""
    if not isinstance(index_sha, list) or len(index_sha) != 114:
        raise IndexFieldError("audioSha256 غيرُ صالحةٍ للمقارنة")
    out = {}
    for n, got in sorted(file_sha.items()):
        want = index_sha[n - 1]
        if not want:
            out[n] = "NO_INDEX_SHA"
        elif got != want:
            out[n] = "SHA_MISMATCH"
    return out


def cmd_unregistered(a):
    src = Src(False)
    only = set(a.only or [])
    riwayat = tuple(a.riwaya or RIWAYAT)
    pub = published_set(src)
    registered, keys = set(), []
    sizes = {}
    for riw in riwayat:
        man = load_manifest(src, riw)
        registered |= {(riw, e["id"]) for e in (man or {}).get("reciters", [])}
        for page in src.cl.get_paginator("list_objects_v2").paginate(Bucket=src.bucket, Prefix=f"audio/{riw}/"):
            for o in page.get("Contents", []):
                keys.append(o["Key"])
                sizes[o["Key"]] = o["Size"]
    groups = find_unregistered(keys, registered, {x for x in pub if x[0] in riwayat})
    if only:
        groups = {k: v for k, v in groups.items() if f"{k[0]}/{k[1]}" in only}
    if not groups:
        print("== لا مرآةَ غيرُ مسجَّلةٍ لقرّاء منشورين" + (" ضمن --only" if only else ""))
        return 0
    total = bad_total = unver = 0
    for (riw, rid), files in sorted(groups.items()):
        nbytes = sum(sizes[k] for k in files.values())
        if a.list_only:
            print(f"{riw}/{rid}: {len(files)} ملفّاً · {nbytes / 1e9:.2f} غ.ب (غيرُ مسجَّل)")
            continue
        try:
            idx_sha = load_index_sha(src, riw, rid)
        except Exception as exc:                                            # noqa: BLE001
            unver += 1
            print(f"⚠️ {riw}/{rid}: غيرُ قابلٍ للتحقّق — {type(exc).__name__}: {str(exc)[:160]}")
            continue
        with ThreadPoolExecutor(a.workers) as ex:
            ns = sorted(files)
            got = dict(zip(ns, ex.map(lambda n: src.sha_of(files[n]), ns)))
        bad = compare_files(got, idx_sha)
        total += len(files)
        bad_total += len(bad)
        tag = "✅ مطابقة — التسجيلُ مأمون" if not bad else f"⛔ مخالفة {sorted(bad)}"
        print(f"{riw}/{rid}: {len(files)} ملفّاً · {tag}")
    if a.list_only:
        print(f"== {len(groups)} قارئاً غيرَ مسجَّل (عدٌّ فقط، بلا تنزيل)")
        return 0
    print(f"== مرآةٌ غيرُ مسجَّلة: {len(groups)} قارئاً · {total} ملفّاً · {bad_total} مخالفاً"
          + (f" · {unver} غيرُ قابلٍ للتحقّق" if unver else "") + " (report فقط — لم يُكتب شيء)")
    if bad_total:
        return 3
    return 6 if unver else 0


# ───────────────────────── الاختبار ─────────────────────────

def _fake_entry(shas, blocked=()):
    return {"id": "x", "mode": "surah", "complete": True,
            "perFile": [{"surah": n, "name": f"{n:03d}.mp3", "bytes": 1000 + n, "sha256": shas[n - 1],
                         "clipsOk": n not in blocked} for n in range(1, 115)],
            "clipsOkBySurah": [n for n in range(1, 115) if n not in blocked],
            "clipsBlockedBySurah": sorted(blocked),
            "clipsBlockedReason": {str(n): "DURATION_MISMATCH" for n in blocked},
            "timingIndexShaMatch": "MATCH", "usableForClips": True}


def selftest():
    idx = [f"{n:064x}" for n in range(1, 115)]
    e = _fake_entry(idx)
    assert find_mismatches(e, idx) == {}
    # مخالفة صريحة
    e2 = copy.deepcopy(e)
    e2["perFile"][6]["sha256"] = "0" * 64                     # س7
    e2["perFile"][8]["sha256"] = "1" * 64                     # س9 محجوبة أصلاً بالمدة
    e2["clipsBlockedBySurah"] = [9]
    e2["clipsOkBySurah"] = [n for n in range(1, 115) if n != 9]
    e2["clipsBlockedReason"] = {"9": "DURATION_MISMATCH"}
    m = find_mismatches(e2, idx)
    assert m == {7: "SHA_MISMATCH", 9: "SHA_MISMATCH"}, m
    new, newly = apply_blocks(e2, m, idx, 1)
    assert newly == [7, 9] or newly == [7], newly
    assert new["clipsBlockedReason"]["7"] == "SHA_MISMATCH"
    assert new["clipsBlockedReason"]["9"] == "DURATION_MISMATCH"          # لا يُستبدل سببٌ أشدّ
    assert new["clipsBlockedBySurah"] == [7, 9] and 7 not in new["clipsOkBySurah"]
    assert new["perFile"][6]["clipsOk"] is False and new["perFile"][5]["clipsOk"] is True
    assert new["usableForClips"] is False and new["timingIndexShaMatch"].startswith("MISMATCH")
    assert e2["perFile"][6]["clipsOk"] is True                           # الأصل لم يُمَسّ
    # رتابيّ: إعادة التطبيق لا تغيّر شيئاً
    again, _ = apply_blocks(new, m, idx, 2)
    assert again["clipsBlockedBySurah"] == new["clipsBlockedBySurah"]
    # الحجم المتقادم
    assert find_mismatches(e, idx, {3: 5555}) == {3: "STALE_MANIFEST"}
    assert find_mismatches(e, idx, {3: 1003}) == {}
    # rehash يغلب المانيفست في الاتجاهين
    assert find_mismatches(e, idx, None, {5: "f" * 64}) == {5: "SHA_MISMATCH"}
    bad = copy.deepcopy(e)
    bad["perFile"][4]["sha256"] = "2" * 64
    assert find_mismatches(bad, idx, None, {5: idx[4]}) == {}
    # ⛔ فهرسٌ بلا 114 بصمة صالحة **لا يمرّ «نظيفاً»**: يُرفع ليسمّيه المسحُ «غيرَ قابلٍ للتحقّق»
    for bad_idx in (idx[:100], None, "[]", {}):
        try:
            find_mismatches(e, bad_idx)
            raise SystemExit(f"⛔ كان يجب أن يرفع على {type(bad_idx).__name__}")
        except IndexFieldError:
            pass
    # sync: يرفع SHA_MISMATCH وحده ويُبقي DURATION_MISMATCH
    e3 = _fake_entry(idx, blocked={9})
    e3["perFile"][6]["sha256"] = "0" * 64                      # س7 مخالفة
    e3["perFile"][8]["sha256"] = "1" * 64                      # س9 مخالفة ومحجوبة بالمدة
    m3 = find_mismatches(e3, idx)
    b3, _ = apply_blocks(e3, m3, idx, 1)
    assert b3["clipsBlockedReason"] == {"7": "SHA_MISMATCH", "9": "DURATION_MISMATCH"}
    u = apply_sync(b3, {7: (idx[6], 4242), 9: (idx[8], 99)}, idx, 2)
    assert "7" not in u["clipsBlockedReason"] and u["clipsBlockedReason"]["9"] == "DURATION_MISMATCH"
    assert u["clipsBlockedBySurah"] == [9] and 7 in u["clipsOkBySurah"] and 9 not in u["clipsOkBySurah"]
    assert u["perFile"][6]["clipsOk"] is True and u["perFile"][6]["bytes"] == 4242 and u["perFile"][8]["clipsOk"] is False
    assert u["timingIndexShaMatch"] == "MATCH" and u["usableForClips"] is True
    assert u["bytes"] == sum(p["bytes"] for p in u["perFile"])
    try:
        apply_sync(b3, {7: ("f" * 64, 1)}, idx, 3)
        raise SystemExit("⛔ كان يجب أن يرفض بصمةً لا تطابق الفهرس")
    except ValueError:
        pass
    assert _plain_mp3_url("https://x.org/a/007.mp3?x=1") and not _plain_mp3_url("https://archive.org/d/002.ogg") \
        and _plain_mp3_url("https://archive.org/d/%D8%B3.mp3")
    # المرآة غير المسجَّلة
    keys = ["audio/hafs/qasm/002.mp3", "audio/hafs/qasm/005.mp3", "audio/hafs/a_klb/002.mp3",
            "audio/hafs/orphan/001.mp3", "audio/hafs/manifest.json", "audio/hafs/qasm/readme.txt",
            "audio/_superseded/hafs/qasm/002.abc12345.mp3", "audio/hafs/qasm/000.mp3", "audio/hafs/qasm/115.mp3",
            "audio/warsh/laghdaf_shinqiti/085.mp3"]
    g = find_unregistered(keys, {("hafs", "a_klb")}, {("hafs", "qasm"), ("hafs", "a_klb"), ("warsh", "laghdaf_shinqiti")})
    assert sorted(g) == [("hafs", "qasm"), ("warsh", "laghdaf_shinqiti")], g
    assert sorted(g[("hafs", "qasm")]) == [2, 5] and ("hafs", "orphan") not in g
    got = {2: idx[1], 5: "e" * 64, 7: idx[6]}
    idx2 = list(idx)
    idx2[6] = None
    assert compare_files(got, idx2) == {5: "SHA_MISMATCH", 7: "NO_INDEX_SHA"}
    try:
        compare_files(got, idx[:5])
        raise SystemExit("⛔ كان يجب أن يرفع على فهرسٍ ناقص")
    except IndexFieldError:
        pass
    print("✅ selftest: كلُّ الحالات سليمة")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    for name in ("report", "apply"):
        q = sp.add_parser(name)
        q.add_argument("--public", action="store_true")
        q.add_argument("--riwaya", nargs="*")
        q.add_argument("--only", nargs="*")
        q.add_argument("--verify-size", action="store_true")
        q.add_argument("--rehash", action="store_true")
        if name == "apply":
            q.add_argument("--surahs", nargs="*", help="riw/id:1,2,3 — يحصر الحجب بهذه السور")
    q = sp.add_parser("unregistered")
    q.add_argument("--only", nargs="*")
    q.add_argument("--riwaya", nargs="*")
    q.add_argument("--list-only", action="store_true")
    q.add_argument("--workers", type=int, default=6)
    q = sp.add_parser("sync")
    q.add_argument("--surahs", nargs="+", required=True, help="riw/id:1,2,3")
    q.add_argument("--dry", action="store_true")
    sp.add_parser("selftest")
    a = p.parse_args()
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "sync":
        return cmd_sync(a)
    if a.cmd == "unregistered":
        return cmd_unregistered(a)
    return cmd_report(a) if a.cmd == "report" else cmd_apply(a)


if __name__ == "__main__":
    sys.exit(main())
