#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎚️ **المعالجةُ الصوتيّة قبل النموذج على المتعلّمين الحقيقيّين** — قياسٌ فقط، لا يُشحن.

السؤال: أيُّ معالجةٍ قبل النموذج (‏بوّابةُ الضجيج · AudioLevelV2 · مرشّحُ تمريرٍ عالٍ · بوّابةٌ ألطف ·
حشوُ صمتٍ حول المجموعة) ترفع الأداءَ في الضجيج والخفوت **ولا تخفضه نظيفاً**، على صوت متعلّمين
وسمهم إنسان (‏sobolev · MIT) لا على قرّاءٍ محترفين؟

المرآة: `local_whisper.py` و`denoise.py` و`frontend.py` منسوخةٌ حرفاً من `QuranRafiq@main`
(‏`_transcribe_engine_old` = ترتيبُ `LongAudioTranscriber` المشحون: تسويةٌ ⇒ تقطيع ⇒ بصمةٌ ⇒ بوّابةٌ لكلّ مجموعة ·
`_transcribe_v2post` = المسارُ نفسُه و`AudioLevelV2.enabled=true`). والاستدلالُ بـwhisper-cli والنموذجِ المشحون بالبصمة.

الأذرع:
- `off`   : تسويةُ الذروة + تقطيع، بلا بوّابة (‏طريقةُ التفريغات المخزّنة في ملفّ الذهب D-734/D-735).
- `ship`  : المشحونُ اليوم (‏NoiseGate.enabled=true · AudioLevelV2 مطفأة).
- `v2`    : المشحون + AudioLevelV2.enabled=true.
- `hpf`   : مرشّحُ تمريرٍ عالٍ (‏بترورث رتبة 2 · 100 هز · صفريُّ الطور) على الخام ثمّ `ship`.
- `mild`  : `ship` ببوّابةٍ ألطف (‏over 1.3 · أرضيةٌ −10 د.ب بدل 1.6 و−14).
- `pad`   : `ship` مع 250 م.ث صمتاً قبل كلّ مجموعةٍ وبعدها قبل النموذج.

الظروف (‏حتميّةٌ بالبذرة لكلّ مفتاح): `clean` كما سُجّل · `fan10`/`fan5` ضجيجٌ ورديٌّ بنسبة 10/5 د.ب على كلام
التسجيل (‏مرآةُ `augment.mix_at_snr`) · `quiet30` خفضُ 30 د.ب.

    python tools/audiofe/run_fe.py --model tiny --model-path model.bin --cli bin/whisper-cli \
        --audio work/learner_audio --cond clean fan10 --arms off ship v2 --out work/fe_tiny.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import denoise as dn          # noqa: E402
import frontend as fe         # noqa: E402
import local_whisper as lw    # noqa: E402

SR = 16_000
LANG = {"tiny": "en", "tiny_v2": "en", "base_q5_1": "ar"}   # مرآةُ WhisperDecode.SERVING (كما forced_judge.MODELS)
ARMS = ["off", "ship", "v2", "hpf", "mild", "pad"]
CONDS = ["clean", "fan10", "fan5", "quiet30"]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def read_audio(path: str) -> np.ndarray:
    ff = os.environ.get("FFMPEG", "ffmpeg")
    r = subprocess.run([ff, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype="<f4").astype(np.float32)


# ───── مرآةُ augment.py (‏speech_mask · pink_noise · mix_at_snr) حرفاً ─────
def speech_mask(x, frame=320, rel_db=35.0):
    n = len(x) // frame
    if n == 0:
        return np.ones(len(x), dtype=bool)
    f = x[: n * frame].reshape(n, frame)
    e = np.sqrt((f.astype(np.float64) ** 2).mean(axis=1) + 1e-12)
    thr = e.max() * (10 ** (-rel_db / 20))
    m = np.repeat(e >= thr, frame)
    if len(m) < len(x):
        m = np.concatenate([m, np.zeros(len(x) - len(m), dtype=bool)])
    return m if m.any() else np.ones(len(x), dtype=bool)


def pink_noise(n, rng):
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    scale = np.ones_like(freqs)
    scale[1:] = 1.0 / np.sqrt(freqs[1:])
    spec *= scale
    out = np.fft.irfft(spec, n)
    peak = np.abs(out).max()
    return (out / peak).astype(np.float32) if peak > 0 else out.astype(np.float32)


def mix_at_snr(clean, noise, snr_db):
    m = speech_mask(clean)
    ps = float((clean[m].astype(np.float64) ** 2).mean() + 1e-20)
    pn = float((noise[m].astype(np.float64) ** 2).mean() + 1e-20)
    gain = np.sqrt(ps / (pn * (10 ** (snr_db / 10))))
    return (clean + noise * gain).astype(np.float32)


def rng_for(key: str, cond: str):
    h = hashlib.sha256(f"1446:{key}:{cond}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def condition(x: np.ndarray, key: str, cond: str) -> np.ndarray:
    if cond == "clean":
        return x
    if cond.startswith("fan"):
        return mix_at_snr(x, pink_noise(len(x), rng_for(key, cond)), float(cond[3:]))
    if cond.startswith("quiet"):
        return (x * 10 ** (-float(cond[5:]) / 20)).astype(np.float32)
    raise SystemExit("ظرفٌ غير معروف: " + cond)


def hpf(x: np.ndarray, fc: float = 100.0, order: int = 2) -> np.ndarray:
    """تمريرٌ عالٍ بمقدار بترورث |H|=1/√(1+(fc/f)^(2n)) في المجال الترددي (‏صفريُّ الطور)."""
    n = len(x)
    if n < 64:
        return x
    spec = np.fft.rfft(x.astype(np.float64))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    h = np.zeros_like(f)
    h[1:] = 1.0 / np.sqrt(1.0 + (fc / f[1:]) ** (2 * order))
    return np.fft.irfft(spec * h, n).astype(np.float32)


def level_info(x: np.ndarray) -> dict:
    sl = fe.speech_level(x)
    nf = fe.noise_floor(x)
    return {"dur": round(len(x) / SR, 2), "speech_db": round(fe._db(sl), 1), "noise_db": round(fe._db(nf), 1)}


class Arms:
    def __init__(self, tr):
        self.tr = tr
        self._orig_denoise = dn.denoise
        self._orig_pick = tr._pick

    def run(self, arm: str, x: np.ndarray) -> str:
        tr = self.tr
        dn.denoise = self._orig_denoise
        tr._pick = self._orig_pick
        try:
            if arm == "off":
                tr.gate, tr.frontend = False, "old"
                out = tr.transcribe(x)
            elif arm == "ship":
                tr.gate = True
                out = tr._transcribe_engine_old(x, None, 0.0, None, 0.0, 5)
            elif arm == "v2":
                tr.gate = True
                out = tr._transcribe_v2post(x, None, 0.0, None, 0.0, 5)
            elif arm == "hpf":
                tr.gate = True
                out = tr._transcribe_engine_old(hpf(x), None, 0.0, None, 0.0, 5)
            elif arm == "mild":
                tr.gate = True
                od = self._orig_denoise
                dn.denoise = lambda seg, **kw: od(seg, over=1.3, floor_db=-10.0, **kw)
                out = tr._transcribe_engine_old(x, None, 0.0, None, 0.0, 5)
            elif arm == "pad":
                tr.gate = True
                op = self._orig_pick
                z = np.zeros(SR // 4, dtype=np.float32)
                tr._pick = lambda seg, *a: op(np.concatenate([z, np.asarray(seg, np.float32), z]), *a)
                out = tr._transcribe_engine_old(x, None, 0.0, None, 0.0, 5)
            else:
                raise SystemExit("ذراعٌ غير معروفة: " + arm)
        finally:
            dn.denoise = self._orig_denoise
            tr._pick = self._orig_pick
        return out[0] if isinstance(out, tuple) else out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=sorted(LANG))
    ap.add_argument("--model-path", required=True)
    ap.add_argument("--cli", required=True)
    ap.add_argument("--audio", required=True, help="مجلّدٌ فيه manifest.json (مخرَجُ forced_judge.py fetch)")
    ap.add_argument("--cond", nargs="+", default=CONDS, choices=CONDS)
    ap.add_argument("--arms", nargs="+", default=ARMS, choices=ARMS)
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    man = json.load(open(os.path.join(a.audio, "manifest.json"), encoding="utf-8"))["items"]
    keys = sorted(man)
    if a.limit:
        keys = keys[:a.limit]
    tr = lw.Transcriber(a.model_path, backend="cli", cli=a.cli, lang=LANG[a.model], threads=a.threads)
    arms = Arms(tr)
    res = {"model": a.model, "lang": LANG[a.model], "arms": a.arms, "conds": a.cond,
           "mirror": {f: hashlib.sha256(open(os.path.join(HERE, f + ".py"), "rb").read()).hexdigest()[:12]
                      for f in ("local_whisper", "denoise", "frontend")},
           "hyps": {}, "levels": {}, "seconds": {}, "errors": {}}
    raws = {k: read_audio(os.path.join(a.audio, man[k])) for k in keys}
    for cond in a.cond:
        for arm in a.arms:
            name = f"{a.model}.{cond}.{arm}"
            res["hyps"][name] = {}
            t0 = time.time()
            for n, k in enumerate(keys, 1):
                x = condition(raws[k], k, cond)
                if arm == a.arms[0]:
                    res["levels"].setdefault(cond, {})[k] = level_info(x)
                try:
                    res["hyps"][name][k] = " ".join(arms.run(arm, x).split())
                except Exception as e:  # noqa: BLE001 — يُسجَّل ولا يُبتلع: الصفُّ يسقط بـmissing_witness
                    res["errors"].setdefault(name, {})[k] = str(e)[:200]
            res["seconds"][name] = round(time.time() - t0, 1)
            print(f"✅ {name}: {len(keys)} مقطعاً · {res['seconds'][name]}ث · أخطاء {len(res['errors'].get(name, {}))}",
                  flush=True)
            json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
