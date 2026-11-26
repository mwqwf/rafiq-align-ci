#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""شاهدٌ زمنيٌّ بالاصطلاح الصوتيّ نفسِه لخرائط CTC السماعيّة (‏م1 · 2026-11-25): MMS_FA ∧ QWA على ملفّ سورةٍ واحد.

    python tools/index_qa/timing_witness.py --url <mp3> --surah 39 --riwaya hafs --out out

يكتب `out/timing_s039.json`: بصمةُ الصوت المنزَّل وفي كلّ آيةٍ كوفيّةٍ بدءُ كلمتها الأولى عند محاذيَين مستقلَّين:
  • `mms`  — محاذاةٌ قسريّةٌ (‏torchaudio MMS_FA، uroman) لنصّ السورة كلِّه من `text_<الرواية>.jz` في المستودع؛
  • `qwa`  — quran-word-align (‏Conformer-CTC قرآنيّ، MIT) يجد الآيات في التسجيل نفسِه بمصحف الرواية.
⛔ ليس شاهدَ سماع: هويّةُ النصّ يشهد بها Whisper وحده في `pin_heard`؛ وهذا يحلّ محلَّ طابعِ Whisper الزمنيّ فقط حين
   يتّفق المحاذيان ضمن TW_CONS_MS، ثمّ يُقارَن بـCTC بالعتبة W_AGREE_MS نفسِها. لا يُكتب منه شيءٌ في فهرس.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SR = 16000
QWA_RIWAYAT = ("hafs", "warsh", "qalun")
_HARAKAT = re.compile("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640\u08D3-\u08FF]")


def first_norm(word):
    """تطبيعُ الكلمة الأولى للمطابقة بين نصّ المستودع ومصحف QWA (‏حروفٌ عاريةٌ بلا همزاتٍ ولا تشكيل)."""
    w = _HARAKAT.sub("", word or "")
    w = re.sub("[أإآٱ]", "ا", w).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub("[^\u0621-\u064A]", "", w).replace("ء", "")


def kufi_from_qwa(seq, firsts, mms, near_ms=3000):
    """لكلّ آيةٍ كوفيّةٍ لها بدءُ MMS: أقربُ كلمةٍ في تسلسل QWA [(كلمةٌ مطبَّعة، بدء، ثقة)] تطابق كلمتَها الأولى
    ضمن near_ms — فترقيمُ مصحف QWA (‏المدنيّ في ورش وقالون) لا يُفترض مطابقاً للكوفيّ. يُرجع {آية: (بدء، ثقة)}."""
    out = {}
    for a, m in mms.items():
        fw = firsts.get(a)
        c = [x for x in seq if fw and x[0] == fw and abs(x[1] - m) < near_ms]
        if c:
            b = min(c, key=lambda x: abs(x[1] - m))
            out[a] = (int(b[1]), float(b[2]))
    return out


def mms_starts(wav_path, ayat_text, with_basmala_text=None):
    """بدءُ الكلمة الأولى لكلّ آيةٍ ودرجتُها بمحاذاة MMS_FA القسريّة على السورة كلّها (‏نوافذ 30ث بتداخل 2ث)."""
    import numpy as np                                                   # noqa: PLC0415
    import torch                                                         # noqa: PLC0415
    import torchaudio                                                    # noqa: PLC0415
    import uroman                                                        # noqa: PLC0415
    import wave                                                          # noqa: PLC0415
    from torchaudio.pipelines import MMS_FA as B                         # noqa: PLC0415
    with wave.open(wav_path, "rb") as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    wav = torch.from_numpy(pcm).unsqueeze(0)
    model, D, U = B.get_model(with_star=False).eval(), B.get_dict(), uroman.Uroman()

    def rom(t):
        t = _HARAKAT.sub("", t).replace("ٱ", "ا")
        return [x for x in ("".join(c for c in y if c in D) for y in U.romanize_string(t).lower().split()) if x]
    CH, OV, ems = 30 * SR, 2 * SR, []
    with torch.inference_mode():
        i = 0
        while i < wav.shape[1]:
            seg = wav[:, max(0, i - OV):i + CH + OV]
            e = torch.log_softmax(model(seg)[0], -1)[0]
            fr = e.shape[0] / seg.shape[1]
            lo, n = int(round((i - max(0, i - OV)) * fr)), int(round(min(CH, wav.shape[1] - i) * fr))
            ems.append(e[lo:lo + n])
            i += CH
    em = torch.cat(ems)
    words, own = [], []
    if with_basmala_text:
        for x in rom(with_basmala_text):
            words.append(x); own.append(0)
    for k, t in enumerate(ayat_text, 1):
        for x in rom(t):
            words.append(x); own.append(k)
    tok = [D[c] for x in words for c in x]
    ali, sc = torchaudio.functional.forced_align(em.unsqueeze(0), torch.tensor([tok], dtype=torch.int32), blank=0)
    spans = torchaudio.functional.merge_tokens(ali[0], sc[0].exp())
    ms_per_frame = wav.shape[1] / em.shape[0] / 16
    idx, starts, scores = 0, {}, {}
    for x, k in zip(words, own):
        sp = spans[idx:idx + len(x)]
        idx += len(x)
        if k and k not in starts:
            starts[k] = int(round(sp[0].start * ms_per_frame))
            scores[k] = round(float(np.mean([s.score for s in sp])), 4)
    return starts, scores


def qwa_sequence(mp3, surah, riwaya, first_out=None):
    """تسلسلُ كلمات QWA [(كلمةٌ مطبَّعة، بدء، ثقة)] بالترتيب المسموع (‏الكلمةُ المعادةُ تُعدّ مرّةً أخرى)."""
    from quran_word_align import align as Q                              # noqa: PLC0415
    import quran_word_align                                              # noqa: PLC0415
    res = Q.align_recording(surah, Path(mp3), Q.mushaf_words(riwaya), Q.Model())
    W = json.load(open(Path(quran_word_align.__file__).parent / "data" / f"{riwaya}-words.json", encoding="utf-8"))
    seq = []
    for a, ws in res.items():
        if first_out is not None and ws:
            first_out[int(a)] = int(ws[0][1])
        txt = dict((i, t) for i, t in W.get(f"{surah}:{int(a)}", []))
        for wi, st, _en, cf in ws:
            seq.append((first_norm(txt.get(wi, "")), int(st), float(cf)))
    return sorted(seq, key=lambda x: x[1])


def pause_around(wav_path, t_ms, back=1500, fwd=400, thr=18, minrun=8):
    """م3: أقربُ سكتةٍ (‏≥minrun×10م.ث تحت p90−thr د.ب) تنتهي في [t−back, t+fwd] ⇒ [بدء، نهاية] بالم.ث أو None.
    هي نفسُ `pause_bounds` في ظلّ م3 (‏shadow2/build.py) حرفاً."""
    import wave                                                          # noqa: PLC0415
    import numpy as np                                                   # noqa: PLC0415
    with wave.open(wav_path, "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
    db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(160) / 160, "same")[::160]) + 1e-9)
    i0, i1 = max(0, int(t_ms - back) // 10), min(len(db), int(t_ms + fwd) // 10)
    if i1 <= i0:
        return None
    ref = np.percentile(db[max(0, i0 - 300):i1 + 300], 90)
    q = db[i0:i1] < ref - thr
    best, j = None, 0
    while j < len(q):
        if q[j]:
            k = j
            while k < len(q) and q[k]:
                k += 1
            if k - j >= minrun:
                s, e = (i0 + j) * 10, (i0 + k) * 10
                if best is None or abs(e - t_ms) < abs(best[1] - t_ms):
                    best = (s, e)
            j = k
        else:
            j += 1
    return list(best) if best else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    if a.riwaya not in QWA_RIWAYAT:
        raise SystemExit(f"⛔ QWA لا يحمل مصحف {a.riwaya} — لا شاهدَ زمنيّاً بمحاذٍ واحد")
    sys.path.insert(0, str(ROOT / "tools" / "alignment"))
    from common import fetch_retry, load_index, load_text, surah_slice, to_wav16k   # noqa: PLC0415
    os.makedirs(a.out, exist_ok=True)
    mp3 = os.path.join(a.out, f"{a.surah:03d}.mp3")
    fetch_retry(a.url, mp3)
    sha = hashlib.sha256(open(mp3, "rb").read()).hexdigest()
    wav = to_wav16k(mp3, os.path.join(tempfile.mkdtemp(), "a.wav"))
    start, end, _info = surah_slice(load_index(), a.surah)
    text = load_text(a.riwaya)
    ayat = text[start:end]
    bas = text[0] if a.surah not in (1, 9) else None
    mms, score = mms_starts(wav, ayat, bas)
    firsts = {k: first_norm(t.split()[0]) for k, t in enumerate(ayat, 1)}
    qfirst = {}
    qwa = kufi_from_qwa(qwa_sequence(mp3, a.surah, a.riwaya, first_out=qfirst), firsts, mms)
    res = {"surah": a.surah, "riwaya": a.riwaya, "fileRef": a.url, "sha256": sha, "tool": "mms_fa+qwa",
           "ayahs": {str(k): {"mms": mms[k], "mmsScore": score[k],
                              "qwa": qwa.get(k, (None, None))[0], "qwaConf": qwa.get(k, (None, None))[1],
                              "pause": (pause_around(wav, qwa[k][0]) if k in qwa and k <= 3 else None),
                              # م3أ: الآية 1 (الحروف): أقربُ سكتةٍ إلى بدء MMS وأوّلُ كلمةٍ لها عند QWA
                              "pauseMms": (pause_around(wav, mms[k]) if k == 1 else None),
                              "qwaFirst": (qfirst.get(k) if k == 1 else None)}
                     for k in sorted(mms)}}
    out = os.path.join(a.out, f"timing_s{a.surah:03d}.json")
    with open(out + ".part", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    os.replace(out + ".part", out)
    os.remove(mp3)
    both = sum(1 for v in res["ayahs"].values() if v["qwa"] is not None)
    print(f"كُتب: {out} · آيات {len(mms)} · بقياسَين {both} · بصمة الصوت {sha[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
