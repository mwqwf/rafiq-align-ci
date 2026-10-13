#!/usr/bin/env python3
"""🔤 **ضبطُ نموذج CTC صوتيّ على التلاوة** — M3-2 (‏D-703 · 2026-09-18).

المسارُ المعتمد بعد أن لم يجتز نموذجٌ جاهزٌ شرطَ الترخيص: `facebook/wav2vec2-base` (Apache-2.0) يُضبط بـCTC على
**تلاواتنا** بتسمياتٍ يولّدها `QuranG2P` (إشرافٌ ضعيف — `QuranG2PExport` يكتبها JSONL بلا نصٍّ قرآنيّ).

    # فحصُ الآلية محلياً بلا شبكة: نموذجٌ صغيرٌ عشوائيّ يحفظ ثماني آيات (يجب أن يهبط الخسارُ وأن يقترب PER من الصفر)
    python tools/tasmi_phoneme/ctc_train.py --smoke --labels work/g2p_labels.jsonl --items tools/tasmi_bench/sample.json \
        --wav-dir tools/tasmi_bench/work/wav

    # التدريبُ الحقيقيّ (معالجٌ رسوميٌّ مجانيّ — كولاب/كاغل):
    python tools/tasmi_phoneme/ctc_train.py --labels g2p_labels.jsonl --items train_items.json --wav-dir clips/ \
        --base facebook/wav2vec2-base --steps 20000 --out out_ctc

`--items`: قائمةٌ `{"id","riwaya","globalIndex"}` (صيغةُ `sample.json` نفسُها) والصوتُ `<wav-dir>/<id>.wav` أحاديٌّ 16ك.هز.
⛔ **ولا يُقاس النموذجُ بتسمياتٍ من المحوّل نفسِه وحدها**: PER هنا يقيس مطابقتَه لـ`QuranG2P`، والبوّابةُ بمرجعٍ بشريّ
(`validate_gold.py`) — وإلا صار القياسُ دائريّاً.
"""
import argparse
import json
import math
import os
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SR = 16000
PAD, UNK, DELIM = "[PAD]", "[UNK]", "|"


# ───────────── التسميات ─────────────

def load_labels(path):
    """{(riwaya, flat): (words, skip)} من تصدير `QuranG2PExport`."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for ln in f:
            o = json.loads(ln)
            out[(o["r"], o["flat"])] = (o["words"], set(o["skip"]))
    return out


def ayah_target(words, skip):
    """أصواتُ الآية بفاصل كلماتٍ `|` — أو None إن كان فيها ما لا يصلح تسميةً (لا تُقصّ الآيةُ فيختلّ المقطع)."""
    if skip:
        return None
    seq = []
    for i, w in enumerate(words):
        if not w:
            continue
        if seq:
            seq.append(DELIM)
        seq.extend(w)
    return seq or None


def build_vocab(labels):
    """المفرداتُ من التسميات نفسِها (مغلقةٌ على مخزون `QuranG2P.INVENTORY`) + الفراغ الصامت والمجهول والفاصل."""
    phones = sorted({p for (words, _) in labels.values() for w in words for p in w})
    vocab = {PAD: 0, UNK: 1, DELIM: 2}
    for p in phones:
        vocab.setdefault(p, len(vocab))
    return vocab


# ───────────── المقياس ─────────────

def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = cur
    return prev[len(b)]


def per(refs, hyps):
    """نسبةُ خطأ الأصوات (بلا فواصل الكلمات) — مجموعُ المسافات ÷ مجموع أطوال المراجع."""
    e = n = 0
    for r, h in zip(refs, hyps):
        r = [p for p in r if p != DELIM]
        h = [p for p in h if p != DELIM]
        e += edit_distance(r, h)
        n += len(r)
    return e / max(1, n)


def ctc_greedy(ids, inv):
    out, prev = [], None
    for i in ids:
        if i != prev and i != 0:
            out.append(inv.get(i, UNK))
        prev = i
    return out


# ───────────── البيانات ─────────────

def surah_starts(index_path):
    """بداياتُ السور المسطّحة من `index.jz` (gzip) — لتحويل `ayahId` «س:آ» إلى فهرسٍ مسطّح."""
    import gzip
    idx = json.loads(gzip.decompress(open(index_path, "rb").read()).decode("utf-8"))
    return [s["start"] for s in idx["surahs"]]


def load_items(items_path, labels, wav_dir, index_path=None, max_seconds=None):
    """صيغتان: `sample.json` (`id`·`riwaya`·`globalIndex` والصوتُ `<wav-dir>/<id>.wav`) أو `manifest.jsonl` من
    `tools/finetune/prep.py` (`path`·`riwaya`·`ayahId` والصوتُ `<wav-dir>/<path>` flac) — فلا مُعِدٌّ ثانٍ للبيانات."""
    if items_path.endswith(".jsonl"):
        starts = surah_starts(index_path or os.path.join(os.path.dirname(__file__), "..", "..", "core", "quran", "src",
                                                          "main", "assets", "quran", "index.jz"))
        items = []
        for ln in open(items_path, encoding="utf-8"):
            r = json.loads(ln)
            s, a = (int(x) for x in r["ayahId"].split(":"))
            items.append({"id": r["path"], "riwaya": r["riwaya"], "globalIndex": starts[s - 1] + a - 1, "file": r["path"],
                          "seconds": r.get("seconds"), "reciter": r.get("reciter")})
    else:
        items = json.load(open(items_path, encoding="utf-8"))
        items = items["items"] if isinstance(items, dict) else items
    out, dropped = [], 0
    for it in items:
        key = (it["riwaya"], it["globalIndex"])
        wav = os.path.join(wav_dir, it["file"]) if "file" in it else os.path.join(wav_dir, it["id"] + ".wav")
        if key not in labels or not os.path.exists(wav):
            dropped += 1
            continue
        # ⛔ لا يُقصّ صوتٌ أطولُ من الحدّ مع إبقاء تسميته كاملة — ذلك يُفسد محاذاةَ CTC؛ يُسقط البندُ كلُّه.
        if max_seconds and it.get("seconds") and it["seconds"] > max_seconds:
            dropped += 1
            continue
        tgt = ayah_target(*labels[key])
        if tgt is None:
            dropped += 1
            continue
        # ⛔ الصوتُ يُقصّ عند الحدّ والهدفُ يبقى كاملاً ⇒ خسارةُ CTC لا نهائيّة. يُسقَط البندُ هنا لا هناك.
        if max_seconds and not ctc_feasible(max_seconds, len(tgt)):
            dropped += 1
            continue
        out.append({"id": it["id"], "riwaya": it["riwaya"], "wav": wav, "target": tgt, "reciter": it.get("reciter"),
                    "seconds": it.get("seconds")})   # ⚖️ يلزم --eval-max-seconds (D-757) — كان يُسقَط فيعمى الترشيح
    return out, dropped


def ctc_feasible(seconds, n_target, conv_stride=(5, 2, 2, 2, 2, 2, 2)):
    """أيكفي عددُ إطاراتِ النموذج لهدفٍ بهذا الطول؟

    ⛔ **عطبٌ مقيسٌ (2026-09-20):** البندُ الذي لا يحمل حقلَ `seconds` (مثلُ `sample.json`) **لا يُسقَط**
    عند `--max-seconds`، فيُقصّ صوتُه ويبقى هدفُه كاملاً ⇒ CTC يطلب مساراً لا وجودَ له فتصير الخسارةُ
    **لا نهائيّة** ويموت الشوطُ عند أوّل بندٍ طويل (وقع عند الخطوة 19 في أوّل شوطِ طالبٍ ضيّق).
    و`fp16` كان يُلام ظلماً — والعلّةُ حسابيّةٌ بحتة.
    """
    hop = 1
    for s in conv_stride:
        hop *= s
    frames = int(seconds * SR) // hop
    # CTC يحتاج إطاراً لكلّ رمزٍ + إطارَ فراغٍ بين كلّ رمزَين متماثلَين (حدٌّ أدنى متحفّظ)
    return frames >= n_target + 1


def read_wav(path, max_seconds):
    import soundfile as sf
    x, sr = sf.read(path, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        raise ValueError(f"{path}: معدّل {sr} لا {SR}")
    return x[: int(max_seconds * SR)]


# ───────────── النموذج ─────────────

def make_model(base, vocab, smoke):
    import torch
    from transformers import Wav2Vec2Config, Wav2Vec2ForCTC
    if smoke:
        # نموذجٌ صغيرٌ عشوائيّ — يثبت الآليةَ (بيانات ⇐ دفعة ⇐ خسارة CTC ⇐ فكّ ⇐ PER) بلا تنزيل.
        cfg = Wav2Vec2Config(
            vocab_size=len(vocab), hidden_size=64, num_hidden_layers=2, num_attention_heads=2, intermediate_size=128,
            conv_dim=(32, 32, 32, 32, 32, 32, 32), conv_stride=(5, 2, 2, 2, 2, 2, 2), conv_kernel=(10, 3, 3, 3, 3, 2, 2),
            num_conv_pos_embeddings=16, num_conv_pos_embedding_groups=4, pad_token_id=0,
            ctc_loss_reduction="mean", mask_time_prob=0.0, layerdrop=0.0,
        )
        torch.manual_seed(0)
        return Wav2Vec2ForCTC(cfg)
    model = Wav2Vec2ForCTC.from_pretrained(
        base, vocab_size=len(vocab), pad_token_id=0, ctc_loss_reduction="mean",
        ignore_mismatched_sizes=True, mask_time_prob=0.05, layerdrop=0.05,
    )
    model.freeze_feature_encoder()
    return model


def make_student(teacher_dir, vocab, hidden, layers, heads=6):
    """🪶 نموذجٌ **أضيق** يبلغ هدفَ الحجم (‏20–40 م.ب) — وهو الطريقُ الوحيدُ إليه بعد [[D-719]].

    [[D-719]] قاس أنّ **بترَ الطبقات لا يبلغ الهدف أبداً**: حتى طبقتان تعطيان 48.1 م.ب، لأنّ
    مستخرِجَ الخصائص الالتفافيّ والتضمينَ 768 لا يتقلّصان بالبتر. فالتضييقُ (‏hidden 384) هو الباب.

    **ويُبذَر من المعلّم لا من العدم**: مستخرِجُ الخصائص الالتفافيّ **متطابقُ الشكل** بين العريض
    والضيّق (‏conv_dim ثابتٌ 512)، فيُنسخ كما هو ⇒ يُوفَّر على الطالب تعلُّمُ الطبقةِ الصوتيّة
    الأولى كلِّها. وما اختلف شكلُه (المحوّل والرأس) يبدأ عشوائيّاً.
    ⛔ ولا يُولَّد بهذا نصٌّ ولا صوت: الأوزانُ تُنسخ والتدريبُ على تلاواتٍ منشورةٍ بوسمِ محوّلنا.
    """
    import torch
    from transformers import Wav2Vec2Config, Wav2Vec2ForCTC
    t = Wav2Vec2ForCTC.from_pretrained(teacher_dir)
    tc = t.config
    cfg = Wav2Vec2Config(
        vocab_size=len(vocab), hidden_size=hidden, num_hidden_layers=layers,
        num_attention_heads=heads, intermediate_size=hidden * 4,
        conv_dim=tc.conv_dim, conv_stride=tc.conv_stride, conv_kernel=tc.conv_kernel,
        num_conv_pos_embeddings=tc.num_conv_pos_embeddings,
        num_conv_pos_embedding_groups=tc.num_conv_pos_embedding_groups,
        feat_extract_norm=tc.feat_extract_norm, do_stable_layer_norm=tc.do_stable_layer_norm,
        pad_token_id=0, ctc_loss_reduction="mean", mask_time_prob=0.05, layerdrop=0.05,
    )
    s = Wav2Vec2ForCTC(cfg)
    ts, ss = t.state_dict(), s.state_dict()
    copied = 0
    for k, v in ts.items():
        if k in ss and ss[k].shape == v.shape:
            ss[k] = v.clone()
            copied += 1
    s.load_state_dict(ss)
    s.freeze_feature_encoder()
    n = sum(p.numel() for p in s.parameters())
    print(f"🪶 طالبٌ ضيّق: hidden={hidden} · طبقات={layers} · {n/1e6:.1f} م.معلمة "
          f"· نُسخ من المعلّم {copied}/{len(ts)} موتّراً", flush=True)
    del t
    return s


def augment_wave(x, rng, np):
    """🎚️ **توليفُ مجال المتعلّم أثناء التدريب** (D-791 · 2026-09-22 — بعد [[D-790]]: `PER` 8.4 على المحترفين لم ينتقل إلى
    المتعلّمين). كلُّ عيّنةٍ (باحتمال `--augment`) تُمرَّر بواحدٍ أو أكثر من: كسبٍ عشوائيّ (−30..+6 د.ب · هامسٌ أو بعيد) ·
    ضجيجٍ أبيض/ورديٍّ بـSNR 5..25 د.ب (مروحة/طريق) · تمريرٍ منخفض (ميكروفونُ هاتفٍ رخيص) · قصٍّ صلب (تشبّع). النصُّ لا يتغيّر
    فالهدفُ يبقى — كما في `tools/tasmi_bench/augment.py` (G2) لكن على الطاير وبلا ملفّات. تُعاد إلى تطبيعٍ قياسيّ بعدها."""
    y = x.astype("float32")
    r = rng.random()
    if r < 0.6:                                              # كسب
        g = 10 ** (rng.uniform(-30.0, 6.0) / 20.0)
        y = y * g
    if rng.random() < 0.6:                                   # ضجيج
        snr = rng.uniform(5.0, 25.0)
        noise = np_rng_normal(rng, len(y), np)
        if rng.random() < 0.5:                               # ورديّ تقريباً: تكاملٌ مرشَّح
            noise = np.cumsum(noise); noise -= np.convolve(noise, np.ones(64) / 64, mode="same"); noise /= (np.std(noise) + 1e-7)
        p_sig = float(np.mean(y ** 2)) + 1e-9
        p_noise = p_sig / (10 ** (snr / 10.0))
        y = y + noise * np.sqrt(p_noise)
    if rng.random() < 0.3:                                   # تمريرٌ منخفض (متوسّطٌ متحرّك 3..9)
        k = int(rng.integers(3, 10)) if hasattr(rng, "integers") else int(rng.randint(3, 10))
        y = np.convolve(y, np.ones(k) / k, mode="same")
    if rng.random() < 0.15:                                  # تشبّع
        y = np.clip(y, -0.6, 0.6) / 0.6
    return y


def np_rng_normal(rng, n, np):
    return (rng.standard_normal(n) if hasattr(rng, "standard_normal") else np.random.RandomState(rng.randint(0, 2**31 - 1)).standard_normal(n)).astype("float32")


def batches(items, vocab, bs, max_seconds, rng, cache, augment=0.0):
    import numpy as np
    import torch
    np_rng = np.random.default_rng(1446)
    order = list(range(len(items)))
    while True:
        rng.shuffle(order)
        for k in range(0, len(order) - bs + 1, bs):
            chunk = [items[i] for i in order[k:k + bs]]
            wavs = []
            for it in chunk:
                if it["id"] not in cache:
                    x = read_wav(it["wav"], max_seconds)
                    cache[it["id"]] = (x - x.mean()) / (x.std() + 1e-7)
                w = cache[it["id"]]
                if augment > 0 and np_rng.random() < augment:
                    w = augment_wave(w, np_rng, np)
                    w = (w - w.mean()) / (w.std() + 1e-7)
                wavs.append(w)
            n = max(len(w) for w in wavs)
            inp = np.zeros((len(wavs), n), dtype="float32")
            att = np.zeros((len(wavs), n), dtype="int64")
            for i, w in enumerate(wavs):
                inp[i, : len(w)] = w
                att[i, : len(w)] = 1
            tl = max(len(it["target"]) for it in chunk)
            lab = np.full((len(chunk), tl), -100, dtype="int64")
            for i, it in enumerate(chunk):
                ids = [vocab.get(p, 1) for p in it["target"]]
                lab[i, : len(ids)] = ids
            yield torch.from_numpy(inp), torch.from_numpy(att), torch.from_numpy(lab), chunk


def evaluate(model, items, vocab, max_seconds, device):
    import torch
    inv = {v: k for k, v in vocab.items()}
    model.eval()
    refs, hyps = [], []
    with torch.no_grad():
        for it in items:
            x = read_wav(it["wav"], max_seconds)
            x = (x - x.mean()) / (x.std() + 1e-7)
            logits = model(torch.from_numpy(x)[None].to(device)).logits[0]
            hyps.append(ctc_greedy(logits.argmax(-1).tolist(), inv))
            refs.append(it["target"])
    model.train()
    return per(refs, hyps), hyps


def quantize_and_measure(model, held, vocab, max_seconds, out_dir, n=100):
    """int8 ديناميكيٌّ للطبقات الخطّيّة (بلا تنزيل أدوات) — الحجمُ على القرص وPER قبل التكميم وبعده على المعالج."""
    import copy
    import torch
    cpu = copy.deepcopy(model).float().cpu().eval()
    q = torch.ao.quantization.quantize_dynamic(copy.deepcopy(cpu), {torch.nn.Linear}, dtype=torch.qint8)
    sizes = {}
    for name, m in (("fp32", cpu), ("int8", q)):
        path = os.path.join(out_dir, f"state_{name}.pt")
        torch.save(m.state_dict(), path)
        sizes[name] = os.path.getsize(path) / 1e6
    sub = held[:n]
    p32, _ = evaluate(cpu, sub, vocab, max_seconds, "cpu")
    p8, _ = evaluate(q, sub, vocab, max_seconds, "cpu")
    print(f"📦 fp32 {sizes['fp32']:.1f} م.ب ⇐ int8 {sizes['int8']:.1f} م.ب · PER على {len(sub)} آية: "
          f"{100 * p32:.1f}٪ ⇐ {100 * p8:.1f}٪", flush=True)
    return {"sizeMbFp32": sizes["fp32"], "sizeMbInt8": sizes["int8"], "perFp32Cpu": p32, "perInt8Cpu": p8, "quantN": len(sub)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--wav-dir", required=True)
    ap.add_argument("--index", help="مسارُ index.jz مع manifest.jsonl (افتراضاً من المستودع)")
    ap.add_argument("--base", default="facebook/wav2vec2-base")
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--max-seconds", type=float, default=20.0)
    ap.add_argument("--augment", type=float, default=0.0, help="🎚️ احتمالُ توليف كلّ عيّنةٍ بمجال المتعلّم (D-791): 0 = لا توليف")
    ap.add_argument("--holdout", type=float, default=0.05)
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--out", default="out_ctc")
    ap.add_argument("--fp16", action="store_true", help="حسابٌ مختلَط الدقّة على المعالج الرسومي (خسارةُ CTC تبقى 32 بتاً داخل HF)")
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--holdout-reciters", default="", help="قرّاءٌ يُعزلون للتقييم كلّياً (مفصولون بفاصلة) — بدل عيّنةٍ عشوائيّةٍ من القرّاء أنفسهم")
    ap.add_argument("--resume", action="store_true",
                    help="إن وُجدت نقطةُ حفظٍ في --out (‏trainer_state.json) يُستأنف منها — لجلساتٍ تنقطع (كولاب المجانيّ · D-709)")
    ap.add_argument("--quantize", action="store_true", help="بعد التدريب: int8 ديناميكيّ ويُقاس الحجمُ وPER قبله وبعده على المعالج")
    ap.add_argument("--student-from", help="مجلّدُ معلّمٍ مدرَّب ⇒ يُبنى طالبٌ أضيقُ يُبذَر منه (D-719)")
    ap.add_argument("--student-hidden", type=int, default=384)
    ap.add_argument("--student-layers", type=int, default=8)
    ap.add_argument("--student-heads", type=int, default=6)
    ap.add_argument("--eval-max-seconds", type=float, default=None,
                    help="⚖️ سقفُ طولِ آيات التقييم وحدَها (D-757): يُرفع --max-seconds للتدريب ويبقى المحجوزُ هو هو "
                         "فتبقى أرقامُ PER قابلةً للمقارنة بما قبلها. الافتراض: = --max-seconds (السلوكُ القديم)")
    ap.add_argument("--distill-from", help="🎓 مجلّدُ معلّمٍ يُقطَّر منه (D-755): الطالبُ يتعلّم احتمالاتِه كاملةً مع الوسم")
    ap.add_argument("--distill-alpha", type=float, default=0.0,
                    help="وزنُ التقطير في الخسارة: (1−α)·CTC + α·KL — ‏0 = لا تقطير ولا يُحمَّل معلّمٌ (السلوكُ القديمُ حرفاً)")
    ap.add_argument("--distill-temp", type=float, default=2.0, help="حرارةُ التليين في KL (تُضرب الخسارةُ في T² كالعادة)")
    ap.add_argument("--item-targets", help="🧑‍🏫 خ-8: jsonl {path, target:[رموز]} — هدفُ كلِّ مقطعٍ بعينه (وسمٌ زائفٌ من معلّمٍ كـMuaalem لقارئه نفسِه) بدل وسم الآية المشترك · والمفرداتُ تُبنى منه")
    ap.add_argument("--smoke", action="store_true", help="نموذجٌ صغيرٌ عشوائيّ يحفظ ثماني آياتٍ — فحصُ آليةٍ بلا شبكة")
    args = ap.parse_args()

    import torch
    rng = random.Random(1446)
    labels = load_labels(args.labels)
    vocab = build_vocab(labels)
    items, dropped = load_items(args.items, labels, args.wav_dir, args.index, args.max_seconds)
    if args.item_targets:
        # ⚠️ وسمُ الآية يبقى شرطَ دخول البند (سلامةُ المرجع) — ثمّ يُستبدل بهدف المقطع نفسِه
        tg = {}
        for ln in open(args.item_targets, encoding="utf-8"):
            o = json.loads(ln)
            if o.get("target"):
                tg[o["path"]] = list(o["target"])
        before = len(items)
        items = [dict(it, target=tg[it["id"]]) for it in items if it["id"] in tg]
        items = [it for it in items if not args.max_seconds or ctc_feasible(args.max_seconds, len(it["target"]))]
        vocab = {PAD: 0, UNK: 1, DELIM: 2}
        for p in sorted({t for it in items for t in it["target"]}):
            vocab.setdefault(p, len(vocab))
        dropped += before - len(items)
        print(f"🧑‍🏫 أهدافُ المقاطع من {args.item_targets}: {len(items)}/{before} بنداً · مفرداتٌ جديدة {len(vocab)}", flush=True)
    print(f"📚 {len(items)} آية صالحة ({dropped} أُسقطت: بلا صوتٍ أو بلا تسميةٍ صالحة) · مفردات {len(vocab)}", flush=True)
    if not items:
        raise SystemExit("⛔ لا بنود")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if args.smoke:
        # أقصرُ ثماني آيات: حفظُها ممكنٌ على المعالج في دقائق — والمطلوبُ هبوطُ الخسارة وPER نحو الصفر.
        items = sorted(items, key=lambda it: len(it["target"]))[:8]
        train, held = items, items
        args.steps, args.bs, args.lr, args.eval_every, args.max_seconds = 1200, 4, 3e-3, 300, 8.0
    elif args.holdout_reciters:
        hold = {r.strip() for r in args.holdout_reciters.split(",") if r.strip()}
        em = args.eval_max_seconds
        # ⚖️ المحجوزُ يُرشَّح **قبل** الخلط وبحالة rng نفسِها ⇒ هو هو القائمةُ والترتيبُ التي قِيس عليها ما قبله.
        held = [it for it in items if it.get("reciter") in hold and (em is None or not it.get("seconds") or it["seconds"] <= em)]
        train = [it for it in items if it.get("reciter") not in hold]
        rng.shuffle(held)
        print(f"🧍 قرّاءٌ محجوزون كلّياً {sorted(hold)}: {len(held)} آية للتقييم · {len(train)} للتدريب", flush=True)
        if not held or not train:
            raise SystemExit("⛔ القسمةُ بالقرّاء فارغةٌ في أحد طرفيها")
    else:
        rng.shuffle(items)
        k = max(1, int(len(items) * args.holdout))
        held, train = items[:k], items[k:]

    start = 1
    state_path = os.path.join(args.out, "trainer_state.json")
    if args.resume and os.path.exists(state_path) and os.path.exists(os.path.join(args.out, "config.json")):
        from transformers import Wav2Vec2ForCTC
        st = json.load(open(state_path, encoding="utf-8"))
        model = Wav2Vec2ForCTC.from_pretrained(args.out).to(device)
        if not args.smoke:
            model.freeze_feature_encoder()
        start = st["step"] + 1
        print(f"⏯️ استئنافٌ من الخطوة {st['step']} (PER آنذاك {100 * st.get('per', 1):.1f}٪)", flush=True)
    else:
        model = (make_student(args.student_from, vocab, args.student_hidden,
                              args.student_layers, args.student_heads)
                 if args.student_from else make_model(args.base, vocab, args.smoke)).to(device)
    teacher = None
    if args.distill_alpha > 0:
        if not args.distill_from:
            raise SystemExit("⛔ --distill-alpha بلا --distill-from: لا يُقطَّر من لا شيء")
        from transformers import Wav2Vec2ForCTC as _W
        teacher = _W.from_pretrained(args.distill_from).to(device).eval()
        for q in teacher.parameters():
            q.requires_grad_(False)
        if teacher.config.vocab_size != model.config.vocab_size:
            raise SystemExit(f"⛔ مفرداتُ المعلّم {teacher.config.vocab_size} ≠ الطالب {model.config.vocab_size} ⇒ KL بلا معنى")
        print(f"🎓 تقطيرٌ من {args.distill_from} · α={args.distill_alpha} · T={args.distill_temp}", flush=True)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.0 if args.smoke else 0.01)
    warm = max(1, args.steps // 20)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + start) / warm) * max(0.0, 1 - (s + start - 1) / args.steps) if not args.smoke else 1.0)
    os.makedirs(args.out, exist_ok=True)
    json.dump(vocab, open(os.path.join(args.out, "vocab.json"), "w", encoding="utf-8"), ensure_ascii=False)

    first_loss = None
    losses = []
    import time
    fp16 = args.fp16 and device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=fp16)
    t_start = time.time()
    if args.augment > 0:
        print(f"🎚️ توليفُ مجال المتعلّم على الطاير · p={args.augment}", flush=True)
    it_batches = batches(train, vocab, args.bs, args.max_seconds, rng, {}, augment=args.augment)
    model.train()
    for step in range(start, args.steps + 1):
        inp, att, lab, _ = next(it_batches)
        with torch.autocast("cuda", dtype=torch.float16, enabled=fp16):
            # ⚠️ نماذجُ group-norm (wav2vec2-base) لا تُعطى قناعَ الانتباه — الحشوُ أصفارٌ وحسب (وثائقُ HF)؛ ومع قناعٍ تنحرف.
            use_mask = getattr(model.config, "feat_extract_norm", "group") == "layer"
            out = model(inp.to(device), attention_mask=att.to(device) if use_mask else None, labels=lab.to(device))
        loss = out.loss
        if teacher is not None:
            # 🎓 KL(معلّم ‖ طالب) على الإطارات الحقيقيّة وحدَها — الحشوُ لا يُعلَّم.
            #    ⛔ بدقّةٍ كاملة خارج autocast: KL على fp16 يفيض في الذيل اللوغاريتميّ.
            with torch.no_grad():
                with torch.autocast("cuda", dtype=torch.float16, enabled=fp16):
                    t_logits = teacher(inp.to(device), attention_mask=att.to(device) if use_mask else None).logits
            s_logits = out.logits.float(); t_logits = t_logits.float()
            n = min(s_logits.shape[1], t_logits.shape[1])
            s_logits, t_logits = s_logits[:, :n], t_logits[:, :n]
            lens = model._get_feat_extract_output_lengths(att.sum(-1).to(device)).clamp(max=n)
            mask = (torch.arange(n, device=device)[None, :] < lens[:, None]).float()
            T = args.distill_temp
            kl = torch.nn.functional.kl_div(torch.log_softmax(s_logits / T, -1), torch.log_softmax(t_logits / T, -1),
                                            log_target=True, reduction="none").sum(-1)
            kd = (kl * mask).sum() / mask.sum().clamp(min=1.0) * (T * T)
            loss = (1.0 - args.distill_alpha) * loss + args.distill_alpha * kd
        if not math.isfinite(loss.item()):
            if fp16:
                opt.zero_grad(); scaler.update(); continue      # فيضٌ عابرٌ في fp16 — تُتخطّى الدفعةُ ويُصغَّر المقياس
            raise SystemExit(f"⛔ خسارةٌ غيرُ منتهية عند الخطوة {step}")
        opt.zero_grad()
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        sched.step()
        if step % args.log_every == 0:
            print(f"  · {step}/{args.steps} خسارة {sum(losses[-args.log_every:] or [loss.item()]) / max(1, len(losses[-args.log_every:])):.3f}"
                  f" · {(time.time() - t_start) / (step - start + 1):.2f}ث/خطوة", flush=True)
        losses.append(loss.item())
        first_loss = first_loss if first_loss is not None else loss.item()
        if step % args.eval_every == 0 or step == args.steps:
            p, hyps = evaluate(model, held[:200], vocab, args.max_seconds, device)
            print(f"  خطوة {step}: خسارة {sum(losses[-50:]) / len(losses[-50:]):.3f} · PER {100 * p:.1f}٪", flush=True)
            model.save_pretrained(args.out)
            json.dump({"step": step, "per": p}, open(state_path, "w", encoding="utf-8"))

    if not losses:                                   # استئنافٌ وجد الشوطَ مكتملاً
        losses = [float("nan")]; first_loss = float("nan")
    final = sum(losses[-20:]) / len(losses[-20:])
    p, hyps = evaluate(model, held[:200], vocab, args.max_seconds, device)
    summary = {"items": len(items), "firstLoss": first_loss, "finalLoss": final, "per": p, "smoke": args.smoke,
               "heldout": len(held), "holdoutReciters": args.holdout_reciters or None}
    if args.quantize:
        summary.update(quantize_and_measure(model, held, vocab, args.max_seconds, args.out))
    json.dump(summary, open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8"))
    print(f"✅ الخسارة {first_loss:.2f} ⇐ {final:.3f} · PER {100 * p:.1f}٪", flush=True)
    if args.smoke:
        ok = final < 0.25 * first_loss and p < 0.30
        print("🧪 الفحصُ الآلي:", "✅ الآليةُ سليمة (حُفظت الآياتُ الثماني)" if ok else "❌ لم يحفظ — عطبٌ في الآلية", flush=True)
        print("   مثال:", " ".join(hyps[0][:30]), flush=True)
        print("   مرجع:", " ".join(held[0]["target"][:30]), flush=True)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
