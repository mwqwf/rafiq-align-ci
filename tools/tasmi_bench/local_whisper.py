# -*- coding: utf-8 -*-
"""🖥️ **المستنسِخ المحلي — مرآةُ المحرك على معالج جهاز المالك** (خارطة الطريق M0-3).

لماذا وُجد: قياس G1+G2 يحتاج آلاف التفريغات، وخادم الأسطول مغلق وكولاب متقطّع، ولا مترجم C
على الجهاز فلا `whisper-cli`. فهذا يشغّل **الأوزان نفسها** عبر `transformers` على المعالج،
ويحاكي `LongAudioTranscriber` خطوةً بخطوة (تسوية المستوى · التقطيع عند السكتات · نوافذ 25ث
بقطعٍ عند أهدأ نقطة) — ومخرجُه بصيغة `remote_whisper.py` نفسها فيقرؤه `score.py` بلا تغيير.

⚠️ **وهو مرآةٌ لا حَكَم:** الحقيقة هي المحرك على الجهاز. لذلك `--parity` يقارن نصوصَه حرفياً
بمخرج مسبار `whisperBatch` من المحاكي؛ فإن هبط التطابق دون العتبة فالمرآة كاذبة ولا يُبنى
على أرقامها شيء (درس REPORT.md §١: أول تشغيلٍ لم يحاكِ النوافذ فأعطى 79.3٪ بدل 91.4٪).

    python tools/tasmi_bench/local_whisper.py --set g1 --model shipped
    python tools/tasmi_bench/local_whisper.py --set g2:gain-30 --model tuned-v1
    python tools/tasmi_bench/local_whisper.py --parity work/emu_batch.txt --hyps work/hyps_shipped_g1.json
"""
import argparse
import json
import os
import re
import sys
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(HERE, "work")
WAV = os.path.join(WORK, "wav")
G2 = os.path.join(WORK, "g2")
SR = 16_000

MODELS = {
    # ⬇️ نسخةٌ محلية (‏HF نزّلها مرةً واحدة) — لا نداءَ شبكةٍ في كل تشغيل
    "shipped": os.path.join(ROOT, "tools", "finetune", "work", "shipped"),
    # 🧱 النموذجُ المكمَّم q8 — **ما يحمله التطبيق بعينه**، لمسار `--backend cli` (بلا HF ولا شبكة).
    "q8": os.path.join(WORK, "ggml-q8.bin"),
    # 🧱 **النموذجُ الأكبرُ مكمَّماً** — `whisper-base-ar-quran` q8 (‏81.8 م.ب مقابل 43.5 للصغير).
    # ⛔ **لم يُقَس قطُّ في هذه اللوحة** رغم وجوده على R2 منذ 09-02: ستُّ وصفاتِ ضبطٍ على النموذج
    # **الصغير** سقطت، ولم يُجرَّب **تكبيرُ النموذج** — وهو البابُ الوحيدُ الباقي بعد D-347.
    "base-q8": os.path.join(WORK, "ggml-base-ar-quran-q8_0.bin"),
    "base": "tarteel-ai/whisper-base-ar-quran",
    "tuned-v1": os.path.join(ROOT, "tools", "finetune", "work", "best"),
}

# مرآة LongAudioTranscriber
WINDOW_SECONDS = 25
MIN_SILENCE_MS = 350
MIN_UTTERANCE_MS = 400
MAX_GAP_SECONDS = 2


# ───────────────────── مرآة AudioLevel (Kotlin) ─────────────────────

def al_peak(x):
    return float(np.abs(x).max()) if len(x) else 0.0


def al_rms(x):
    return float(np.sqrt((x.astype(np.float64) ** 2).mean())) if len(x) else 0.0


def al_normalize(x, target_peak=0.9, max_gain=30.0):
    """مرآةُ `AudioLevel.normalize`: كسبٌ إلى ذروةٍ قياسية بحدٍّ أقصى، ويُترك القياسيُّ أصلاً."""
    p = al_peak(x)
    if p <= 1e-4 or p >= 0.5:
        return x
    g = min(max_gain, target_peak / p)
    return np.clip(x * g, -1.0, 1.0).astype(np.float32)


def al_speech_floor(x, frame=320):
    """مرآةُ `AudioLevel.speechFloor`: عُشرُ المئين 85 من طاقة الإطارات، محصورةً [0.004, 0.02]."""
    n = len(x) // frame
    if n == 0:
        return 0.01
    e = np.sqrt((x[: n * frame].reshape(n, frame).astype(np.float64) ** 2).mean(axis=1))
    e.sort()
    speech = e[min(max(int(n * 0.85), 0), n - 1)]
    return float(min(max(speech * 0.1, 0.004), 0.02))


# ─────────────── مرآة LongAudioTranscriber (تقطيع ونوافذ) ───────────────

def split_at_silences(x, threshold, min_silence_ms=MIN_SILENCE_MS, min_utt_ms=MIN_UTTERANCE_MS):
    frame = SR // 50                      # 20 م.ث
    n = len(x) // frame
    if n == 0:
        return [(0, len(x))]
    e = np.sqrt((x[: n * frame].reshape(n, frame).astype(np.float64) ** 2).mean(axis=1))
    quiet = e < threshold
    min_sil = min_silence_ms // 20
    out, start, sil_run = [], -1, 0
    for i in range(n):
        if quiet[i]:
            sil_run += 1
            if start >= 0 and sil_run >= min_sil:
                out.append((start * frame, (i - sil_run + 1) * frame))
                start = -1
        else:
            if start < 0:
                start = i
            sil_run = 0
    if start >= 0:
        out.append((start * frame, len(x)))
    min_utt = min_utt_ms * SR // 1000
    kept = [(a, b) for a, b in out if b - a >= min_utt]
    return kept or [(0, len(x))]


def group_utterances(utts, max_samples, max_gap):
    """مرآةُ `LongAudioTranscriber.groupUtterances` (‏D-250): نطقاتٌ متتالية تُجمَّع ما لم تتجاوز
    [max_samples] ولم تضمّ سكتةً ≥ [max_gap]."""
    out, start, end = [], -1, -1
    for a, b in utts:
        if start < 0:
            start, end = a, b
            continue
        if (a - end) < max_gap and (b - start) <= max_samples:
            end = b
        else:
            out.append((start, end)); start, end = a, b
    if start >= 0:
        out.append((start, end))
    return out


def quietest_cut(x, frm, to):
    frame = SR // 10
    best, best_e, i = to - frame, None, frm
    while i + frame <= to:
        e = float((x[i:i + frame].astype(np.float64) ** 2).sum())
        if best_e is None or e < best_e:
            best_e, best = e, i
        i += frame // 2
    return min(best + frame // 2, to)


class Transcriber:
    """يحمّل النموذج مرةً ويفرّغ كما يفرّغ المحرك.

    [frontend]: `old` = مرآةُ `AudioLevel` المشحونة · `new` = الواجهة الأمامية v2
    (`frontend.py`) — المفتاحُ واحدٌ كي تكون المقارنةُ أ/ب على المسار نفسه بلا فرقٍ آخر.
    """

    def __init__(self, model_path, device="cpu", frontend="old", threads=4, gate=False,
                 group_cap=WINDOW_SECONDS * SR, backend="hf", cli=None, lang="en", floor_rule="v2"):
        self.backend, self.cli, self.model_path, self.threads, self.lang = backend, cli, model_path, threads, lang
        self.device = device
        self.frontend = frontend
        self.gate = gate
        self.group_cap = group_cap
        # 🔪 D-345: قاعدةُ عتبة السكوت — `v2` هامشٌ ثابتٌ +6 د.ب (المشحون) · `prop` نسبةٌ من المدى.
        self.floor_rule = floor_rule
        if backend == "cli":
            # 🧱 **مرآةُ المحرك على CI (‏2026-09-11):** الواجهةُ الأمامية نفسُها (بوّابة · تقطيع · سقف) بايثونياً،
            # والاستدلالُ بـ`whisper-cli` من whisper.cpp بالنموذج q8 **نفسِه** الذي يحمله التطبيق — أقربُ ما يكون
            # إلى المحاكي بلا جهاز المالك (يبقى فرقُ JNI/أندرويد وحدَه). الأعلامُ مرآةُ المحرك: greedy بلا طوابع.
            if not cli or not os.path.exists(cli):
                raise SystemExit(f"⛔ لا whisper-cli في {cli!r} — مرّر --cli أو WHISPER_CLI")
            # ⛔ **درسُ 2026-09-12:** عَلَمٌ لا تعرفه النسخةُ المثبَّتة يجعل CLI يطبع «usage» **ويخرج بصفر**،
            # فيُسجَّل نصٌّ فارغٌ لـ202 بند في عشر ثوانٍ ويُقرأ «0.00٪» **كأنه نتيجة**. فالأعلامُ تُستنبَط لا تُفترض.
            import subprocess as _sp
            h = _sp.run([cli, "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            help_txt = (h.stdout or "") + (h.stderr or "")
            self.cli_flags = [f for f in ("-nc",) if f in help_txt]
            print(f"🧱 whisper-cli: أعلامٌ إضافيّةٌ مدعومة {self.cli_flags or 'لا شيء'}", flush=True)
            self.gen_kwargs = {}
            return
        import torch
        torch.set_num_threads(threads)      # نتركُ نوىً للمحاكي (المسحُ يجري بالتوازي)
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        self.torch = torch
        self.proc = WhisperProcessor.from_pretrained(model_path)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_path).to(device).eval()
        # مرآةُ إعدادات المحرك: greedy (‏-bo 1 -bs 1)، عربية، بلا سياقٍ سابق.
        # ⚠️ **ولا يُمرَّر رمزُ لغةٍ إطلاقاً**، لسببين مقيسين:
        # ١. `generation_config` لهذا النموذج (‏2022) قديمٌ بلا خرائط رموز اللغات، فتمريرُ
        #    `language=` يرمي «The generation config is outdated…»، و`forced_decoder_ids`
        #    أسقطه transformers 5. أيُّ التفافٍ حولهما يجعل المرآةَ تفعل شيئاً غير ما يفعله المحرك.
        # ٢. **ولا حاجة**: المحرك نفسُه يعلن `params.language = "en"` (بقيّةٌ من عيّنة whisper.cpp)،
        #    وقياسُ REPORT.md §٤ على العيّنة كاملة: ar ‏79.31٪ مقابل en ‏79.60٪ — فرقٌ داخل مجال
        #    الثقة. فالنموذجُ مضبوطٌ على العربية ورمزُ اللغة لا يغيّر مساره.
        self.gen_kwargs = {}

    def nbest(self, audio, k=5):
        """يعيد [(نصّ، لوغاريتمُ الاحتمال المطبَّع)] لأفضل [k] مرشّحين ببحث الشعاع."""
        if len(audio) < SR // 20:
            return [("", 0.0)]
        feats = self.proc(audio, sampling_rate=SR, return_tensors="pt").input_features.to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(feats, num_beams=k, num_return_sequences=k,
                                      do_sample=False, max_new_tokens=200,
                                      output_scores=True, return_dict_in_generate=True,
                                      **self.gen_kwargs)
        texts = [re.sub(r"<\|[^|]*\|>", " ", t).strip()
                 for t in self.proc.batch_decode(out.sequences, skip_special_tokens=True)]
        scores = out.sequences_scores.tolist() if hasattr(out, "sequences_scores") else [0.0] * len(texts)
        return list(zip(texts, scores))

    def bias_for(self, ref_text):
        """🎯 **فكُّ تشفيرٍ مقيَّدٌ بالنصّ المتوقَّع — قيدٌ ناعم** (خارطة الطريق M1-4).

        في المدى المعلوم (حفظي · صفحة · اختبار مرحلة) نعرف الآياتِ المنتظرة، فنرجّح رموزَها
        في كل خطوةِ فكّ. والقيدُ **ناعمٌ عمداً** (إضافةُ لوغاريتم لا منعُ ما سواه):

        ⛔ القيدُ الصارم (‏`prefix_allowed_tokens_fn`) يمنع النموذج من كتابة ما لم يُنتظَر،
        فيصير التفريغُ نسخةً من المرجع مهما قرأ المستخدم — أي **يُخفي الخطأ الذي وُجدنا لكشفه**.
        فالمقياسُ الحاكم هنا ليس التتبّع وحده بل **الكشفُ على العيّنة المحقونة** معه.
        """
        if not ref_text:
            return None
        ids = set()
        for w in ref_text.split():
            for form in (w, " " + w):
                ids.update(self.proc.tokenizer.encode(form, add_special_tokens=False))
        return ids

    def _raw(self, audio, bias_ids=None, bias=0.0):
        if len(audio) < SR // 20:
            return ""
        if self.backend == "cli":
            if bias_ids and bias:
                raise SystemExit("⛔ الترجيحُ (--bias) غيرُ متاحٍ في مسار whisper-cli")
            import subprocess, tempfile
            import soundfile as _sf
            fd, tmp = tempfile.mkstemp(suffix=".wav"); os.close(fd)
            _sf.write(tmp, np.asarray(audio, dtype=np.float32), SR, subtype="PCM_16")
            # مرآةُ `jni.c` حرفاً: `language = "en"` (لا ar — قِيس أن الفارق داخل مجال الثقة نظيفاً، لكنّ الاتّهامَ ضجيجاً عند حدّ
            # القرار يتأثّر بكل شيء) · greedy · هبوطُ الحرارة الافتراضيّ · no_context لا أثرَ له في نافذةٍ واحدة ≤ 30ث.
            # 🔤 D-298: رمزُ اللغة صار **معاملَ تجربةٍ لا ثابتاً** — المحركُ يفكّ بـ`en` والتدريبُ يُلصق `<|ar|>`.
            cmd = [self.cli, "-m", self.model_path, "-f", tmp, "-l", self.lang, "-t", str(self.threads),
                   "-bo", "1", "-bs", "1", "-nt", "-np"] + list(getattr(self, "cli_flags", []))
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            os.remove(tmp)
            if r.returncode:
                raise RuntimeError(f"whisper-cli rc={r.returncode}: {r.stderr[-200:]}")
            txt = " ".join(r.stdout.split())
            # 🚨 الصمتُ ليس نتيجة: ثانيةٌ من التلاوة لا تعطي نصّاً فارغاً إلا بعطب (نموذجٌ لم يُحمَّل · عَلَمٌ مرفوض).
            if not txt and len(audio) > SR:
                raise RuntimeError("whisper-cli أعاد نصّاً فارغاً لصوتٍ طوله "
                                   f"{len(audio)/SR:.1f}ث — stderr: {(r.stderr or '')[-200:]!r}")
            return txt
        feats = self.proc(audio, sampling_rate=SR, return_tensors="pt").input_features.to(self.device)
        kw = dict(self.gen_kwargs)
        if bias_ids and bias:
            torch = self.torch

            class _Bias:
                def __call__(self, input_ids, scores):
                    idx = torch.tensor(sorted(bias_ids), device=scores.device)
                    scores = scores.clone()
                    scores[:, idx] += bias
                    return scores

            kw["logits_processor"] = [_Bias()]
        with self.torch.no_grad():
            ids = self.model.generate(feats, num_beams=1, do_sample=False,
                                      max_new_tokens=200, **kw)
        txt = self.proc.batch_decode(ids, skip_special_tokens=True)[0]
        # ⚠️ transformers 5 يُبقي رموزَ التحكّم (`<|ar|><|transcribe|><|notimestamps|>`) في المخرَج
        # رغم `skip_special_tokens=True`. تُقشَّر صراحةً: بقاؤها يجعلها «كلماتٍ زائدة» في الحكم.
        return re.sub(r"<\|[^|]*\|>", " ", txt).strip()

    def _pick(self, audio, bias_ids, bias, ref_text, lam, k):
        """مسارٌ واحد: جشعٌ حين lam=0، وشعاعٌ بإعادة ترتيبٍ حين lam>0."""
        if lam > 0:
            return self.rescore(self.nbest(audio, k), ref_text, lam)[0]
        return self._raw(audio, bias_ids, bias)

    def rescore(self, cands, ref_text, lam):
        """🎯 **إعادةُ ترتيبٍ على مستوى الكلمة** (‏M1-4، البديلُ الناجح عن ترجيح الرموز).

        ⛔ **لماذا سقط ترجيحُ الرموز:** قِيس أن 47 من 54 رمزاً في مخرَج النموذج موجودةٌ أصلاً في
        رموز النصّ المتوقَّع (حركاتٌ وحروفٌ عربيةٌ مشتركةٌ بين كل الكلمات)، فالترجيحُ يرفع الخطأَ
        والصوابَ معاً ⇒ **أثرُه صفر**. أما الكلمةُ **بعد التطبيع** فوحدةُ تمييزٍ حقيقية.

        الاختيار: `لوغاريتمُ الاحتمال الصوتي + lam × دقّةُ المطابقة مع المتوقَّع`. فالمرشّحُ لا
        يُختار لأنه يشبه المرجع بل لأن **الصوتَ يسنده** وهو أشبهُ بالمرجع من إخوته.
        ⚠️ وكلَّما كبر [lam] اقترب المخرَجُ من المرجع مهما قرأ المستخدم ⇒ **يُخفي الخطأ**.
        فالحكمُ عليه بعيّنة الأخطاء المحقونة لا بالتتبّع وحده.
        """
        if not cands:
            return "", None
        if not ref_text or lam <= 0:
            return cands[0][0], None
        import scorer as _sc
        ref_words = ref_text.split()
        best, best_val, best_acc = cands[0][0], None, None
        for text, ac in cands:
            sc_ = _sc.score(ref_words, text, _sc.DEFAULT)
            acc = sc_["correct"] / max(sc_["total"], 1)
            val = ac + lam * acc
            if best_val is None or val > best_val:
                best, best_val, best_acc = text, val, acc
        return best, best_acc

    def transcribe(self, raw_audio, bias_ids=None, bias=0.0, ref_text=None, lam=0.0, k=5):
        """مرآةُ `LongAudioTranscriber.transcribe` بحذافيرها (بواجهةٍ أماميةٍ قابلةٍ للتبديل)."""
        if self.gate:
            # 🔇 كتمُ الضجيج **داخل المسار** بدقّةٍ عائمة — كما يفعل المحرك تماماً؛ لا مقروءاً
            # من ملفٍ منقّىً مسبقاً (‏PCM16). الفرقُ بينهما ليس نظرياً: على SNR 5 قِيس فرقٌ
            # في التتبّع بين المسارين، ومصدرُه تكميمُ الملف لا الخوارزمية (اللتان تطابقتا
            # بايتاً: ارتباط 1.000000 على صوتٍ حقيقي).
            import denoise as _dn
            raw_audio = _dn.denoise(raw_audio)
        if self.frontend == "new":
            import frontend as fe
            audio = fe.normalize_v2(raw_audio)
            floor = (fe.speech_floor_prop(audio) if getattr(self, 'floor_rule', '') == 'prop'
                     else fe.speech_floor_v2(audio))
        else:
            audio = al_normalize(raw_audio)
            floor = al_speech_floor(audio)
        window = WINDOW_SECONDS * SR
        cuts = getattr(self, "cuts", None)
        key = getattr(self, "_item_id", None)
        if cuts and key in cuts:
            utts = [tuple(c) for c in cuts[key]]
        else:
            utts = split_at_silences(audio, floor)
        # 🔀 مرآةُ D-250: تجميعُ النطقات في مجموعاتٍ لا تعبر سكتةً ≥ MAX_GAP ولا تتجاوز [group_cap].
        # [group_cap] قابلٌ للضبط: القاعدةُ المشحونة نافذةٌ كاملة (25ث)، وقِيس أن مجموعةً بهذا الطول
        # فيها كلامٌ غيرُ متجانس (‏مقدّمةٌ + بدايةٌ خاطئة + آية) تجعل whisper-tiny يعطي **كلمةً واحدة**.
        if len(utts) > 1:
            groups = group_utterances(utts, self.group_cap, MAX_GAP_SECONDS * SR)
        else:
            groups = [(0, utts[0][1] if utts else len(audio))]
        if len(groups) > 1 or (groups and groups[0][1] - groups[0][0] <= window + SR):
            parts = []
            for a, b in groups:
                seg = audio[a:min(b, len(audio))]
                if len(seg) <= window + SR:
                    parts.append(self._pick(seg, bias_ids, bias, ref_text, lam, k))
                else:
                    parts.append(self._windowed(seg, bias_ids, bias, ref_text, lam, k))
            return " ".join(p for p in parts if p), len(groups)
        if len(audio) <= window + SR:
            return self._pick(audio, bias_ids, bias, ref_text, lam, k), 1
        return self._windowed(audio, bias_ids, bias, ref_text, lam, k), 1

    def _windowed(self, audio, bias_ids, bias, ref_text, lam, k):
        window = WINDOW_SECONDS * SR
        parts, start = [], 0
        while start < len(audio):
            hard = min(start + window, len(audio))
            end = hard if hard == len(audio) else quietest_cut(audio, start + window * 2 // 3, hard)
            parts.append(self._pick(audio[start:end], bias_ids, bias, ref_text, lam, k))
            if end == len(audio):
                break
            start = end
        return " ".join(p for p in parts if p)


def resolve_set(name):
    """`g1` · `g2:<condition>` · `g3:<variant>` ⇒ (المجلد، الوسم)."""
    if name == "g1":
        return WAV, "g1"
    if name.startswith("g2:"):
        cond = name.split(":", 1)[1]
        return os.path.join(G2, cond), f"g2-{cond}"
    if name.startswith("g4c:"):         # الطويلُ خافتاً/مضجَّجاً — أقربُ ما يكون لتسجيل الهاتف
        v = name.split(":", 1)[1]
        return os.path.join(WORK, "g4c", v), f"g4c-{v}"
    if name.startswith("g4b:"):         # الطويلُ + سلوكُ المتعلّم — حالةُ المالك بنصِّها
        v = name.split(":", 1)[1]
        return os.path.join(WORK, "g4b", v), f"g4b-{v}"
    if name.startswith("g4"):           # g4 نظيف · g4n ضجيج · g4q خافت · g4c صعب
        return os.path.join(WORK, name), name
    if name.startswith("g3r:"):          # حقنُ ورشٍ وقالون (‏inject_riwaya.py)
        v = name.split(":", 1)[1]
        return os.path.join(WORK, "g3r", v), f"g3r-{v}"
    if name.startswith("g3:"):
        v = name.split(":", 1)[1]
        return os.path.join(WORK, "g3", v), f"g3-{v}"
    raise SystemExit(f"مجموعةٌ غير معروفة: {name} (‏g1 · g2:<condition> · g3:<variant>)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="g1")
    ap.add_argument("--model", default="shipped")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--ids", help="ملفُّ معرّفاتٍ (واحدٌ في السطر) لتقييد المجموعة")
    ap.add_argument("--threads", type=int, default=4)
    # 🔪 **D-345:** عتبةُ السكوت هامشٌ ثابتٌ ‎+6 د.ب فوق الأرضية، وعند نسبةِ إشارةٍ 5 د.ب يكون
    # الكلامُ نفسُه نحوَ 5 د.ب فوقها ⇒ تُحسب 54٪ من الإطارات صمتاً فيُقطَّع النطقُ في أثنائه
    # (‏14 نطقاً بدل 6 · 53٪ من القطوع داخلَ كلام). و`prop` هامشٌ نسبيٌّ يضيق حين يضيق المدى،
    # **ومطابقٌ حرفياً في النظيف**. يُقاس أثرُه في الدقّة قبل أن يُقترح على المحرك.
    # 🎯 **حدودٌ مثاليّةٌ (oracle)** — تُقرأ من ملفٍّ بدل كشفها من الصوت. بها يُفصل أثرُ **الضجيج**
    # عن أثر **رداءة الحدود**: إن عادت الدقّةُ بالحدود الصحيحة فالعطبُ في الكشف لا في السمع.
    ap.add_argument("--cuts-json", default="", help="ملفُّ حدودٍ {id: [[a,b],…]} بالعيّنات — يغلب كشفَ السكتات")
    ap.add_argument("--floor-rule", default="v2", choices=["v2", "prop"],
                    help="قاعدةُ عتبة السكوت: v2 ثابتٌ +6 (المشحون) · prop نسبةٌ من المدى (D-345)")
    ap.add_argument("--group-cap", type=float, default=float(WINDOW_SECONDS),
                    help="سقفُ طول المجموعة بالثواني (المشحون 25) — D-262")
    ap.add_argument("--gate", action="store_true",
                    help="كتمُ الضجيج داخل المسار (عائم) — كما في المحرك")
    ap.add_argument("--lam", type=float, default=0.0,
                    help="وزنُ مطابقةِ المتوقَّع في إعادة الترتيب (‏M1-4) — 0 = جشعٌ كما المحرك")
    ap.add_argument("--nbest", type=int, default=5, help="عرضُ الشعاع مع --lam")
    ap.add_argument("--bias", type=float, default=0.0,
                    help="ترجيحُ رموز النصّ المتوقَّع (‏M1-4) — 0 = بلا قيد؛ جرّب 1..5")
    ap.add_argument("--frontend", default="old", choices=["old", "new"],
                    help="الواجهة الأمامية: old = المشحونة · new = frontend.py (‏M0-5)")
    ap.add_argument("--backend", default="hf", choices=["hf", "cli"],
                    help="hf = transformers fp32 (المرآة) · cli = whisper-cli بالنموذج q8 نفسِه (مرآةُ المحرك على CI)")
    ap.add_argument("--cli", default=os.environ.get("WHISPER_CLI", ""), help="مسارُ whisper-cli مع --backend cli")
    ap.add_argument("--lang", default="en", help="رمزُ لغة الفكّ مع --backend cli (en = ما يفعله المحرك اليوم · ar = ما دُرِّب عليه النموذج)")
    ap.add_argument("--parity", help="مخرَجُ whisperBatch من المحاكي للمقارنة الحرفية")
    ap.add_argument("--hyps", help="مع --parity: ملفُّ الفرضيات المحلي")
    args = ap.parse_args()

    if args.parity:
        return parity(args.parity, args.hyps)

    src, tag = resolve_set(args.set)
    if not os.path.isdir(src):
        raise SystemExit(f"⛔ لا مجلد {src}")
    ids = sorted(f[:-4] for f in os.listdir(src) if f.endswith(".wav"))
    if args.ids:
        keep = {ln.strip() for ln in open(args.ids, encoding="utf-8") if ln.strip()}
        ids = [i for i in ids if i in keep]
    if args.limit:
        ids = ids[: args.limit]

    model_path = MODELS.get(args.model, args.model)
    suffix = "" if args.frontend == "old" else f"_fe-{args.frontend}"
    if args.bias:
        suffix += f"_bias{args.bias:g}"
    if args.lam:
        suffix += f"_lam{args.lam:g}k{args.nbest}"
    if args.gate:
        suffix += "_gate"
    if args.floor_rule != "v2":
        suffix += f"_floor{args.floor_rule}"
    if args.cuts_json:
        suffix += "_oracle"
    if args.group_cap != WINDOW_SECONDS:
        suffix += f"_cap{args.group_cap:g}"
    out = args.out or os.path.join(WORK, f"hyps_{args.model}_{tag}{suffix}.json")
    done, meta = {}, {}
    if os.path.exists(out):
        prev = json.load(open(out, encoding="utf-8"))
        done, meta = prev.get("hyps", {}), prev.get("meta", {})

    refs = {}
    if args.bias or args.lam:
        import json as _j
        src = ("inject_plan_riwaya.json" if tag.startswith("g3r-")
               else "inject_plan.json" if tag.startswith("g3-") else "sample.json")
        refs = {i["id"]: i["refText"] for i in
                _j.load(open(os.path.join(HERE, src), encoding="utf-8"))["items"]}
        print(f"🎯 قيدٌ ناعم بترجيح {args.bias:+.1f} على رموز النصّ المتوقَّع", flush=True)

    print(f"⏳ تحميل {model_path} …", flush=True)
    t0 = time.time()
    tr = Transcriber(model_path, frontend=args.frontend, threads=args.threads, gate=args.gate,
                     group_cap=int(args.group_cap * SR), backend=args.backend, cli=args.cli, lang=args.lang,
                     floor_rule=args.floor_rule)
    if args.cuts_json:
        tr.cuts = json.load(open(args.cuts_json, encoding="utf-8"))
        print(f"🎯 حدودٌ مثاليّةٌ لـ{len(tr.cuts)} بنداً من {args.cuts_json}", flush=True)
    load_ms = int((time.time() - t0) * 1000)
    meta = {"model": args.model, "modelPath": str(model_path), "set": tag,
            "frontend": args.frontend,
            "lang": args.lang,
            "engine": (f"whisper.cpp/whisper-cli q8 · -l {args.lang} · -nc (مرآةُ المحرك على CI)" if args.backend == "cli"
                       else "transformers-cpu (مرآة LongAudioTranscriber)"), "loadMs": load_ms,
            "flags": "num_beams=1, do_sample=False (greedy — مرآة -bo 1 -bs 1)"}
    print(f"✅ حُمّل في {load_ms/1000:.1f}ث — {len(ids)} بنداً ({len(done)} منجزٌ سابقاً)", flush=True)

    todo = [i for i in ids if i not in done]
    for n, item in enumerate(todo, 1):
        x, sr = sf.read(os.path.join(src, item + ".wav"), dtype="float32")
        if sr != SR:
            done[item] = {"error": f"معدّلٌ غير متوقَّع {sr}"}
            continue
        t0 = time.time()
        tr._item_id = item          # 🎯 لتُقرأ حدودُ هذا البند من ملفّ الحدود المثاليّة إن وُجد
        try:
            bias_ids = tr.bias_for(refs.get(item)) if args.bias else None
            text, parts = tr.transcribe(x, bias_ids, args.bias,
                                        ref_text=refs.get(item), lam=args.lam, k=args.nbest)
            done[item] = {"text": " ".join(text.split()), "ms": int((time.time() - t0) * 1000),
                          "audioMs": int(len(x) * 1000 / SR), "rc": 0, "windows": parts}
        except Exception as e:                       # بندٌ لا يُسقط التشغيل كله
            done[item] = {"error": str(e)[:200]}
        if n % 10 == 0 or n == len(todo):
            json.dump({"meta": meta, "hyps": done}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
            el = time.time()
            print(f"  {n}/{len(todo)}  ({item})", flush=True)
    json.dump({"meta": meta, "hyps": done}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    ok = sum(1 for v in done.values() if "error" not in v)
    print(f"DONE {ok}/{len(done)} ⇒ {out}", flush=True)
    return 0


def parity(emu_path, hyps_path):
    """⚖️ المرآة ↔ المحرك: تطابقُ نصوص التفريغ حرفياً على البنود المشتركة.

    مخرَجُ `whisperBatch` أسطرٌ `id<TAB>text` (أو `id|text`). العتبةُ المعلنة في خارطة الطريق:
    **≥ 90٪** — وكان الخادمُ والمحاكي 37/40 (‏92.5٪) في REPORT.md §٥.
    """
    import re
    sys.path.insert(0, HERE)
    import scorer
    hyps = json.load(open(hyps_path, encoding="utf-8"))["hyps"]
    emu = {}
    for ln in open(emu_path, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        parts = re.split(r"[\t|]", ln, maxsplit=1)
        if len(parts) == 2:
            emu[parts[0].strip()] = parts[1].strip()
    common = [i for i in emu if i in hyps and "error" not in hyps[i]]
    if not common:
        print("⛔ لا بنود مشتركة — تحقّق من صيغة ملف المحاكي")
        return 1
    exact = norm_eq = 0
    diffs = []
    for i in common:
        a, b = emu[i], hyps[i]["text"]
        if a == b:
            exact += 1
            norm_eq += 1
        else:
            na = " ".join(scorer.norm(w) for w in a.split())
            nb = " ".join(scorer.norm(w) for w in b.split())
            if na == nb:
                norm_eq += 1
            else:
                diffs.append((i, a, b))
    n = len(common)
    print(f"البنود المشتركة: {n}")
    print(f"تطابقٌ حرفي: {exact}/{n} = {100*exact/n:.1f}%")
    print(f"تطابقٌ بعد التطبيع: {norm_eq}/{n} = {100*norm_eq/n:.1f}%")
    print(f"الحكم: {'✅ المرآة أمينة' if 100*norm_eq/n >= 90 else '❌ المرآة ليست مرآة — لا يُبنى على أرقامها'}")
    for i, a, b in diffs[:8]:
        print(f"\n— {i}\n  محاكي: {a[:120]}\n  مرآة : {b[:120]}")
    return 0 if 100 * norm_eq / n >= 90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
