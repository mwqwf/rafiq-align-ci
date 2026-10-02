# -*- coding: utf-8 -*-
"""تصحيحُ حدود مرشّحٍ بما اتّفق عليه نموذجا CTC المثبَّتان — محرّك `ctc-dualfix-1`.

⭐ **أمرُ المنسّق (‏2026-10-02 · عاصم ص):** مرشّحُ `ctc-heardmap-1` اجتاز الملوحَ الأربعة، لكنّ شاهدَ
النوافذ (‏`window_census_witness`) وجد في نحو عشر آياتٍ أنّ النموذجين العامَّ `jonatasgrosman` والقرآنيَّ
`rabah2026` يتّفقان معاً ضدّ حدود المرشّح بثوانٍ. فهذا المحرّك **يقيس** كلَّ آيةٍ من السورة في نافذتها
من المرشّح (‏السابقة→الآية→اللاحقة، كما يقيس الشاهد تماماً) بالنموذجين، ويأخذ الحدَّ **حيث اتّفقا**
(‏بتسامح الشاهد نفسِه `START_TOL`/`END_TOL` وثقةٍ ≥ `TARGET_CONF` في كليهما)، ويُبقي حدَّ المرشّح حيث
لا اتّفاق. **لا حدَّ مختلَقاً**: كلُّ حدٍّ إمّا مقيسٌ باتّفاق نموذجين مستقلّين أو موروثٌ من المرشّح بنسبه.

## الحُرّاس (‏`fuse`)
- الحدودُ تُدمج حدّاً حدّاً فتبقى المداخلُ متّصلةً رتيبةً بلا تداخل (‏نهايةُ k = بدايةُ k+1).
- حدٌّ يشهد له الجاران باتّفاقٍ (‏نهايةُ k وبدايةُ k+1 كلتاهما مقيستان) يؤخذ وسطُهما إن تقاربا، وإلا
  يبقى حدُّ المرشّح — فالخلافُ ليس اتّفاقاً.
- مدّةُ كلّ آيةٍ بين `DUR_LO`×و`DUR_HI`× المتوقَّع (‏وسيطُ م.ث/حرف من المرشّح نفسِه)؛ وما خالف تُردّ
  حدودُه إلى المرشّح ويُعاد الفحص حتى يستقرّ — وإن لم يستقرّ فالسورةُ لا تُكتب.
- الدليلُ كاملاً (‏قياسُ كلّ نموذجٍ لكلّ آية ومصدرُ كلّ حدّ) يُكتب في `dualFixEvidence` ويُنقل إلى
  الفهرس في `dualFixEvidenceBySurah` فلا يُخفى شيء.
"""
from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "index_qa"))

import window_census_witness as X   # noqa: E402

ENGINE = "ctc-dualfix-1"
BASE_ENGINES = ("ctc-heardmap-1",)
MAX_PASSES = 200


def agreed_bounds(meas, tol_start=X.START_TOL, tol_end=X.END_TOL, min_conf=X.TARGET_CONF):
    """[بداية، نهاية] المتّفقُ عليهما بين النموذجين لآيةٍ واحدة، أو None.
    `meas` = {'generic': (s, e, conf), 'quran': (s, e, conf)} أو ناقص."""
    g, q = meas.get("generic"), meas.get("quran")
    if not g or not q:
        return None
    if g[2] < min_conf or q[2] < min_conf:
        return None
    if abs(g[0] - q[0]) > tol_start or abs(g[1] - q[1]) > tol_end:
        return None
    return [(g[0] + q[0]) // 2, (g[1] + q[1]) // 2]


def fuse(base, measurements, chars, rate, tol_start=X.START_TOL, tol_end=X.END_TOL,
         min_conf=X.TARGET_CONF, lo=X.DUR_LO, hi=X.DUR_HI):
    """يدمج حدودَ المرشّح `base` (‏قائمةُ [s, e] لكلّ آيةٍ بالترتيب) مع قياسات النموذجين.
    يُرجع (‏حدودٌ جديدة [s, e]، مصادرُ كلّ حدٍّ، تفصيلُ كلّ آية) أو يرفع ValueError."""
    n = len(base)
    if n == 0 or len(measurements) != n or len(chars) != n:
        raise ValueError("base, measurements and chars must describe the same ayahs")
    for k in range(1, n):
        if base[k][0] < base[k - 1][1]:
            raise ValueError("base candidate overlaps")
    agreed = [agreed_bounds(m or {}, tol_start, tol_end, min_conf) for m in measurements]
    # حدودُ المرشّح: b[0] = بدايةُ الأولى، b[k] = نهايةُ k = بدايةُ k+1، b[n] = نهايةُ الأخيرة.
    # (‏وإن لم يكن المرشّحُ متّصلاً فحدُّ الفاصل يؤخذ من بداية اللاحقة، والفجوةُ تُغلق.)
    base_b = [base[0][0]] + [base[k][0] for k in range(1, n)] + [base[n - 1][1]]
    frozen = [False] * n          # آيةٌ رُدّت إلى حدود المرشّح بعد مخالفة المدّة

    def boundary(k):
        """الحدُّ رقم k ومصدرُه: 0 = بدايةُ الأولى … n = نهايةُ الأخيرة."""
        left = agreed[k - 1][1] if k >= 1 and agreed[k - 1] and not frozen[k - 1] else None
        right = agreed[k][0] if k < n and agreed[k] and not frozen[k] else None
        if left is not None and right is not None:
            if abs(left - right) <= tol_end:
                return (left + right) // 2, "agreed-both"
            return base_b[k], "conflict-base"
        if left is not None:
            return left, "agreed-end"
        if right is not None:
            return right, "agreed-start"
        return base_b[k], "base"

    for _ in range(MAX_PASSES):
        b, src = zip(*[boundary(k) for k in range(n + 1)])
        b, src = list(b), list(src)
        bad = None
        for k in range(n):
            dur, exp = b[k + 1] - b[k], rate * chars[k]
            touched = b[k] != base_b[k] or b[k + 1] != base_b[k + 1]
            # حارسُ المدّة على ما تغيّر وحده؛ وما بقي على حدود المرشّح يبقى بنسبه (‏اجتاز بنيتَه).
            if dur <= 0 or (touched and not lo * exp <= dur <= hi * exp):
                bad = k; break
        if bad is None:
            # الرتابةُ الصارمة: كلُّ حدٍّ بعد سابقه
            if all(b[k + 1] > b[k] for k in range(n)):
                break
            bad = next(k for k in range(n) if b[k + 1] <= b[k])
        if frozen[bad]:
            # الآيةُ على حدود المرشّح وما زالت مخالفة: جارتُها المقيسة هي السبب
            nb = [j for j in (bad - 1, bad + 1) if 0 <= j < n and not frozen[j] and agreed[j]]
            if not nb:
                raise ValueError(f"ayah {bad + 1} violates duration or monotonicity even on base boundaries")
            for j in nb:
                frozen[j] = True
        else:
            frozen[bad] = True
    else:
        raise ValueError("fusion did not converge")
    bounds = [[b[k], b[k + 1]] for k in range(n)]
    detail = []
    for k in range(n):
        detail.append({"ayah": k + 1, "base": list(base[k]), "agreed": agreed[k], "reverted": bool(frozen[k]),
                       "taken": bounds[k], "startSource": src[k], "endSource": src[k + 1]})
    return bounds, src, detail


def measure_all(pcm_all, idx, surah, total_ms, log=print):
    """قياسُ كلّ آيةٍ في نافذتها بالنموذجين (‏النموذجُ خارجَ الحلقة كما في الشاهد)."""
    import ci_spoken_census as W
    n = sum(1 for e in idx["entries"] if e["ayahId"].startswith(f"{surah}:"))
    plans = {}
    for k in range(1, n + 1):
        aid = f"{surah}:{k}"
        try:
            plans[aid] = X.plan(idx, aid, total_ms)
        except ValueError as exc:
            log(f"⚠️ {aid}: لا نافذة ({exc})")
    meas = {aid: {} for aid in plans}
    models = {}
    for name in ("generic", "quran"):
        model = W.configure_generic() if name == "generic" else W.Q.configure()
        models[name] = {k: model[k] for k in ("id", "revision", "weightsSha256", "license")}
        for aid, (ids, (start, end), texts) in plans.items():
            actual = texts if name == "generic" else [W.Q.reference_text(t) for t in texts]
            pcm = pcm_all[start * 16:end * 16]
            try:
                raw = W.C._segment(W.C._emissions(pcm), len(pcm), actual)
            except Exception as exc:                 # noqa: BLE001
                log(f"⚠️ {name} {aid}: {str(exc)[:120]}"); continue
            ents = [(start + int(st * 1000), start + int(en * 1000), W.C._conf(sc)) for (st, en, sc) in raw]
            ents = [(s_, ents[i + 1][0] if i + 1 < len(ents) else e_, c_) for i, (s_, e_, c_) in enumerate(ents)]
            pos = ids.index(aid)
            meas[aid][name] = [ents[pos][0], ents[pos][1], round(ents[pos][2], 4)]
            meas[aid].setdefault("context", {})[name] = [[cid, s_, e_, round(c_, 3)] for cid, (s_, e_, c_) in zip(ids, ents)]
            log(f"{name} {aid} {ents[pos][0]} {ents[pos][1]} {ents[pos][2]:.3f}")
        W.C._M.clear(); gc.collect()
    return meas, models, {aid: {"contextAyahIds": p[0], "windowMs": p[1]} for aid, p in plans.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-key", required=True, help="مفتاحُ المرشّح الأساس في timings-staging (‏heardmap)")
    ap.add_argument("--url", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    if os.environ.get("CTC_INT8") != "0" or os.environ.get("CTC_THREADS") != "2":
        raise ValueError("float32 and two threads are required (CTC_INT8=0 CTC_THREADS=2)")
    if not a.base_key.startswith("timings-staging/") or a.base_key.count("/") != 2:
        raise ValueError("base key must be a staged candidate")
    import promote as P
    import run as R
    from common import load_index, load_text, norm, surah_slice
    from validate import band, check_surah
    cl, bucket = P.s3()
    body = cl.get_object(Bucket=bucket, Key=a.base_key)["Body"].read()
    idx = json.loads(gzip.decompress(body)); base_sha = hashlib.sha256(body).hexdigest()
    s = a.surah
    if idx.get("riwaya") != a.riwaya or (idx.get("engineBySurah") or {}).get(str(s)) not in BASE_ENGINES:
        raise ValueError("base candidate must carry the surah by a heard-map engine in this riwaya")
    rows = [e for e in idx["entries"] if e["ayahId"].startswith(f"{s}:") and e.get("startMs") is not None]
    begin, stop, _ = surah_slice(load_index(), s)
    n = stop - begin
    if [e["ayahId"] for e in rows] != [f"{s}:{k}" for k in range(1, n + 1)]:
        raise ValueError("base candidate must hold every ayah of the surah in order")
    if {e["fileRef"] for e in rows} != {a.url}:
        raise ValueError("base candidate fileRef differs from the given url")
    os.makedirs(a.out_dir, exist_ok=True)
    audio = os.path.join(a.out_dir, f"{s:03d}.mp3")
    if not os.path.exists(audio) or os.path.getsize(audio) < 10_000:
        from ctc_gapsplit import fetch
        fetch(a.url, audio)
    sha = hashlib.sha256(open(audio, "rb").read()).hexdigest()
    if sha != idx["audioSha256"][s - 1]:
        raise ValueError("downloaded audio differs from the base candidate's audioSha256")
    pcm_all = R._full_decode_pcm(audio)
    total_ms = len(pcm_all) // 16
    meas, models, plans = measure_all(pcm_all, idx, s, total_ms)
    refs = load_text(a.riwaya)[begin:stop]
    chars = [len(norm(t).replace(" ", "")) for t in refs]
    rate, _ = X._rate(idx, s)
    base = [[e["startMs"], e["endMs"]] for e in rows]
    bounds, src, detail = fuse(base, [meas.get(f"{s}:{k}") for k in range(1, n + 1)], chars, rate)
    entries = []
    for k, (st, en) in enumerate(bounds):
        e = rows[k]; d = detail[k]
        if d["agreed"] and not d["reverted"] and (d["startSource"] != "base" or d["endSource"] != "base"):
            conf = min(meas[f"{s}:{k + 1}"]["generic"][2], meas[f"{s}:{k + 1}"]["quran"][2], 0.74)
        else:
            conf = float(e.get("conf") or 0.0)
        entries.append({"ayahIdx": k, "startMs": int(st), "endMs": int(en), "conf": round(conf, 3),
                        "snapped": not e.get("startApprox", False)})
    issues = check_surah(entries, chars, total_ms)
    bands = {}
    for e in entries:
        bands[band(e["conf"])] = bands.get(band(e["conf"]), 0) + 1
    changed = sum(1 for k in range(n) if bounds[k] != base[k])
    evidence = {"engine": ENGINE, "baseKey": a.base_key, "baseSha256": base_sha, "baseEngine": "ctc-heardmap-1",
                "sourceSha256": sha, "totalMs": total_ms, "models": models,
                "runtime": dict(X.RUNTIME), "canonicalTextChanged": False,
                "thresholds": {"startTol": X.START_TOL, "endTol": X.END_TOL, "minConf": X.TARGET_CONF,
                               "durLo": X.DUR_LO, "durHi": X.DUR_HI, "rateMsPerChar": rate},
                "windows": plans, "measurements": meas, "perAyah": detail,
                "changedAyat": changed, "boundarySources": src}
    res = {"surah": s, "riwaya": a.riwaya, "engine": ENGINE, "totalMs": total_ms, "fileRef": a.url,
           "sha256": sha, "vadRel": None, "vadVersion": None, "entries": entries, "issues": issues,
           "bands": bands, "dualFixEvidence": evidence}
    out = os.path.join(a.out_dir, f"s{s:03d}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    lines = [f"# dualfix س{s}: غُيّرت حدودُ {changed}/{n} آية · {bands} · {len(issues)} ملاحظة"]
    for d in detail:
        lines.append(f"{s}:{d['ayah']}\t{d['base']}\t→\t{d['taken']}\t{d['startSource']}/{d['endSource']}"
                     f"\t{'رُدّت' if d['reverted'] else ''}")
    lines += ["⚠️ " + i for i in issues]
    with open(os.path.join(a.out_dir, f"dualfix_s{s:03d}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines)); print(f"كُتب: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
