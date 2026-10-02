#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎚️☁️ **`vad_filter` في «سمّع معي» السحابيّ — ذراعان على المقطع نفسِه** (‏`FeatureFlags.RECITE_CLOUD_VAD` · المستشار · 2026-10-02).

يسجّل جهازاً مؤقّتاً (‏كما يفعل `cloud_stream_probe.py` — بلا أسرار: العنوانُ علنيٌّ في التطبيق)، ويرسل نافذةَ
3.6ث من وسط كلّ بندٍ (‏شكلُ نافذة الحلقة) مرّتين إلى `/v1/tasmi/stream`: بلا رأس، ثمّ بـ`x-tasmi-vad: 1`
(‏وهو ما يفعله المفتاحُ في الجهاز) — ويقيس الزمنَ والنصَّ: `oov` (‏كلماتٌ ليست في الآية) · `words` ·
`agree` بين الذراعين · والفارغ. ثمّ يمحو الجهاز.

⚠️ الكلفة: نداءاتُ Workers AI على حساب المالك (‏دقائقُ صوتٍ معدودة — تُسمّى في التقرير)؛ والحصّةُ 90 طلباً/دقيقة
ونُرسل واحداً كلَّ ثانية. ⛔ لا يُخزَّن الصوتُ في الخادم (‏مسارُ البثّ يمرّر وينسى).
"""
import argparse
import io
import json
import os
import statistics as st
import sys
import time
import urllib.error
import urllib.request
import wave

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from speed_ab import norm_words, edits, SR  # noqa: E402

BASE = "https://mushafak-api.mushafak.workers.dev"
UA = "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 7 Build/UQ1A)"


def call(method, path, data=None, headers=None, timeout=40):
    h = {"user-agent": UA, **(headers or {})}
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.time() - t0
    except Exception as e:
        return None, str(e).encode(), time.time() - t0


def wav_bytes(x):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return b.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", required=True, help="مجلّدُ بنود (يُكرَّر: wav · wavn)")
    ap.add_argument("--sample", default="sample.json")
    ap.add_argument("--limit", type=int, default=30, help="بنودٌ من كلّ مجلّد")
    ap.add_argument("--window", type=float, default=3.6)
    ap.add_argument("--md", required=True)
    ap.add_argument("--json", required=True)
    a = ap.parse_args()
    items = {it["id"]: it for it in json.load(open(a.sample, encoding="utf-8"))["items"]}
    s, body, dt = call("POST", "/v1/device", json.dumps({"app_version": "probe", "platform": "ci-vad-ab"}).encode(),
                       {"content-type": "application/json"})
    if s != 200:
        raise SystemExit("⛔ تعذّر تسجيلُ جهاز: %s %r" % (s, body[:200]))
    tok = json.loads(body)["token"]
    auth = {"authorization": "Bearer " + tok, "content-type": "audio/wav"}
    rows = []
    sent_ms = 0
    try:
        for src in a.src:
            wavs = sorted(f for f in os.listdir(src) if f.endswith(".wav") and f[:-4] in items)[: a.limit]
            for k, f in enumerate(wavs):
                x, sr = sf.read(os.path.join(src, f), dtype="float32")
                n = int(a.window * SR); st_ = max(0, len(x) // 2 - n // 2)
                win = x[st_: st_ + n]
                payload = wav_bytes(win)
                row = {"id": f[:-4], "set": os.path.basename(src.rstrip("/")), "ref": items[f[:-4]]["refText"]}
                for name, hdr in (("novad", {}), ("vad", {"x-tasmi-vad": "1"})):
                    s, body, dt = call("POST", "/v1/tasmi/stream", payload, {**auth, **hdr})
                    txt = ""
                    if s == 200:
                        try:
                            txt = json.loads(body).get("text", "") or ""
                        except Exception:
                            txt = ""
                    row[name] = {"status": s, "sec": dt, "text": txt, "err": "" if s == 200 else body[:120].decode("utf-8", "replace")}
                    sent_ms += int(len(win) * 1000 / SR)
                    time.sleep(1.0)
                rows.append(row)
                if (k + 1) % 10 == 0 or k + 1 == len(wavs):
                    print("%s %d/%d" % (row["set"], k + 1, len(wavs)), flush=True)
    finally:
        s, _, _ = call("DELETE", "/v1/device", headers={"authorization": "Bearer " + tok})
        print("DELETE /v1/device →", s)

    summary = {}
    lines = ["## ☁️🎚️ `vad_filter` في البثّ السحابيّ — نافذةُ %.1fث من الوسط · %d بنداً · %.1f دقيقة صوتٍ أُرسلت" % (
        a.window, len(rows), sent_ms / 60000), "",
        "| المجموعة | الذراع | ن (200) | وسيطُ الزمن | p95 | oov | words/novad | فارغة | agree مع novad |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for set_ in sorted({r["set"] for r in rows}):
        rs = [r for r in rows if r["set"] == set_]
        for name in ("novad", "vad"):
            ok = [r for r in rs if r[name]["status"] == 200]
            secs = sorted(r[name]["sec"] for r in ok)
            oov = tot = nb = ae = an = empty = 0
            for r in ok:
                h = norm_words(r[name]["text"]); b = norm_words(r["novad"]["text"])
                ayah = set(norm_words(r["ref"]))
                oov += sum(1 for w in h if w not in ayah); tot += len(h); nb += len(b)
                ae += edits(h, b); an += max(1, len(b)); empty += (len(h) == 0)
            s = {"n_ok": len(ok), "n": len(rs), "med_s": st.median(secs) if secs else None,
                 "p95_s": secs[min(len(secs) - 1, int(0.95 * len(secs)))] if secs else None,
                 "oov": oov / max(1, tot), "words_ratio": tot / max(1, nb), "empty": empty, "agree": 1 - ae / an if an else None}
            summary[set_ + "/" + name] = s
            lines.append("| %s | %s | %d/%d | %s | %s | %.1f%% | %.2f | %d | %s |" % (
                set_, name, s["n_ok"], s["n"], "%.2fث" % s["med_s"] if s["med_s"] is not None else "—",
                "%.2fث" % s["p95_s"] if s["p95_s"] is not None else "—", 100 * s["oov"], s["words_ratio"], s["empty"],
                "%.1f%%" % (100 * s["agree"]) if s["agree"] is not None else "—"))
    errs = [(r["id"], n, r[n]["status"], r[n]["err"]) for r in rows for n in ("novad", "vad") if r[n]["status"] != 200]
    if errs:
        lines += ["", "⚠️ ردودٌ غيرُ 200: " + " · ".join("%s/%s=%s %s" % e for e in errs[:8]) + (" …" if len(errs) > 8 else "")]
    md = "\n".join(lines) + "\n"
    open(a.md, "w", encoding="utf-8").write(md)
    json.dump({"summary": summary, "rows": rows, "sent_ms": sent_ms}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(md)


if __name__ == "__main__":
    main()
