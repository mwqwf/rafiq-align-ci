#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سبرٌ حيٌّ للقراءة فقط: هل يُحمَّل شاهدُ Whisper الحقيقيّ، وهل تطابق بصمتُه `audioSha256`، وماذا يحكم `timing_repair.evidence_error`.

    python tools/index_qa/witness_live_probe.py --key timings/hafs/kurdi.jz --surah 4 --runs 42772755657,42785017500

لا يكتب شيئاً (‏لا دلوَ ولا مستودعاً)؛ يقرأ مخرَجَ تشغيلةٍ ناجحةٍ لـ`whisper_witness.yml` عبر `pin_heard.load_witness`
(‏الطريقِ نفسِه الذي تعيد به البوّابةُ حكمَها) وفهرساً واحداً من الدلو. ويبني من الشاهد **مدخلاً مصنوعاً**: مسابيرُ تدّعي أنّ
شاهداً سمع في بدء آيةٍ نصَّ آيةٍ أخرى — حيث سمع الشاهدُ فعلاً مطلعَ آيةٍ في زمنٍ بعينه — ثمّ يعرضه على الدالّة نفسِها.
وضابطٌ سلبيّ: المدخلُ نفسُه بحقلٍ مبدَّلٍ يجب أن يُردّ."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, help="مفتاح فهرسٍ في الدلو يُقابَل به audioSha256")
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--runs", required=True, help="تشغيلاتٌ بفواصل")
    ap.add_argument("--timing-repair-sha",
                    help="بصمةُ إيداعٍ (40 خانة) يُجلب منها `tools/index_qa/timing_repair.py` ويُستورد — لفحص كودٍ لم يدخل main بعد")
    a = ap.parse_args()
    if a.timing_repair_sha:
        import base64, re, subprocess, tempfile
        if not re.fullmatch(r"[0-9a-f]{40}", a.timing_repair_sha):
            raise SystemExit("⛔ --timing-repair-sha بصمةُ إيداعٍ كاملة (40 خانة) لا فرعٌ متحرّك")
        r = subprocess.run(["gh", "api", f"repos/mwqwf/rafiq-align-ci/contents/tools/index_qa/timing_repair.py?ref={a.timing_repair_sha}",
                            "--jq", ".content"], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"⛔ تعذّر جلب timing_repair.py: {r.stderr[:200]}")
        d = tempfile.mkdtemp(prefix="tr_")
        Path(d, "timing_repair.py").write_bytes(base64.b64decode(r.stdout))
        sys.path.insert(0, d)
        print(f"timing_repair.py من الإيداع {a.timing_repair_sha[:10]}")
    import heard_gate as HG
    import pin_heard as PH
    import timing_repair as T
    from run import s3

    cl, b = s3()
    idx = json.loads(gzip.decompress(cl.get_object(Bucket=b, Key=a.key)["Body"].read()).decode("utf-8"))
    want = (idx.get("audioSha256") or [None] * 114)[a.surah - 1]
    print(f"الفهرس {a.key}: {idx.get('riwaya')}/{idx.get('reciterId')} · audioSha256[{a.surah}] = {str(want)[:16]}…")
    runs, wits = [r.strip() for r in a.runs.split(",") if r.strip()], {}
    for r in runs:
        try:
            w = PH.load_witness(r, a.surah)
        except (SystemExit, Exception) as e:                      # noqa: BLE001
            print(f"[{r}] لم يُحمَّل: {str(e)[:300]}")
            continue
        wits[r] = w
        toks = sum(len(HG._wtoks(x)) for x in (w.get("ayahs") or {}).values())
        print(f"[{r}] حُمّل ✔ · surah={w.get('surah')} riwaya={w.get('riwaya')} model={w.get('model')} "
              f"{w.get('computeType')} · sha256={str(w.get('sha256'))[:16]}… · "
              f"تطابق audioSha256: {'نعم' if w.get('sha256') == want else 'لا'} · نوافذ={len(w.get('ayahs') or {})} كلمات={toks}")
    if not wits:
        print("لا شاهدَ محمَّل — لا مدخلَ يُصنع.")
        return
    # مواضع سمع الشاهدُ فيها مطلعَ آيةٍ (‏W_K كلماتٍ متّصلة) — مادّةُ المدخل المصنوع.
    riw = idx.get("riwaya") or "hafs"
    k, n = PH.W_K, None
    import promote
    n = promote._AYAH_COUNTS[a.surah - 1]
    first = next(iter(wits.values()))
    toks = [t for x in (first.get("ayahs") or {}).values() for t in HG._wtoks(x)]
    hits = []
    for o in range(1, n + 1):
        ow = HG.disputed_ref_words(riw, a.surah, o)
        if len(ow) < k:
            continue
        for i in range(len(toks) - k + 1):
            if [t[0] for t in toks[i:i + k]] == ow[:k]:
                hits.append((o, toks[i][1]))
                break
    print(f"مطالعُ آياتٍ سمعها الشاهد الأوّل: {hits}")
    pick, last = [], -9
    for o, t in sorted(hits):
        if o - last >= 2:
            pick.append((o, t))
            last = o
    pick = pick[:3]
    off = 2 if all(o + 2 <= n for o, _ in pick) else -2
    probes = [{"ayah": o + off, "startMs": int(t), "heardAyah": o} for o, t in pick]
    print(f"المسابير المصنوعة ({len(probes)}): {probes}")
    rec = {"probes": probes,
           "witnesses": {r: {kk: w.get(kk) for kk in HG.DISPUTED_SRC_KEYS} for r, w in wits.items()}}
    print("evidence_error(مدخلٌ من الشاهد المحمَّل حرفاً):", T.evidence_error(idx, a.surah, rec))
    bad = copy.deepcopy(rec)
    r0 = next(iter(bad["witnesses"]))
    bad["witnesses"][r0]["fileRef"] = str(bad["witnesses"][r0]["fileRef"]) + "#مبدَّل"
    print("ضابطٌ سلبيّ (fileRef مبدَّل):", T.evidence_error(idx, a.surah, bad))


if __name__ == "__main__":
    main()
