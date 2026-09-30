#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قسمةُ المدخل الذي ابتلع جارتَه — محاذاةٌ قسريّةٌ بـCTC على **نافذة الجارتين وحدها**.

⭐ **سببُه مقيسٌ 2026-09-29** (`tools/index_qa/gap_probe.py` على المنشور كلِّه):
من 120 آيةً غائبةً داخل سورٍ حاضرة **لا واحدةَ لها فجوةٌ بين جارتَيها** (fill=0)،
و**86 فجوتُها صفر**: نهايةُ السابقة = بدايةُ اللاحقة. ⇒ صوتُ الآية الغائبة **داخلَ
مدخل جارتها**، فالجارةُ في المنشور تمتدّ على آيتين (عطبُ توقيتٍ حيّ فوق الغياب).
والمحرّكان عجزا عن الآية **في السورة كلّها**؛ أمّا نافذةٌ نعرف أنّها تحوي النصوصَ
الثلاثة بالترتيب (السابقة · الغائبة · اللاحقة) فمحاذاةُ نصٍّ معلومٍ فيها أيسرُ بكثير.

⛔ **ما لا يفعله:** لا يلمس مدخلاً غيرَ الجارتين، ولا يحرّك بدايةَ السابقة ولا نهايةَ
اللاحقة (حدّا النافذة من الأب نفسِه)، ولا يولّد نصّاً (النصُّ من الرواية).
⛔ **حُرّاسٌ قبل أيّ قبول** — وما لم يجتزها يبقى غائباً ويُسمّى:
   ١. ثقةُ CTC لكلّ آيةٍ جديدة ≥ 0.45 (حدُّ MED في `_conf`).
   ٢. مدّةُ كلّ آيةٍ جديدة بين 0.5× و2.0× المتوقَّع (حروفُها × معدّلُ القارئ في السورة).
   ٣. الجارتان بعد القسمة لا تنكمش إحداهما دون 0.5× متوقَّعها.
   ٤. لا HIGH بلا برهان صمت (D-025): الثقةُ تُسقَف 0.74 ما لم يقع الحدُّ في صمت.
⚖️ والحكمُ الحاسمُ للبوّابة الصوتيّة (مطالع · أربعة ملوح · إحصاءٌ شامل · عتبة 5%).

المخرَج: `s<سورة>.json` بصيغة `batch_run` نفسِها (السورةُ كاملةً: مداخلُ الأب كما هي
إلا الجارتين المقسومتين، والمقسومُ مضاف) ⇒ يدمجه `splice_surah.py` بحرّاسه.

    python tools/alignment_v3/ctc_gapsplit.py --index parent.jz --surahs 55,74 \
        --riwaya warsh --out-dir tools/alignment/work/batch_<id>
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import statistics
import sys
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
from ctc_seg import SR, _conf, _emissions, _segment  # noqa: E402
from common import load_index, load_text, norm, to_wav16k  # noqa: E402
from vad import read_wav, silences, snap_to_silence  # noqa: E402

MIN_CONF = 0.45
DUR_LO, DUR_HI = 0.5, 2.0
NEIGH_LO = 0.5
ABSORBED_MS = 400
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}
BAND_CONF = {"HIGH": 0.85, "MED": 0.6, "LOW": 0.4}


def chars(t: str) -> int:
    return len(norm(t).replace(" ", ""))


def fetch(url: str, dst: str) -> None:
    last = None
    for _ in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r, \
                    open(dst, "wb") as f:
                want = int(r.headers.get("Content-Length") or 0)
                f.write(r.read())
            if not want or os.path.getsize(dst) == want:
                return
            last = RuntimeError(f"مبتور {os.path.getsize(dst)} من {want}")
        except Exception as ex:                        # noqa: BLE001
            last = ex
    raise RuntimeError(f"تعذّر تنزيل {url}: {last}")


def plan_splits(ents: dict, n: int, text_of, rate: float):
    """الغياباتُ المبتلعة في سورة: (b0, b1, prev, next) لكلّ مدىً غائبٍ بين جارتين فجوتُهما صفر."""
    out, a = [], 1
    while a <= n:
        if a in ents:
            a += 1
            continue
        b0 = a
        while a <= n and a not in ents:
            a += 1
        b1 = a - 1
        p, q = ents.get(b0 - 1), ents.get(b1 + 1)
        if p and q and q["startMs"] - p["endMs"] < ABSORBED_MS:
            out.append((b0, b1))
    return out


def split_window(x: np.ndarray, p: dict, q: dict, texts: list[str]):
    """يحاذي النصوص (السابقة · الغائبات · اللاحقة) على [بدء السابقة، نهاية اللاحقة].
    يُرجع حدودَ البدء المطلقة وثقاتِها، أو يرمي إن تعذّر."""
    ws, we = int(p["startMs"]), int(q["endMs"])
    clip = x[ws * SR // 1000: we * SR // 1000]
    segs = _segment(_emissions(clip), len(clip), texts)
    return [(ws + int(st * 1000), ws + int(en * 1000), _conf(sc)) for st, en, sc in segs]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--surahs", required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    idx = json.loads(gzip.decompress(open(a.index, "rb").read()).decode("utf-8"))
    qidx = load_index()
    text = load_text(a.riwaya)
    report = []
    for s in [int(v) for v in a.surahs.split(",") if v.strip()]:
        meta = next(m for m in qidx["surahs"] if m["n"] == s)
        st0, n = meta["start"], meta["ayahs"]
        rows = [e for e in idx["entries"] if int(e["ayahId"].split(":")[0]) == s]
        ents = {int(e["ayahId"].split(":")[1]): dict(e) for e in rows
                if e.get("startMs") is not None and e.get("endMs") is not None}
        if not ents:
            report.append(f"س{s}: لا مداخلَ في الأب — ليست من هذا الباب")
            continue
        t_of = lambda k: text[st0 + k - 1]              # noqa: E731
        rates = [(ents[k]["endMs"] - ents[k]["startMs"]) / max(1, chars(t_of(k))) for k in ents]
        rate = statistics.median(rates)
        splits = plan_splits(ents, n, t_of, rate)
        if not splits:
            report.append(f"س{s}: لا غيابَ مبتلعاً بين جارتين")
            continue
        refs = {e.get("fileRef") for e in rows}
        if len(refs) != 1:
            report.append(f"س{s}: ⛔ روابطُ صوتٍ متعدّدة في السورة {refs} — لا قسمة")
            continue
        url = refs.pop()
        mp3 = os.path.join(a.out_dir, f"g{s:03d}.mp3")
        fetch(url, mp3)
        sha = hashlib.sha256(open(mp3, "rb").read()).hexdigest()
        wav = to_wav16k(mp3)
        x = read_wav(wav).astype(np.float32)
        sil = silences(wav)
        added = []
        for b0, b1 in splits:
            p, q = ents[b0 - 1], ents[b1 + 1]
            ks = [b0 - 1] + list(range(b0, b1 + 1)) + [b1 + 1]
            try:
                segs = split_window(x, p, q, [norm(t_of(k)) for k in ks])
            except Exception as ex:                    # noqa: BLE001
                report.append(f"س{s}:{b0}-{b1}: تعذّرت المحاذاة — {str(ex)[:80]}")
                continue
            starts = [p["startMs"]] + [sg[0] for sg in segs[1:]]
            ends = starts[1:] + [q["endMs"]]
            why = None
            for i, k in enumerate(ks):
                dur, exp = ends[i] - starts[i], chars(t_of(k)) * rate
                if i in (0, len(ks) - 1):
                    if dur < NEIGH_LO * exp:
                        why = f"الجارة {s}:{k} تنكمش إلى {dur}م.ث والمتوقَّع {exp:.0f}"
                else:
                    if segs[i][2] < MIN_CONF:
                        why = f"{s}:{k} ثقةُ CTC {segs[i][2]} < {MIN_CONF}"
                    elif not (DUR_LO * exp <= dur <= DUR_HI * exp):
                        why = f"{s}:{k} مدّتُها {dur}م.ث والمتوقَّع {exp:.0f} (خارج {DUR_LO}–{DUR_HI}×)"
                if why:
                    break
            if why:
                report.append(f"س{s}:{b0}-{b1}: ⛔ رُدّت — {why}")
                continue
            p["endMs"] = starts[1]
            q["startMs"] = starts[-1]
            for i, k in enumerate(ks[1:-1], start=1):
                t, on_sil = snap_to_silence(starts[i], sil, tolerance_ms=300)
                conf = segs[i][2] if on_sil else min(segs[i][2], 0.74)
                ents[k] = {"startMs": int(starts[i]), "endMs": int(ends[i]), "conf": conf,
                           "snapped": bool(on_sil)}
            added.append(f"{b0}" if b0 == b1 else f"{b0}-{b1}")
            report.append(f"س{s}:{b0}-{b1}: ✅ قُسمت · " + " · ".join(
                f"{s}:{k} {starts[i]}–{ends[i]}" for i, k in enumerate(ks)))
        if not added:
            continue
        out_rows = []
        for k in range(1, n + 1):
            e = ents.get(k)
            if e is None:
                out_rows.append({"ayahIdx": k - 1, "startMs": None, "endMs": None, "conf": 0.0})
                continue
            conf = e.get("conf")
            if conf is None:
                conf = BAND_CONF.get(e.get("confBand"), 0.6)
            out_rows.append({"ayahIdx": k - 1, "startMs": int(e["startMs"]), "endMs": int(e["endMs"]),
                             "conf": float(conf), "snapped": not e.get("startApprox", False)
                             if "snapped" not in e else bool(e["snapped"]),
                             "matched": 0, "total": len(norm(t_of(k)).split())})
        with open(os.path.join(a.out_dir, f"s{s:03d}.json"), "w", encoding="utf-8") as f:
            json.dump({"fileRef": url, "sha256": sha, "surah": s, "engine": "ctc-gapsplit-1",
                       "gapsplit": added, "entries": out_rows}, f, ensure_ascii=False)
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
