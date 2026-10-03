#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""☁️⚖️ **طولُ نافذة البثّ السحابيّ بالحاكم الزوجيّ** (‏المستشار · الجولة الرابعة 2026-10-03).

الجولةُ الثالثة حسمت أنّ نافذةَ 6ث أصحُّ نصّاً من 3.6ث (‏هلوسةٌ أقلّ وWER أدنى)، لكنّها قاست النصَّ لا **الحكم**:
هل يتغيّر الاتّهامُ الكاذبُ والكشفُ حين يُحكم بنصّ نوافذَ 6ث بدل 3.6ث؟ هذه الأداةُ تصنع فرضيّاتٍ بصيغة
`local_whisper.py` لكلّ بندٍ من مجموعتَي `g3r` (‏حقنُ ورشٍ وقالون في تلاوات قرّاءٍ منشورة — نظيفٌ ومضجَّج)،
فيقرؤها `v2_gate.py --pattern` بالمسطرة المعتمدة نفسِها (‏`RecitationScorer` · الاتّهام خارج نطاق الحقن ±1).

**النصُّ لكلّ بند:** يُسوّى الصوتُ (‏مرآةُ `AudioLevel.normalize` كما يفعل `TasmiCloudStream.transcribe`) ثمّ يُقطَّع
إلى نوافذَ متتاليةٍ طولُ كلٍّ منها ≤ W ثانية، والقطعُ عند **أهدأ نقطةٍ** في الثلث الأخير من النافذة (‏كـ`_windowed`
في `local_whisper.py`) كي لا تُشطر كلمةٌ ما أمكن؛ وبقيّةٌ أقصرُ من نصف ثانيةٍ تُضمّ إلى ما قبلها (‏التطبيقُ لا يرسل
مقطعاً < 0.5ث). كلُّ نافذةٍ نداءٌ إلى `/v1/tasmi/stream` بلا رأس VAD (‏المشحون)، والنصوصُ تُوصل بالترتيب.
⚠️ **حدُّ التمثيل:** الحلقةُ الحيّة ترسل نوافذَ متراكبة ويُتابعها `follower`، وهنا نوافذُ متجاورة بلا تراكب ⇒ الفرقُ
بين الذراعين يقيس **أثرَ طول النافذة على نصّ الحكم**، لا تجربةَ «سمّع معي» كاملة.

⛔ الصوتُ تلاواتُ قرّاءٍ منشورة من العيّنة لا صوتَ مستخدم؛ ومسارُ البثّ يمرّر ولا يخزّن. جهازٌ مؤقّتٌ يُسجَّل ثمّ
يُمحى، ويُبدَّل بجهازٍ مؤقّتٍ جديدٍ (‏ويُمحى القديم) إن نفدت حصّةُ الجهاز اليوميّة (‏90 دقيقة) — بلا أسرار.

    python cloud_gate_windows.py --set g3r:noisy --set g3r:clean --windows 3.6 6.0
    python v2_gate.py --score-only --pattern "work/hyps_{arm}_{tag}_gate_cap10.json" --arms cloud-w3.6 cloud-w6

🎛️ **الجولةُ الخامسة (‏2026-10-03): أذرعُ رأس الفكّ** — `--arm NAME=W[:DECODE]` (‏يُكرَّر) يرسل **كلَّ نافذةٍ إلى الأذرع كلِّها
متتاليةً** (‏النافذةُ نفسُها والدقيقةُ نفسُها ⇒ زوجٌ حقيقيّ) مع رأس `x-tasmi-decode: DECODE` إن وُجد، ورأسِ `x-tasmi-segments: 1`
(‏لا يغيّر النصّ؛ يحفظ ثقةَ المقاطع). ونصُّ كلِّ نافذةٍ يُحفظ في `parts` كي تُطبَّق مرشّحاتُ الجهاز (‏`stripEdges`) لكلّ نافذةٍ
كما يفعل `ReciteWithMeViewModel` — بلا نداءٍ إضافيّ (‏`cloud_decode5.py`).

    python cloud_gate_windows.py --set g3r:noisy --arm w6=6 --arm w6-guard=6:nocond,hst --arm w6-prompt=6:prompt
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cloud_vad_ab import call, wav_bytes  # noqa: E402
from local_whisper import SR, al_normalize, quietest_cut  # noqa: E402
import emu_sweep as E  # noqa: E402

MIN_CLIP = SR // 2


def tiles(n, w):
    """حدودُ النوافذ [(a, b)] لصوتٍ طوله n عيّنةً ونافذةٍ w عيّنةً — والقطعُ عند أهدأ نقطة."""
    out, start = [], 0
    while start < n:
        hard = min(start + w, n)
        if hard == n:
            end = n
        else:
            end = quietest_cut(AUDIO[0], start + w * 2 // 3, hard)
        if n - end < MIN_CLIP:
            end = n
        out.append((start, end))
        start = end
    return out


AUDIO = [None]


class Device:
    def __init__(self, tag):
        self.tag, self.tok, self.made = tag, None, 0
        self.new()

    def new(self):
        self.drop()
        s, body, _ = call("POST", "/v1/device", json.dumps({"app_version": "probe", "platform": self.tag}).encode(),
                          {"content-type": "application/json"})
        if s != 200:
            raise SystemExit("⛔ تعذّر تسجيلُ جهاز: %s %r" % (s, body[:200]))
        self.tok = json.loads(body)["token"]
        self.made += 1
        print(f"📱 جهازٌ مؤقّت #{self.made}", flush=True)

    def drop(self):
        if self.tok:
            s, _, _ = call("DELETE", "/v1/device", headers={"authorization": "Bearer " + self.tok})
            print("DELETE /v1/device →", s, flush=True)
            self.tok = None

    def stream(self, clip, sleep, extra=None):
        for attempt in range(6):
            h = {"authorization": "Bearer " + self.tok, "content-type": "audio/wav"}
            h.update(extra or {})
            s, body, dt = call("POST", "/v1/tasmi/stream", wav_bytes(clip), h)
            time.sleep(sleep)
            if s == 200:
                j = json.loads(body)
                self.last_segs = j.get("segments")
                return j.get("text", "") or "", dt, s
            err = ""
            try:
                err = json.loads(body).get("error", "")
            except Exception:  # noqa: BLE001
                pass
            if s == 429 and err == "quota":
                self.new()
                continue
            time.sleep(5 * (attempt + 1))
        return None, dt, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", action="append", required=True, help="g3r:noisy · g3r:clean (يُكرَّر)")
    ap.add_argument("--windows", type=float, nargs="+", default=[3.6, 6.0])
    ap.add_argument("--arm", action="append", default=[],
                    help="NAME=W[:DECODE] — ذراعٌ باسمٍ ونافذةٍ ورأسِ فكٍّ اختياريّ (‏يُكرَّر · يُبطل --windows)")
    ap.add_argument("--limit", type=int, default=0, help="بنودٌ من كلّ مجموعة (0 = كلّها)")
    ap.add_argument("--sleep", type=float, default=0.7, help="فاصلٌ بين النداءات (‏حدُّ الدقيقة 90)")
    a = ap.parse_args()
    # الأذرع: (الاسم، النافذة، رأسُ الفكّ). بلا --arm ⇒ أذرعُ الجولة الرابعة كما هي (‏cloud-w3.6 · cloud-w6 بلا رؤوس).
    arms = []
    for spec in a.arm:
        name, rest = spec.split("=", 1)
        w, _, dec = rest.partition(":")
        arms.append((name, float(w), dec.strip()))
    if not arms:
        arms = [(f"w{w:g}", w, "") for w in a.windows]
    dev = Device("ci-window-gate")
    sent_ms, calls, bad = 0, 0, 0
    try:
        for set_name in a.set:
            d = E.local_dir(set_name)
            ids = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".wav"))
            if a.limit:
                ids = ids[: a.limit]
            outs = {name: {} for name, _, _ in arms}
            for k, i in enumerate(ids):
                x, sr = sf.read(os.path.join(d, i + ".wav"), dtype="float32")
                if sr != SR:
                    raise SystemExit(f"⛔ {i}: معدّلُ العيّنة {sr}")
                if x.ndim > 1:
                    x = x.mean(axis=1)
                x = al_normalize(np.asarray(x, dtype=np.float32))
                AUDIO[0] = x
                acc = {name: {"parts": [], "segs": [], "ms": 0, "bad": 0, "n": 0} for name, _, _ in arms}
                span_by_w = {w: tiles(len(x), int(w * SR)) for w in {w for _, w, _ in arms}}
                # النافذةُ الواحدةُ تُرسَل إلى كلّ الأذرع ذاتِ الطول نفسِه متتاليةً (‏زوجٌ في الدقيقة نفسِها)
                for w, spans in span_by_w.items():
                    for (s0, s1) in spans:
                        for name, aw, dec in arms:
                            if aw != w:
                                continue
                            extra = {"x-tasmi-segments": "1"} if a.arm else {}
                            if dec:
                                extra["x-tasmi-decode"] = dec
                            dev.last_segs = None
                            txt, dt, st = dev.stream(x[s0:s1], a.sleep, extra)
                            calls += 1
                            sent_ms += (s1 - s0) * 1000 // SR
                            c = acc[name]
                            c["ms"] += int(dt * 1000); c["n"] += 1
                            if txt is None:
                                c["bad"] += 1
                                bad += 1
                                c["parts"].append(None)
                            else:
                                c["parts"].append(" ".join(txt.split()))
                            c["segs"].append(dev.last_segs)
                for name, aw, dec in arms:
                    c = acc[name]
                    h = {"text": " ".join(p for p in c["parts"] if p), "ms": c["ms"], "audioMs": len(x) * 1000 // SR,
                         "windows": c["n"]}
                    if a.arm:
                        h["parts"], h["segs"] = c["parts"], c["segs"]
                    if c["bad"]:
                        h["error"] = f"{c['bad']} نداءٌ فشل"
                    outs[name][i] = h
                if (k + 1) % 20 == 0:
                    print(f"  {set_name}: {k+1}/{len(ids)} · نداءات {calls} · صوت {sent_ms/60000:.1f} د · إخفاق {bad}", flush=True)
            for name, aw, dec in arms:
                hyps = outs[name]
                p = os.path.join(HERE, "work", f"hyps_cloud-{name}_{E.tag_of(set_name)}_gate_cap10.json")
                json.dump({"model": "cloud:/v1/tasmi/stream (large-v3-turbo)", "window_s": aw, "decode": dec,
                           "note": "نوافذُ متجاورةٌ ≤ W بقطعٍ عند أهدأ نقطة · AudioLevel.normalize · بلا VAD",
                           "hyps": hyps}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(f"💾 {os.path.basename(p)}: {len(hyps)} بنداً", flush=True)
    finally:
        dev.drop()
    print(f"✅ نداءات {calls} · صوت {sent_ms/60000:.1f} دقيقة · إخفاق {bad} · أجهزةٌ مؤقّتة {dev.made}")
    if bad > 0.02 * max(calls, 1):
        raise SystemExit("⛔ إخفاقاتٌ فوق 2٪ — النتيجةُ لا تُقرأ")


if __name__ == "__main__":
    main()
