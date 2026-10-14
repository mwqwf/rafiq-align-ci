#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""زرعُ سورٍ كاملةٍ من متبرِّعٍ في الأصل الحيّ — مرشّحٌ جديدٌ إلى `timings-staging/` وحده (pT · 2026-10-14).

    python tools/index_qa/graft_surahs.py --base timings/qalun/akri_qalun.jz --base-sha b99e3573 \\
        --donor timings-staging/qalun/akri_qalun.f1f1a221.jz --donor-sha f1f1a221 --surahs 28 \\
        --reason "…" [--yes]

**الغاية: ترقيةٌ تدريجيّة.** مرشّحٌ فيه الحيّ نفسُه، ومعه السورُ التي أُصلحت واجتازت السماعَ وحدَها.
أداةٌ جديدةٌ بجانب `graft_surah_range.py` (‏مدى آياتٍ في سورة) ولا تعدّلها ولا تعدّل حارساً. لا تُنشئ زمناً:
كلُّ مدخلٍ في الناتج هو بايتاً مدخلُ الأصل أو مدخلُ المتبرِّع.

**حُرّاسُه (تُرفع بالسبب ولا تُخفَّف):**
1. المتبرِّعُ مشتقٌّ من الأصل: `fromSha256` = بصمةُ الأصل، أو سلسلةُ تحويلاتٍ تنتهي إليها تُجلب وتُتحقَّق حلقةً حلقة
   (‏البصمةُ الفعليّة لكلّ حلقة تطابق ما تدّعيه الحلقةُ التي فوقها، والقارئُ والروايةُ ثابتان).
2. سورُ `--surahs`: مداخلُها في الناتج مطابقةٌ بايتاً لمداخل المتبرِّع.
3. ما خارجها: مطابقٌ بايتاً لمداخل الأصل (‏وتغييرُ المتبرِّع في سورةٍ غيرِ مسمّاةٍ يُتجاهل ولا يدخل الناتج).
4. السورة المزروعة تامّةٌ 1..N بمرجع المصحف (‏`core/quran/.../index.jz`): لا فجوةَ ولا تكرار ولا نصٌّ مغيَّر، وحدودٌ صاعدةٌ بلا تداخل.
5. الترويسة: تحويلٌ جديد (`fromSha256` = الأصل) و`transform.graft` فيه المتبرِّعُ وبصمتُه والسورُ وسلسلةُ النسب ومحرّكُ كلّ سورة
   كما في المتبرِّع (‏يُكتب في `engineBySurah` ما يخالف محرّكَ الفهرس فيلزمه الإحصاء الشامل)، وخرائطُ المصدر/النموذج للسور المزروعة من المتبرِّع.
6. يرفض: قائمةً فارغة · سورةً مكرَّرة · سورةً غيرَ معدَّلةٍ في المتبرِّع · سورةً يعلن المتبرِّعُ إسقاطَها أو نقصَها
   (‏`missing` أو `truncatedTail` أو `declare_gap`) · سورةً غائبةً/ناقصةً في الأصل نفسِه.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_SURAH_MAPS = ("engineBySurah", "sourceBySurah", "sourceTimingBySurah",
               "alignmentModelBySurah", "dualFixEvidenceBySurah")
_TEXT_KEYS = ("text", "textSha256", "textHash")
MAX_CHAIN = 24  # كلّ حلقةٍ تُجلب وتُطابَق بصمتُها الكاملة، فالطولُ لا يُضعف التحقّق؛ سلاسلُ الإصلاح تبلغ 11+ حلقة


def ayah_counts():
    """مرجعُ المصحف: عددُ آيات كلّ سورة من `index.jz` في المستودع (‏114 قيمة)."""
    p = HERE.parent.parent / "core" / "quran" / "src" / "main" / "assets" / "quran" / "index.jz"
    d = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    c = [s["ayahs"] for s in sorted(d["surahs"], key=lambda s: s["n"])]
    if len(c) != 114 or sum(c) != 6236:
        raise SystemExit("⛔ مرجعُ المصحف غيرُ سويّ")
    return c


def _sa(aid):
    s, a = str(aid).split(":")
    return int(s), int(a)


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _by_surah(entries, counts):
    """{سورة: {آية: مدخل}} مع التحقّق من المفاتيح والتكرار."""
    out = {}
    for e in entries:
        try:
            s, a = _sa(e["ayahId"])
        except Exception:                             # noqa: BLE001
            raise SystemExit(f"⛔ مفتاحٌ غيرُ سويّ: {e.get('ayahId')!r}")
        if not (1 <= s <= 114 and 1 <= a <= counts[s - 1]):
            raise SystemExit(f"⛔ {e['ayahId']} خارج مرجع المصحف")
        if a in out.setdefault(s, {}):
            raise SystemExit(f"⛔ {e['ayahId']} مكرَّرة")
        out[s][a] = e
    return out


def parse_surahs(text):
    parts = [p for p in re.split(r"[,\s]+", str(text).strip()) if p]
    if not parts:
        raise SystemExit("⛔ قائمةُ السور فارغة")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        raise SystemExit(f"⛔ --surahs قائمةُ أعداد: {text!r}")
    if len(set(nums)) != len(nums):
        raise SystemExit(f"⛔ سورةٌ مكرَّرة في القائمة: {nums}")
    if any(not 1 <= n <= 114 for n in nums):
        raise SystemExit("⛔ سورةٌ خارج 1..114")
    return sorted(nums)


def verify_lineage(base, donor, base_sha, ancestors):
    """النسبُ حلقةً حلقة. `ancestors`: [{"sha": البصمةُ الفعلية الكاملة, "idx": الفهرس}] من أبِ المتبرِّع صعوداً.
    يُرجع قائمة البصمات (‏من الأب إلى الأصل)."""
    ident = (base.get("riwaya"), base.get("reciterId"))
    if (donor.get("riwaya"), donor.get("reciterId")) != ident:
        raise SystemExit("⛔ الفهرسان لقارئين أو روايتين مختلفتين")
    tr = donor.get("transform") if isinstance(donor.get("transform"), dict) else {}
    want = tr.get("fromSha256")
    chain = []
    for hop in (ancestors or []):
        if not want or hop.get("sha") != want:
            raise SystemExit(f"⛔ حلقةٌ في النسب لا تطابق: المدّعاة {str(want)[:12]} والمجلوبة {str(hop.get('sha'))[:12]}")
        hi = hop["idx"]
        if (hi.get("riwaya"), hi.get("reciterId")) != ident:
            raise SystemExit("⛔ حلقةٌ في النسب لقارئٍ أو روايةٍ أخرى")
        chain.append(want)
        htr = hi.get("transform") if isinstance(hi.get("transform"), dict) else {}
        want = htr.get("fromSha256")
        if len(chain) > MAX_CHAIN:
            raise SystemExit("⛔ سلسلةُ النسب أطول من المسموح")
    if want != base_sha:
        raise SystemExit(f"⛔ المتبرِّع غيرُ مشتقٍّ من الأصل (آخرُ حلقة fromSha256={str(want)[:12]}، والأصل {base_sha[:12]})")
    return chain


def graft(base, donor, base_sha, surahs, ancestors=None, donor_sha=None, counts=None):
    """يُرجع (فهرساً جديداً، تقريراً) أو يرفع SystemExit بالسبب. نقيّةٌ للاختبار (‏الجلب خارجَها)."""
    counts = counts or ayah_counts()
    surahs = sorted(surahs) if not isinstance(surahs, str) else parse_surahs(surahs)
    if not surahs:
        raise SystemExit("⛔ قائمةُ السور فارغة")
    if len(set(surahs)) != len(surahs):
        raise SystemExit(f"⛔ سورةٌ مكرَّرة في القائمة: {surahs}")
    chain = verify_lineage(base, donor, base_sha, ancestors)
    bs, ds = _by_surah(base.get("entries") or [], counts), _by_surah(donor.get("entries") or [], counts)
    dtr = donor.get("transform") if isinstance(donor.get("transform"), dict) else {}
    dmiss = set((donor.get("missing") or {}).get("ids") or [])
    bmiss = set((base.get("missing") or {}).get("ids") or [])
    tails = dtr.get("truncatedTail") or {}
    declared = set()
    for m in re.findall(r"declare_gap:([\d,\s]+)", str(dtr.get("op") or "")):
        declared |= {int(x) for x in re.findall(r"\d+", m)}
    for s in surahs:
        n = counts[s - 1]
        full = list(range(1, n + 1))
        if sorted(ds.get(s, {})) != full:
            raise SystemExit(f"⛔ س{s}: المتبرِّع يُعلنها ناقصةً/غائبة ({len(ds.get(s, {}))}/{n}) — لا تُزرع")
        if any(i.startswith(f"{s}:") for i in dmiss) or str(s) in {str(k) for k in tails} or s in declared:
            raise SystemExit(f"⛔ س{s}: المتبرِّع يعلن إسقاطَها أو نقصَها (missing/truncatedTail/declare_gap)")
        if sorted(bs.get(s, {})) != full or any(i.startswith(f"{s}:") for i in bmiss):
            raise SystemExit(f"⛔ س{s}: غائبةٌ أو ناقصةٌ في الأصل نفسِه — ليست إصلاحاً لحاضرةٍ")
        if all(_canon(ds[s][a]) == _canon(bs[s][a]) for a in full):
            raise SystemExit(f"⛔ س{s}: غيرُ معدَّلةٍ في المتبرِّع (مداخلُها مطابقةٌ للأصل)")
        for a in full:
            for k in _TEXT_KEYS:
                if ds[s][a].get(k) != bs[s][a].get(k):
                    raise SystemExit(f"⛔ س{s}:{a}: حقلُ النصّ {k} يخالف الأصل — لا يُزرع نصٌّ مغيَّر")
        prev = -1
        for a in full:
            st, en = int(ds[s][a]["startMs"]), int(ds[s][a]["endMs"])
            if not (0 <= st < en) or st < prev:
                raise SystemExit(f"⛔ {s}:{a}: حدودٌ غيرُ صاعدة ({st}→{en}، والسابقة تنتهي {prev})")
            prev = en
    # الناتج: لكلّ سورة بترتيبها؛ المسمّاةُ من المتبرِّع والباقي من الأصل.
    out_entries = []
    for s in sorted(set(bs) | set(ds)):
        src = ds if s in surahs else bs
        if s not in src:
            continue
        out_entries.extend(src[s][a] for a in sorted(src[s]))
    # ضماناتٌ نهائيّة على الناتج المبنيّ نفسِه (لا على نيّتنا).
    os_ = _by_surah(out_entries, counts)
    for s in set(bs) | set(os_):
        want = ds if s in surahs else bs
        if sorted(os_.get(s, {})) != sorted(want.get(s, {})) or any(
                _canon(os_[s][a]) != _canon(want[s][a]) for a in os_.get(s, {})):
            raise SystemExit(f"⛔ س{s}: الناتجُ لا يطابق مصدرَه بايتاً")
    if len(out_entries) != len(base.get("entries") or []):
        raise SystemExit("⛔ عددُ المداخل تغيّر")
    out = dict(base)
    out["entries"] = out_entries
    out["lowCount"] = sum(1 for e in out_entries if e.get("confBand") == "LOW")
    # ترويسةُ السور: كما في المتبرِّع للمزروعة، وكما في الأصل لغيرها — فلا يُخفى محرّك.
    engines = {}
    for f in _SURAH_MAPS:
        bm, dm = base.get(f), donor.get(f)
        if f != "engineBySurah" and not isinstance(bm, dict) and not any(
                isinstance(dm, dict) and str(s) in dm for s in surahs):
            continue
        m = dict(bm) if isinstance(bm, dict) else {}
        for s in surahs:
            k = str(s)
            m.pop(k, None)
            if isinstance(dm, dict) and k in dm:
                m[k] = dm[k]
        if f == "engineBySurah":
            for s in surahs:
                k = str(s)
                eng = (dm or {}).get(k) if isinstance(dm, dict) else None
                eng = eng or donor.get("engineVersion")
                engines[k] = eng
                if eng and eng != base.get("engineVersion"):
                    m[k] = eng
        out[f] = m
    moved = sum(1 for s in surahs for a in ds[s] if _canon(ds[s][a]) != _canon(bs[s][a]))
    rep = {"surahs": surahs, "movedEntries": moved, "engines": engines, "lineage": chain,
           "donorSha256": donor_sha, "donorEngineVersion": donor.get("engineVersion")}
    return out, rep


def build_transform(base, out, base_sha, base_key, donor_key, rep, reason, by="graft_surahs"):
    prior = base.get("transform")
    meta = dict(prior) if isinstance(prior, dict) else ({"opAsGiven": prior} if prior else {})
    for k in ("qaDispatch",):
        meta.pop(k, None)
    from rename_reciter import entries_sha
    surahs = rep["surahs"]
    meta.update({
        "op": "graft_surahs:" + ",".join(map(str, surahs)),
        "fromSha256": base_sha, "fromKey": base_key,
        "entriesSha256": entries_sha(out["entries"]),
        "parentEntriesSha256": entries_sha(base["entries"]),
        "movedEntries": rep["movedEntries"], "addedEntries": 0, "removedEntries": 0,
        "reason": reason, "by": by, "at": int(time.time() * 1000),
        "graft": {"surahs": surahs, "donorKey": donor_key, "donorSha256": rep["donorSha256"],
                  "donorEngineVersion": rep["donorEngineVersion"], "engineBySurah": rep["engines"],
                  "lineage": rep["lineage"], "baseKey": base_key, "baseSha256": base_sha,
                  "by": "graft_surahs"},
    })
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--donor", required=True)
    ap.add_argument("--donor-sha", required=True)
    ap.add_argument("--surahs", required=True, help="قائمةٌ مفصولةٌ بفاصلة")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    surahs = parse_surahs(a.surahs)
    import promote
    cl, bucket = promote.s3()

    def load(key, sha):
        body = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
        full = hashlib.sha256(body).hexdigest()
        if not full.startswith(sha):
            raise SystemExit(f"⛔ البصمة لا تطابق {key}: الحيّة {full[:16]} والمطلوبة {sha}")
        return json.loads(gzip.decompress(body).decode("utf-8")), full

    base, bfull = load(a.base, a.base_sha)
    donor, dfull = load(a.donor, a.donor_sha)
    # جلبُ النسب حلقةً حلقة بالبصمة الكاملة المدّعاة.
    anc, cur = [], donor
    while True:
        tr = cur.get("transform") if isinstance(cur.get("transform"), dict) else {}
        want, fkey = tr.get("fromSha256"), tr.get("fromKey")
        if want == bfull or not want or len(anc) >= MAX_CHAIN:
            break
        if not fkey:
            raise SystemExit("⛔ حلقةٌ في النسب بلا fromKey — لا يُتحقَّق منها")
        idx, full = load(fkey, want[:16])
        if full != want:
            raise SystemExit(f"⛔ بصمةُ {fkey} الفعليّة {full[:12]} لا تطابق المدّعاة {want[:12]}")
        anc.append({"sha": full, "idx": idx})
        cur = idx
    out, rep = graft(base, donor, bfull, surahs, anc, dfull)
    out["transform"] = build_transform(base, out, bfull, a.base, a.donor, rep, a.reason)
    blob = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    new_sha = hashlib.sha256(blob).hexdigest()
    target = f"timings-staging/{out.get('riwaya')}/{out.get('reciterId')}.{new_sha[:8]}.jz"
    print(f"سور {surahs} من المتبرِّع {dfull[:8]} (نسب {len(anc)} حلقة) في الأصل {bfull[:8]}: "
          f"مداخلُ متحرّكة {rep['movedEntries']} · محرّكات {rep['engines']}")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new_sha[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob, ContentType="application/gzip",
                  Metadata={"source": "graft_surahs", "from": bfull[:12], "donor": dfull[:12]})
    got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
    print(f"↑ رُفع · الدلو {got} · المحلّي {len(blob)} → {'✅' if got == len(blob) else '❌'}")
    print(f"بصمة الناتج الكاملة: {new_sha}")


if __name__ == "__main__":
    main()
