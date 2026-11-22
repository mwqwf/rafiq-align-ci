#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دمجُ سورٍ كاملة من مرشّحات مسرحٍ تشترك في **الأب المنشور نفسه** إلى مرشّحٍ واحد.

    python tools/index_qa/union_same_parent.py \
        --parent timings/qalun/maroush_qalun.jz --parent-sha 3c0913dd… \
        --url 'https://host/{s:03d}.mp3' \
        --donors-file donors.json --reason '…' --yes

`donors.json`: قائمة `{"key", "sha"}` (‏`surahs` اختياري لحصر السور من ذلك المتبرّع).

**لماذا؟** `graft_surahs` متبرّعٌ واحد ونسبته يجب أن تنتهي عند الأب، ويرفض زرع
سورةٍ غائبةٍ في الأساس. وترقيةُ متبرّعٍ واحدٍ لقارئٍ متعدّد السور تقطع أخواته.
فهذه الأداة تجمع كلَّ المتبرّعين الذين `fromSha256` لهم هو بصمة الأب حرفاً،
ثم تكتب بـ`splice_surah` وترفع بـ`stage_transform` — بحُرّاسهما بلا إرخاء.

## الحُرّاس
1. كلُّ متبرّع: `transform.fromKey` = مفتاح الأب، و`fromSha256` = البصمة الكاملة.
2. لا تُؤخذ إلا سورةٌ كاملة الحدود (عدد الرواية، حدود صاعدة، بلا `startMs` فارغ).
3. سورةٌ يعرضها متبرّعان بحدودٍ أو رابطٍ مختلف: **ردٌّ** — لا ترجيحَ صامت.
4. ما تطابق حرفاً يُقبل من الأوّل. ما لم يختلف عن الأب ولا يملأ ثغرةً يُتجاهل.
5. `fileRef` في المتبرّع يجب أن يطابق `--url` بعد التنسيق — لا يُخمَّن رابط.
6. الدمج محليٌّ بـ`splice_surah`؛ الكتابة إلى الدلو بـ`stage_transform` فقط.
7. خرائط المحرّك/المصدر/النموذج تُنسخ من المتبرّع للسور المأخوذة، وتُترك
   خرائط الأب لما لم يُمسّ. لا يُخترَع وسمُ محرّكٍ لم يعلنه المتبرّع.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import splice_surah as sp  # noqa: E402

COUNTS = sp.COUNTS
AUDIO_EXT_RE = sp.AUDIO_EXT_RE
MAP_FIELDS = (
    "engineBySurah",
    "sourceBySurah",
    "sourceTimingBySurah",
    "alignmentModelBySurah",
    "dualFixEvidenceBySurah",
    "dualAlignmentEvidenceBySurah",
)


def _sa(aid):
    s, a = str(aid).split(":")
    return int(s), int(a)


def by_surah(entries):
    out = {}
    for e in entries or []:
        s, a = _sa(e["ayahId"])
        out.setdefault(s, []).append((a, e))
    for s, rows in out.items():
        rows.sort(key=lambda x: x[0])
        out[s] = [e for _, e in rows]
    return out


def complete_error(rows, s):
    want = COUNTS[s - 1]
    if len(rows) != want:
        return f"س{s}: {len(rows)} آية والرواية {want}"
    prev = -1
    for i, r in enumerate(rows):
        if int(r["ayahId"].split(":")[1]) != i + 1:
            return f"س{s}: ترتيب الآيات غير سويّ"
        st, en = r.get("startMs"), r.get("endMs")
        if st is None or en is None:
            return f"س{s}:{i + 1} بلا حدود"
        if not (0 <= st < en) or st < prev:
            return f"س{s}:{i + 1} حدودٌ غير صاعدة ({st}→{en})"
        prev = en
    refs = {r.get("fileRef") for r in rows}
    if len(refs) != 1:
        return f"س{s}: روابط ملفّ مختلفة {sorted(map(str, refs))}"
    ref = next(iter(refs))
    if not isinstance(ref, str) or not ref.startswith(("https://", "http://")):
        return f"س{s}: رابط غير صالح"
    if not AUDIO_EXT_RE.search(ref):
        return f"س{s}: الرابط مجلّد لا ملفّ صوتي"
    return None


def sig(rows):
    slim = [{"ayahId": r["ayahId"], "startMs": r.get("startMs"),
             "endMs": r.get("endMs"), "fileRef": r.get("fileRef")}
            for r in rows]
    return json.dumps(slim, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def check_parentage(donor, parent_key, parent_sha, donor_key):
    tr = donor.get("transform") if isinstance(donor.get("transform"), dict) else {}
    if tr.get("fromKey") != parent_key:
        raise SystemExit(
            f"⛔ {donor_key}: fromKey={tr.get('fromKey')!r} وليس الأب {parent_key}")
    got = tr.get("fromSha256") or ""
    if got != parent_sha:
        raise SystemExit(
            f"⛔ {donor_key}: fromSha256={got[:16]}… ≠ بصمة الأب {parent_sha[:16]}… "
            "— لا يُدمج إلا ابنٌ مباشر")


def file_ref_matches(ref, url, s):
    try:
        want = url.format(s=s)
    except Exception as ex:  # noqa: BLE001
        raise SystemExit(f"⛔ القالب لا يُنسَّق لس{s}: {ex}") from ex
    return ref == want


def offer_surahs(parent_by, donor, specified=None):
    """سور المتبرّع الكاملة التي تختلف عن الأب أو تملأ ثغرةً فيه."""
    dby = by_surah(donor.get("entries"))
    want = set(specified) if specified else set(dby)
    out = {}
    for s in sorted(want):
        rows = dby.get(s) or []
        err = complete_error(rows, s)
        if err:
            if specified is not None:
                raise SystemExit(f"⛔ {err} — سورةٌ مسمّاة لم تُحلّ")
            continue
        prow = parent_by.get(s) or []
        parent_ok = complete_error(prow, s) is None
        if parent_ok and sig(prow) == sig(rows):
            continue
        out[s] = rows
    return out


def plan(parent, parent_key, parent_sha, donors, url):
    """donors: قائمة (مفتاح، بصمة كاملة أو بادئة للتحقق لاحقاً، فهرس، سور أو None).

    تُرجع {سورة: سجلّ} والسجلّ فيه donor_key وrows وref والخرائط الجزئية.
    """
    pby = by_surah(parent.get("entries"))
    taken = {}
    for key, sha, idx, specified in donors:
        check_parentage(idx, parent_key, parent_sha, key)
        offers = offer_surahs(pby, idx, specified)
        for s, rows in offers.items():
            ref = rows[0]["fileRef"]
            if not file_ref_matches(ref, url, s):
                raise SystemExit(
                    f"⛔ {key} س{s}: fileRef {ref} ≠ القالب {url.format(s=s)} — لا يُخمَّن")
            rec = {"donor_key": key, "donor_sha": sha, "rows": rows, "ref": ref,
                   "maps": {f: (idx.get(f) or {}).get(str(s)) for f in MAP_FIELDS},
                   "audio_sha": None}
            ash = idx.get("audioSha256")
            present = sorted({int(e["ayahId"].split(":")[0]) for e in idx.get("entries") or []})
            if isinstance(ash, list) and len(ash) == len(present) and s in present:
                rec["audio_sha"] = ash[present.index(s)]
            elif isinstance(ash, list) and len(ash) == 114:
                rec["audio_sha"] = ash[s - 1]
            prev = taken.get(s)
            if prev and sig(prev["rows"]) != sig(rows):
                raise SystemExit(
                    f"⛔ تعارض س{s} بين {prev['donor_key']} و{key} — لا يُرجَّح")
            if prev:
                continue
            taken[s] = rec
    if not taken:
        raise SystemExit("⛔ لا سورةَ تُدمج: المتبرّعون لا يضيفون ولا يصلحون شيئاً")
    return taken


def aligned_payload(rec):
    entries = []
    for r in rec["rows"]:
        item = {"ayahId": r["ayahId"], "startMs": int(r["startMs"]),
                "endMs": int(r["endMs"]), "conf": float(r.get("conf") or 0.0)}
        if r.get("startApprox") or r.get("snapped") is False:
            item["snapped"] = False
        entries.append(item)
    out = {"entries": entries, "fileRef": rec["ref"]}
    if rec.get("audio_sha"):
        out["sha256"] = rec["audio_sha"]
    return out


def apply_maps(out, taken):
    """بعد splice بلا engine-tag: أثبت خرائط المتبرّع للسور المأخوذة فقط."""
    taken_s = set(taken)
    for field in MAP_FIELDS:
        base = {k: v for k, v in dict(out.get(field) or {}).items()
                if int(k) not in taken_s}
        for s, rec in taken.items():
            val = rec["maps"].get(field)
            if val:
                base[str(s)] = val
        if base:
            out[field] = dict(sorted(base.items(), key=lambda kv: int(kv[0])))
        else:
            out.pop(field, None)
    ash = out.get("audioSha256")
    present = sorted({int(e["ayahId"].split(":")[0]) for e in out.get("entries") or []})
    if isinstance(ash, list) and len(ash) == 114:
        for s, rec in taken.items():
            if rec.get("audio_sha"):
                ash[s - 1] = rec["audio_sha"]
        out["audioSha256"] = ash
    elif isinstance(ash, list) and len(ash) == len(present):
        pos = {s: i for i, s in enumerate(present)}
        for s, rec in taken.items():
            if rec.get("audio_sha") and s in pos:
                ash[pos[s]] = rec["audio_sha"]
        out["audioSha256"] = ash
    return out


def splice_union(parent, taken, url, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    parent_path = workdir / "parent.jz"
    out_path = workdir / "patched.jz"
    sp.dump(parent, parent_path)
    files = []
    surahs = []
    for s in sorted(taken):
        af = workdir / f"s{s:03d}.json"
        af.write_text(json.dumps(aligned_payload(taken[s]), ensure_ascii=False),
                      encoding="utf-8")
        files.append(str(af))
        surahs.append(str(s))
    cmd = [sys.executable, str(HERE / "splice_surah.py"),
           "--index", str(parent_path), "--surah", ",".join(surahs),
           "--aligned", *files, "--url", url, "--out", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(
            (r.stdout or "") + (r.stderr or "") or f"⛔ splice_surah خرج {r.returncode}")
    print(r.stdout, end="" if (r.stdout or "").endswith("\n") else "\n")
    out = sp.load(out_path)
    out = apply_maps(out, taken)
    sha = sp.dump(out, out_path)
    return out, out_path, sha, [int(s) for s in surahs]


def load_donors_file(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise SystemExit("⛔ --donors-file قائمة غير فارغة من {key, sha}")
    out = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict) or not row.get("key") or not row.get("sha"):
            raise SystemExit(f"⛔ عنصر {i} بلا key/sha")
        surahs = row.get("surahs")
        if surahs is not None:
            try:
                surahs = [int(x) for x in surahs]
            except (TypeError, ValueError) as ex:
                raise SystemExit(f"⛔ عنصر {i}: surahs غير مقروءة") from ex
            if any(not (1 <= s <= 114) for s in surahs):
                raise SystemExit(f"⛔ عنصر {i}: سورة خارج 1..114")
        out.append((row["key"], str(row["sha"]), surahs))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--parent", required=True)
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--url", required=True,
                    help="قالب الصوت من الكتالوج وفيه {s:03d} — لا يُخمَّن")
    ap.add_argument("--donors-file", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--workdir", default="")
    ap.add_argument("--parent-file", default="",
                    help="فهرس أب محلي للاختبار (بلا دلو)")
    ap.add_argument("--donor-files", default="",
                    help="ملفات متبرّعين محلية بالترتيب نفسه في donors-file")
    a = ap.parse_args()
    if "{s:03d}" not in a.url and "{s:" not in a.url:
        raise SystemExit("⛔ --url بلا {s:03d} — لا يُخمَّن اسم الملف")
    specs = load_donors_file(a.donors_file)

    if a.parent_file:
        parent = sp.load(Path(a.parent_file))
        parent_sha = a.parent_sha
        # في الاختبار تُمرَّر البصمة كما يدّعي المتبرّع؛ لا قراءة من الدلو.
        dfiles = [x for x in a.donor_files.split(",") if x]
        if len(dfiles) != len(specs):
            raise SystemExit("⛔ --donor-files بعدد عناصر donors-file")
        donors = []
        for (key, sha, surahs), fp in zip(specs, dfiles):
            donors.append((key, sha, sp.load(Path(fp)), surahs))
    else:
        import promote
        cl, bucket = promote.s3()

        def r2_load(key, sha):
            body = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
            full = hashlib.sha256(body).hexdigest()
            if not full.startswith(sha):
                raise SystemExit(
                    f"⛔ البصمة لا تطابق {key}: الحيّة {full[:16]} والمطلوبة {sha}")
            return json.loads(gzip.decompress(body).decode("utf-8")), full

        parent, parent_sha = r2_load(a.parent, a.parent_sha)
        donors = []
        for key, sha, surahs in specs:
            idx, full = r2_load(key, sha)
            donors.append((key, full, idx, surahs))

    taken = plan(parent, a.parent, parent_sha, donors, a.url)
    print("خطة الدمج:")
    for s in sorted(taken):
        rec = taken[s]
        print(f"  س{s}: من {rec['donor_key']} ({rec['donor_sha'][:12]})")

    wd = Path(a.workdir) if a.workdir else Path(tempfile.mkdtemp(prefix="union_"))
    out, out_path, sha, surahs = splice_union(parent, taken, a.url, wd)
    n = len(out.get("entries") or [])
    miss = (out.get("missing") or {}).get("count")
    print(f"المخرج {out_path} · sha {sha[:16]}… · مداخل {n} · غياب {miss} · سور {surahs}")
    if not a.yes:
        print("عرضٌ فقط (بدون --yes) — لم يُرفع إلى المسرح")
        return
    if a.parent_file:
        raise SystemExit("⛔ --yes لا يجتمع مع --parent-file (مسار الدلو فقط)")
    op = "union_same_parent:" + ",".join(map(str, surahs))
    cmd = [sys.executable, str(HERE / "stage_transform.py"),
           "--file", str(out_path), "--parent", a.parent,
           "--parent-sha", parent_sha, "--op", op, "--reason", a.reason,
           "--by", "union_same_parent", "--yes"]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


if __name__ == "__main__":
    main()
