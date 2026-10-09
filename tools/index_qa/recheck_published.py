#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعادةُ فحصِ المنشور بالحرّاس المشدَّدة — قارئٌ محضٌ (عرضٌ فقط، بلا `--yes`).

    python tools/index_qa/recheck_published.py --since 2026-10-08T00:00:00Z --out ops/out/<اسم>.json

لكلّ فهرسٍ رُقّي (`updatedTs` في المانيفست ≥ --since): يجد مفاتيحَ الأحكام التي تحمل
بصمتَه المنشورة، ويُشغّل `promote.main()` عليها **عرضاً** (حرّاسُ الحكم والمطالع والتجميع
والبتر والسماع والإحصاء والهويّة كما هي بعد PR #34)، ويحفظ المخرَج. لا كتابةَ في الدلو.
"""
from __future__ import annotations
import argparse, contextlib, io, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote as P  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def classify(text):
    bad = [l.strip() for l in text.splitlines() if l.lstrip().startswith(("⛔", "🔴", "⏳"))]
    ok = any("✅ جاهز" in l for l in text.splitlines())
    return ok, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None, help="مفاتيح منشورة بفاصلة (اختياري)")
    ap.add_argument("--budget-sec", type=int, default=3000)
    a = ap.parse_args()
    out = Path(a.out)
    if out.parent.name != "out" or out.suffix != ".json" or out.exists():
        raise SystemExit("ملفّ JSON جديد في ops/out مطلوب")
    since = datetime.fromisoformat(a.since.replace("Z", "+00:00")).timestamp() * 1000
    cl, bucket = P.s3()
    man = json.loads(cl.get_object(Bucket=bucket, Key="timings/manifest.json")["Body"].read())
    ents = man.get("indexes") if isinstance(man, dict) else man
    if isinstance(ents, dict):
        ents = list(ents.values())
    rows = [e for e in ents if (e.get("updatedTs") or 0) >= since]
    if a.only:
        want = set(a.only.split(","))
        rows = [e for e in rows if f"{e['riwaya']}/{e['reciterId']}" in want]
    print(f"المانيفست: {len(ents)} فهرساً · رُقّي منذ {a.since}: {len(rows)}")
    t0 = time.time()
    everywhere = list(P.reports()) + P.bucket_reports(cl, bucket)
    failed = P.READ_FAILED
    P.REPORTS_CACHE = everywhere
    # ⚖️ الهدفُ المنشورُ مجمَّدٌ ببصمته بعد الترقية، وبوّابةُ `gate` ترفض كلَّ هدفٍ مجمَّد.
    #    لإعادة قياس الحرّاس الأخرى على البصمة نفسها تُقدَّم قائمةُ تجميدٍ فارغة (قراءةٌ محضة):
    #    تطابقُ التجميد مع المانيفست تقيسه `full_audit.py` (البند 1).
    P.load_frozen = lambda _cl, _b: ({}, "", None)
    print(f"أحكامٌ محمَّلة: {len(everywhere)} · أحكامٌ تعذّرت قراءتها: {failed}")
    by_sha = {}
    for _n, r in everywhere:
        by_sha.setdefault(r.get("sha256"), set()).add(r.get("key"))
    res = []
    argv0 = sys.argv
    for e in sorted(rows, key=lambda x: x.get("updatedTs") or 0):
        pk = f"timings/{e['riwaya']}/{e['reciterId']}.jz"
        item = {"key": pk, "sha256": e["sha256"], "sha8": e["sha256"][:8], "entries": e.get("entries"),
                "updatedTs": e.get("updatedTs"), "runs": []}
        keys = sorted(by_sha.get(e["sha256"], []), key=lambda k: (not str(k).startswith("timings-staging/"), str(k)))
        item["reportKeys"] = keys
        # 🩺 تشخيصُ البتر: سببُ «stale» إن وُجد (عدمُ تطابق ETag أم تعذّرُ القراءة)
        try:
            pe = cl.head_object(Bucket=bucket, Key=pk).get("ETag")
            dk = P.DIAGNOSIS_KEY.format(riwaya=e["riwaya"], reciter=e["reciterId"])
            try:
                dd = json.loads(cl.get_object(Bucket=bucket, Key=dk)["Body"].read())
                weak = [(w.get("surah"), w.get("verdict")) for w in (dd.get("weakSurahs") or [])
                        if "TRUNC" in str(w.get("verdict") or "").upper()]
                item["diag"] = {"read": "ok", "indexETag": dd.get("indexETag"), "publishedETag": pe,
                                "match": (dd.get("indexETag") or "").strip('"') == (pe or "").strip('"'),
                                "generatedAt": dd.get("generatedAt") or dd.get("ts") or dd.get("updated"),
                                "truncatedSurahs": weak}
            except Exception as ex:  # noqa: BLE001
                item["diag"] = {"read": f"{type(ex).__name__}: {str(ex)[:120]}", "publishedETag": pe}
        except Exception as ex:  # noqa: BLE001
            item["diag"] = {"read": f"head {type(ex).__name__}"}
        if time.time() - t0 > a.budget_sec:
            item["note"] = "سقف الزمن — لم يُفحص"
            res.append(item)
            continue
        if not keys:
            item["note"] = "لا حكمَ صوتيّاً مفهرساً بهذه البصمة (مسار تحويلٍ موثَّق أو حكمٌ بمفتاح آخر)"
        for k in keys[:2]:
            buf = io.StringIO()
            sys.argv = ["promote.py", "--only", k]
            code = 0
            try:
                with contextlib.redirect_stdout(buf):
                    P.main()
            except SystemExit as ex:
                code = ex.code if ex.code is not None else 0
                buf.write(f"\nSystemExit: {ex.code}\n")
            except Exception as ex:  # noqa: BLE001
                code = 1
                buf.write(f"\nEXC {type(ex).__name__}: {ex}\n")
            sys.argv = argv0
            txt = buf.getvalue()
            ok, bad = classify(txt)
            item["runs"].append({"src": k, "ok": ok, "bad": bad[:6], "code": str(code),
                                 "tail": txt.strip().splitlines()[-4:]})
        res.append(item)
        r0 = item["runs"][0] if item["runs"] else None
        print(f"{pk} {e['sha256'][:8]} -> " + (("✅" if r0["ok"] else "⛔ " + " | ".join(r0["bad"][:2])) if r0 else "بلا حكم"))
        sys.stdout.flush()
    out.write_text(json.dumps({"since": a.since, "readFailed": failed, "n": len(res), "results": res},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"كُتب {out} · {len(res)} فهرساً")


if __name__ == "__main__":
    main()
