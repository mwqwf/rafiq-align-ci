#!/usr/bin/env python3
"""
🎓 ضبط whisper-tiny-ar-quran (Apache-2.0، tarteel-ai) على ورش/قالون/حفص من `prep.py` — الجولة الثانية `tuned-v2`.

حلقة PyTorch صريحة (لا Trainer — واجهته تتغيّر بين إصدارات transformers):
fp16 autocast · AdamW · تسخين خطي ثم اضمحلال · تقييم دوري بـWER على عيّنة محجوزة بعد تطبيع `norm()`.

ما تغيّر عن جولة v1 (‏2026-09-11 — بعد خمس جولاتٍ ضاعت على كولاب):
- 🔊 **تسويءٌ أثناء التدريب (‏D-270)** بنسبة `--aug-p`: مروحة (ضجيجٌ ورديّ) · **ثرثرةُ تلاواتٍ أخرى**
  (الثرثرةُ كلّفت المحرك ‎−8.73 نقطة) · خفوت · هاتف · بترُ طرف · قصّ. كلُّها **متّجهيّة** — الضجيجُ الورديّ
  بتشكيل الطيف كما في `tasmi_bench/augment.py` لا بحلقة بايثون كانت تكلّف 0.3ث للمقطع.
- ⚡ **الميل على المعالج الرسومي:** مسارُ torch في `WhisperFeatureExtractor(device=…)` — مطابقٌ لمسار numpy
  **بفرقٍ 0.0** (قِيس محلياً على transformers 5.16) وأسرعُ 6× على المعالج ونحوُ 100× على الرسومي.
  فتبقى للعمّال قراءةُ flac والتسويء فقط.
- 💾 **نقطةُ حفظٍ كاملة** (الأوزان + المحسِّن + الجدولة + الخطوة + موضعُ الدورة) كلَّ `--save-every` خطوة،
  تُرفع إلى R2 برابط PUT موقّعٍ **في خيطٍ خلفيّ** ⇒ الاستئنافُ يواصل من الخطوة نفسِها بالترتيب نفسِه،
  وانقطاعُ كولاب يكلّف دقائقَ لا الجولة. (استئنافُ v1 كان يحمّل الأوزانَ ويبدأ العدَّ من الصفر.)
- 🎭 SpecAugment المدمج في HF (`apply_spec_augment`) — أقنعةٌ زمنية وترددية خفيفة (‏5٪).
- 🧪 يعمل على CPU للفحص الذاتي (`--device auto`) — فالشيفرةُ تُختبر محلياً قبل أن تُرسل إلى المعالج الرسومي.

⛔ ولا يُحكم على الناتج بالدقّة وحدَها: بوّابةُ الحكم زوجٌ — الدقّةُ ترتفع **والاتّهامُ الكاذبُ لا يرتفع**،
والقياسُ على المحرك في `tools/tasmi_bench`.
"""
import argparse, contextlib, json, math, os, random, re, shutil, subprocess, sys, threading, time
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # ويندوز: cp1256 يسقط على الرموز (درسُ r2_put)
except Exception: pass
import numpy as np, torch, soundfile as sf
from torch.utils.data import Dataset, DataLoader
from transformers import WhisperForConditionalGeneration, WhisperProcessor

SR = 16000
MAX_SAMPLES = 30 * SR

STRIP = re.compile("[ً-ٰٟۖ-ۭـ]")

# ── 🎯 هدفُ التدريب المتطابقُ التطبيع (v3) ────────────────────────────────────────────
# ⛔ درسُ v2 (‏2026-09-11): `prep.py::target_text` كان يحوّل الخنجريّةَ ألفاً ثانية (`مُوسَىٰ`⇒«موسىا») وصلةَ ۥ/ۦ حرفاً
# (`رَبُّهُۥ`⇒«ربهو») فتعلّم النموذجُ رسماً لا يكتبه أحد، وارتفعت الإبدالاتُ على G1 44⇒68. والقاعدةُ: ما يتعلّمه النموذج
# يجب أن يساوي بعد `scorer.norm` ما يُطبَّع إليه المرجع — حرفاً بحرف (‏D-274/D-275/D-276)، مع إبقاء الحركات لأنّ
# النموذجَ الأساس يكتبها. يُتحقَّق منه بـ`--selftest-target` على المصحف كلِّه (الروايات الثلاث).
_T_DROP = re.compile("[ۖ-ۜ۞-ۤۧ-ۭـؕ-ؚ۬ٓ]")
_T_SUBS = [("ىٰ", "ى"), ("اٰ", "ا"), ("ٰ", "ا"), ("ٱ", "ا"), ("ے", "ي"), ("ۥ", ""), ("ۦ", ""),
           ("ۡ", "ْ"), ("ٖ", "ٍ"), ("ٗ", "ً"), ("ٞ", "ٌ"), ("ءَا", "آ")]
def target_from_ref(t):
    for a, b in _T_SUBS: t = t.replace(a, b)
    return " ".join(_T_DROP.sub("", t).split())
NONAR = re.compile("[^ء-ي ]")
def norm(t):
    # ⛔ **D-291:** حراسةُ D-274/275 كانت ناقصةً **في مرجع المقياس نفسِه**: `wer()` تُطبِّع
    # `ref_text` بهذه الدالّة، فكانت تقلب الخنجريةَ ألفاً بلا حراسة ⇒ المرجعُ `عَلَىٰ` يصير
    # «عليا»، وهدفُ v3 المصحَّح `عَلَى` يصير «علي» ⇒ **خطأٌ يُحاسَب عليه المتعلّمُ المصيب**.
    # قِيس على المصحف كلِّه: 6,235 كلمةً من 232,288 (‏**2.68٪ WER أرضيّةً** لمتعلّمٍ تامٍّ لهدف
    # v3) — وهدفُ v2 المعطوب يُعفى من بابها لأنّ عطبَه يطابق عطبَ المرجع. فالمقياسُ كان
    # **يكافئ الرسمَ الذي يردّه الحاكم**، ولا يصلح لترتيب v2 مقابل v3 قبل هذا السطر.
    t = STRIP.sub("", t.replace("ىٰ", "ى").replace("اٰ", "ا").replace("ٰ", "ا"))
    for a, b in [("ٱ","ا"),("أ","ا"),("إ","ا"),("آ","ا"),("ؤ","و"),("ئ","ي"),("ى","ي"),("ة","ه"),("ء",""),("ے","ي")]:
        t = t.replace(a, b)
    return " ".join(NONAR.sub("", t).split())

def wer(ref, hyp):
    r, h = norm(ref).split(), norm(hyp).split()
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)], len(r)


# ── 🔊 تسويءٌ أثناء التدريب (D-270) ────────────────────────────────────────────
# القواعد: التسويءُ **على الصوت وحدَه لا على الهدف**، وبذرةٌ مشتقّةٌ من اسم الملفّ والدورة فالتشغيلةُ
# تُعاد بالبايتات نفسِها. النسبةُ [aug_p] من الأمثلة تُسوَّأ والباقي يبقى نظيفاً كي لا يُنسى الظرفُ الحسن.

def _rng_for(path, epoch):
    import hashlib
    h = hashlib.sha256(f"{os.path.basename(path)}|{epoch}".encode()).hexdigest()
    return np.random.default_rng(int(h[:16], 16))

def _pink(n, rng):
    """ضجيجٌ ورديّ (‏1/f) بتشكيل الطيف — مرآةُ `augment.py::pink_noise` (المروحة/المكيّف في G2)."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    scale = np.ones_like(f); scale[1:] = 1.0 / np.sqrt(f[1:])
    out = np.fft.irfft(spec * scale, n)
    peak = float(np.abs(out).max()) or 1.0
    return (out / peak).astype(np.float32)

def _mix(a, n, snr_db):
    ps = float(np.mean(a.astype(np.float64) ** 2)) + 1e-12
    pn = float(np.mean(n.astype(np.float64) ** 2)) + 1e-12
    return (a + n * math.sqrt(ps / (pn * (10 ** (snr_db / 10))))).astype(np.float32)

def _fit(y, n, rng):
    """يمدّ/يقصّ تلاوةً أخرى إلى الطول n بإزاحةٍ عشوائية."""
    if len(y) == 0: return np.zeros(n, np.float32)
    y = np.tile(y, int(math.ceil((n + len(y)) / len(y))))
    off = int(rng.integers(0, max(1, len(y) - n)))
    return y[off:off + n]

def augment_wave(a, rng, get_other, no_trim=False):
    """يعيد (الصوتَ مسوَّأً، وصفَ ما فُعل) — بلا ffmpeg ولا ملفّاتِ ضجيجٍ خارجية. [get_other]() تعطي تلاوةً أخرى."""
    what = []
    kind = float(rng.random())
    if no_trim and kind >= 0.80:          # درسُ v2: البترُ مع نصٍّ كامل يعلّم إكمالَ ما لم يُسمع ⇒ يبقى المثالُ نظيفاً
        return a.astype(np.float32), "clean"
    if kind < 0.35:                       # مروحة/مكيّف عند SNR عشوائيّ (‏G2: مروحة 5/10/20)
        snr = float(rng.uniform(3.0, 18.0))
        a = _mix(a, _pink(len(a), rng), snr); what.append(f"fan{snr:.0f}")
    elif kind < 0.50:                     # ثرثرة: تلاوتان أخريان بإزاحاتٍ عشوائية (‏G2: ثرثرة 10)
        n = np.zeros(len(a), np.float32)
        for _ in range(2): n += _fit(get_other(), len(a), rng)
        n /= (float(np.abs(n).max()) or 1.0)
        snr = float(rng.uniform(6.0, 16.0))
        a = _mix(a, n, snr); what.append(f"babble{snr:.0f}")
    elif kind < 0.65:                     # خفوتٌ شديد
        db = float(rng.uniform(-40.0, -15.0))
        a = a * (10 ** (db / 20.0)); what.append(f"gain{db:.0f}")
    elif kind < 0.80:                     # هاتفٌ: نطاقٌ ضيّق بمرشّحٍ بسيط
        k = int(rng.integers(3, 10))
        a = np.convolve(a, np.ones(k, dtype=np.float32) / k, mode="same").astype(np.float32); what.append(f"lp{k}")
    else:                                 # بترُ طرفٍ (سلوكُ المتعلّم: يبدأ متأخّراً أو يقطع)
        cut = int(len(a) * float(rng.uniform(0.02, 0.10)))
        a = a[cut:] if rng.random() < 0.5 else a[:len(a) - cut]; what.append("trim")
    if float(rng.random()) < 0.35:        # قصٌّ لطيفٌ يحاكي ميكروفوناً رخيصاً
        a = np.clip(a, -0.85, 0.85); what.append("clip")
    peak = float(np.max(np.abs(a))) if len(a) else 0.0
    if peak > 1.0: a = a / peak
    return a.astype(np.float32), "+".join(what)


# ── البيانات ─────────────────────────────────────────────────────────────────
def load_wave(path):
    a, sr = sf.read(path, dtype="float32")
    if a.ndim > 1: a = a.mean(1)
    if sr != SR: raise ValueError(f"{path}: sr={sr} ≠ {SR}")
    return a[:MAX_SAMPLES]

class Clips(Dataset):
    def __init__(self, rows, tok, aug_p=0.0, epoch=0, no_trim=False):
        self.rows, self.tok, self.aug_p, self.epoch, self.no_trim = rows, tok, aug_p, epoch, no_trim
    def __len__(self): return len(self.rows)
    def __getitem__(self, i):
        r = self.rows[i]
        a = load_wave(r["path"])
        if self.aug_p > 0:
            rng = _rng_for(r["path"], self.epoch)
            if rng.random() < self.aug_p:
                a, _ = augment_wave(a, rng, lambda: load_wave(self.rows[int(rng.integers(len(self.rows)))]["path"]), self.no_trim)
        return a, self.tok(r["target_text"]).input_ids, r

def collate(batch, bos):
    ids = [b[1] for b in batch]
    if all(x[0] == bos for x in ids): ids = [x[1:] for x in ids]   # decoder_start يُضاف آلياً
    L = max(len(x) for x in ids)
    labels = torch.full((len(ids), L), -100, dtype=torch.long)
    for k, x in enumerate(ids): labels[k, :len(x)] = torch.tensor(x)
    return [b[0] for b in batch], labels, [b[2] for b in batch]

def feats(fe, waves, dev):
    """ميلُ whisper على [dev] — المسارُ نفسُه بايتاً لمسار numpy، لكن STFT على المعالج الرسومي."""
    return fe(waves, sampling_rate=SR, return_tensors="pt", device=dev).input_features.to(dev)

def autocast(dev):
    return torch.autocast("cuda", dtype=torch.float16) if dev == "cuda" else contextlib.nullcontext()


# ── الحفظُ والرفع ────────────────────────────────────────────────────────────
def save_dir(model, proc, d, state=None):
    tmp = d + ".tmp"; shutil.rmtree(tmp, ignore_errors=True)
    model.save_pretrained(tmp); proc.save_pretrained(tmp)
    if state is not None: torch.save(state, f"{tmp}/state.pt")
    shutil.rmtree(d, ignore_errors=True); os.replace(tmp, d)

class Uploader:
    """يحزم المجلّدَ (tar بلا ضغط — الأوزانُ لا تنضغط) ثم يرفعه بـPUT موقّع في خيطٍ خلفيّ كي لا يقف التدريب."""
    def __init__(self): self.t = None
    def push(self, out, name, url):
        if not url: return
        if self.t and self.t.is_alive():
            print(f"⏭ رفعُ {name} مؤجَّل: رفعٌ سابقٌ جارٍ", flush=True); return
        tar = f"{out}/{name}.tar"; t0 = time.time()
        subprocess.run(["tar", "-C", out, "-cf", tar, name], check=True)
        def run():
            r = subprocess.run(["curl", "-sS", "-f", "-X", "PUT", "-T", tar, url], capture_output=True, text=True)
            print(f"☁️ رفع {name}.tar ({os.path.getsize(tar)/1e6:.0f} م.ب) rc={r.returncode} {r.stderr[-100:].strip()} {time.time()-t0:.0f}ث", flush=True)
        self.t = threading.Thread(target=run, daemon=True); self.t.start()
    def wait(self):
        if self.t: self.t.join()


@torch.no_grad()
def evaluate(model, proc, rows, dev, gen_kw, bs=16, max_new=200):
    model.eval(); errs, tot, by = 0, 0, {}
    for i in range(0, len(rows), bs):
        chunk = rows[i:i + bs]
        x = feats(proc.feature_extractor, [load_wave(r["path"]) for r in chunk], dev)
        with autocast(dev):
            out = model.generate(x, max_new_tokens=max_new, num_beams=1, do_sample=False, **gen_kw)
        for r, h in zip(chunk, proc.batch_decode(out, skip_special_tokens=True)):
            e, n = wer(r["ref_text"], h); errs += e; tot += n
            b = by.setdefault(r["riwaya"], [0, 0]); b[0] += e; b[1] += n
    model.train()
    return errs / max(tot, 1), {k: round(v[0] / max(v[1], 1), 4) for k, v in by.items()}

def setup_generation(model, proc):
    """بطاقةُ التوليد في نموذج tarteel قديمة (بلا lang_to_id) فترفض transformers الحديثة وسيطَ language —
    تُستبدل ببطاقة whisper-tiny الأصلية (الحجم نفسه والمعجم نفسه) كما توصي HF؛ وإن تعذّر جلبُها فبالمحثّ الصريح."""
    model.config.forced_decoder_ids = None
    try:
        from transformers import GenerationConfig
        model.generation_config = GenerationConfig.from_pretrained("openai/whisper-tiny")
        model.generation_config.forced_decoder_ids = None
        model.generation_config.language, model.generation_config.task = "ar", "transcribe"
        return dict(language="ar", task="transcribe")
    except Exception as e:
        print("⚠️ بطاقةُ whisper-tiny تعذّرت:", str(e)[:120], "— أستعمل forced_decoder_ids", flush=True)
        return dict(forced_decoder_ids=proc.get_decoder_prompt_ids(language="arabic", task="transcribe"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/content/data")
    ap.add_argument("--base", default="tarteel-ai/whisper-tiny-ar-quran")
    ap.add_argument("--out", default="/content/out")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--accum", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--eval-every", type=int, default=400)
    ap.add_argument("--eval-n", type=int, default=240)
    ap.add_argument("--save-every", type=int, default=300, help="نقطةُ حفظٍ كاملة (last) كلَّ كذا خطوة")
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--upload-last", default=os.environ.get("PUT_LAST", ""), help="PUT موقّع لـlast.tar")
    ap.add_argument("--upload-best", default=os.environ.get("PUT_BEST", ""), help="PUT موقّع لـbest.tar")
    ap.add_argument("--resume", default="", help="مجلّدُ نقطةٍ سابقة؛ إن حوى state.pt استُؤنفت الخطوةُ والمحسِّن")
    ap.add_argument("--aug-p", type=float, default=0.5, help="نسبةُ الأمثلة المسوَّأة (D-270). 0 = تدريبٌ نظيفٌ كـv1 — ولا يُنصح.")
    ap.add_argument("--specaug", type=int, default=1)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--target", default="stored", choices=["stored", "norm"],
                    help="stored = target_text من المجموعة (v2) · norm = يُشتقّ من ref_text بمرآة الحاكم (v3)")
    ap.add_argument("--no-trim", action="store_true", help="بلا تسويء «البتر»: يقطع الصوتَ ويُبقي النصَّ كاملاً فيعلّم الهلوسة (درسُ v2)")
    # ⚓ D-295 (‏2026-09-12): v1·v2·v3 كلُّها تغبّش على قرّاءٍ غير مرئيين حتى نظيفاً ⇒ انجرافٌ عن الأساس (نسيانٌ كارثيّ).
    # المرساة: خسارةُ KL بين توزيع الطالب وتوزيع النموذج الأساس المجمَّد على الدفعة نفسِها (تعليمٌ قسريّ بالعناوين نفسِها)،
    # موزونةٌ بمطابقة الأساس للعنوان (‏`--anchor-by-match`: حيث يصيب الأساسُ يُثبَّت، وحيث يخطئ — ورشٌ وقالون — يتعلّم).
    ap.add_argument("--anchor-kl", type=float, default=0.0, help="وزنُ مرساة KL إلى النموذج الأساس (0 = بلا مرساة)")
    # ⚡ D-297: تجميدُ المشفّر — تسريعٌ وعلاجٌ معاً. مشفّرُ whisper يعالج 1500 إطارَ ميل في كلِّ دفعة (أثقلُ من المفكّك
    # بمراتب)، فتجميدُه يُسقط تفاضلَه؛ ومع المرساة يُحسب **مرّةً واحدة** ويُمرَّر للطالب والمعلّم معاً (وزنُهما واحدٌ حينئذٍ
    # بالضرورة) ⇒ ثلاثةُ مرورات مشفِّرٍ تصير واحداً. ⭐ وهو علاجٌ لأنّ العطبَ المقيس (D-295) نسيانٌ **صوتيّ**
    # (تغبيشُ قرّاءٍ لم يُرَوا)، وفرقُ الروايات معجميٌّ رسميّ يسكن المفكّك ⇒ يُتعلَّم ما يلزم ويُصان ما يُنسى.
    ap.add_argument("--freeze-encoder", action="store_true", help="جمّدْ مشفّرَ whisper (تسريعٌ ~3× وصونٌ للمتانة الصوتية)")
    ap.add_argument("--anchor-by-match", action="store_true", help="وزنُ المرساة لكلِّ مقطعٍ = مطابقةُ الأساس للعنوان من audit.json (1.0 إن غاب)")
    ap.add_argument("--anchor-temp", type=float, default=1.0)
    ap.add_argument("--drop-edge", type=float, default=0.0,
                    help="إسقاطُ تلوّث الحوافّ فقط (‏D-295): يُسقَط المقطعُ إن كان (miss+ins)/n ≥ هذه النسبة أو match < 0.5 — لا يمسّ إبدالاتِ الرواية")
    ap.add_argument("--min-match", type=float, default=0.0,
                    help="تصفيةُ العناوين (v4): يُسقَط كلُّ مقطعٍ تطابقُ نصِّه مع سمع النموذج المشحون دون هذه النسبة — يقرأ <data>/<part>/audit.json إن وُجد")
    ap.add_argument("--time-limit", type=float, default=0.0,
                    help="دقائقُ جدارٍ للتدريب: عند بلوغها يُحفظ last ويُرفع ويخرج بنظافةٍ (مسارُ CI بلا معالجٍ رسوميّ يستأنف نفسَه). 0 = بلا حدّ")
    args = ap.parse_args()
    random.seed(args.seed); torch.manual_seed(args.seed)
    dev = args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    if dev == "cpu":
        torch.set_num_threads(max(1, os.cpu_count() or 1))
        print(f"⚠️ بلا معالجٍ رسوميّ — {torch.get_num_threads()} خيطاً (فحصٌ ذاتيّ أو مسارُ CI البطيء)", flush=True)

    # ── البيانات: المساراتُ النسبيةُ تُحلّ على --data (المجموعةُ تُبنى على جهازٍ وتُدرَّب على آخر) ──
    rows = [json.loads(l) for l in open(f"{args.data}/manifest.jsonl", encoding="utf-8")]
    for r in rows:
        # D-293: المفتاحُ الفريدُ هو المسارُ النسبيّ (‏`g0/warsh/rid/2_255.flac`) لا اسمُ الملفّ
        r["key"] = (os.path.relpath(r["path"], args.data) if os.path.isabs(r["path"]) else r["path"]).replace(os.sep, "/")
        if not os.path.isabs(r["path"]): r["path"] = os.path.join(args.data, r["path"])
    if args.target == "norm":
        for r in rows: r["target_text"] = target_from_ref(r["ref_text"])
    else:
        # 🚨 D-291: `stored` مسارٌ **مخالفٌ للحاكم بالبناء** ولو أُصلحت حراسةُ الخنجرية في `prep`:
        # 3.28٪ من الكلمات (7,621 من 232,288) يبقى فيها الهدفُ مخالفاً لتطبيع المرجع (صلةُ ۥ/ۦ
        # حرفاً · `ءَا`)، وكان 5.96٪ قبل الإصلاح — وهو ما تعلّمه v2 فارتفعت إبدالاتُه 44⇒68.
        # يُقاس بـ`python tools/finetune/target_audit.py`. فلا يُدرَّب مرشَّحٌ جديدٌ بهذا المسار.
        print("🚨 target=stored: الهدفُ يخالف تطبيعَ الحاكم في نحوِ 3.3٪ من الكلمات (D-291/D-278) — "
              "استعمل `--target norm` لكلِّ مرشَّحٍ جديد.", flush=True)
    audit = {}
    if args.min_match > 0 or args.drop_edge > 0 or args.anchor_by_match:
        import glob as _g
        for f in _g.glob(f"{args.data}/*/audit.json"):
            for it in json.load(open(f, encoding="utf-8")).get("items", []):
                if it.get("key"): audit[it["key"]] = it
        print(f"🔎 تدقيقُ العناوين: {len(audit)} مقطعاً مدقَّقاً بالمفتاح الفريد", flush=True)
    if args.drop_edge > 0:
        before = len(rows)
        def bad_edge(r):
            it = audit.get(r["key"])
            if not it: return False
            return (it.get("miss", 0) + it.get("ins", 0)) / max(it.get("n", 1), 1) >= args.drop_edge or it.get("match", 1.0) < 0.5
        rows = [r for r in rows if not bad_edge(r)]
        print(f"🔪 إسقاطُ الحوافّ الملصوقة ((miss+ins)/n ≥ {args.drop_edge:g} أو match<0.5): {before} ⇒ {len(rows)}", flush=True)
    for r in rows:
        r["anchor_w"] = float(audit[r["key"]]["match"]) if (args.anchor_by_match and r["key"] in audit) else 1.0
    if args.min_match > 0:
        # 🔎 درسُ v1·v2·v3 (‏2026-09-11): الاتّهامُ الكاذب يرتفع في كلِّ ضبطٍ ⇒ العلّةُ في العناوين لا الوصفة. `label_audit.py`
        # يقيس تطابقَ نصِّ كلِّ مقطعٍ مع ما يسمعه النموذجُ المشحون ويكتب audit.json لكلِّ جزء؛ هنا يُسقَط ما دون العتبة.
        # 🚨 D-293: المفتاحُ كان `basename` وهو `<سورة>_<آية>.flac` — مشتركٌ بين 32 قارئاً وثلاثِ روايات،
        # و`audit.json` الأربعةُ تُدمج في قاموسٍ واحد ⇒ 23,840 مقطعاً على 6,236 مفتاحاً ممكناً على الأكثر:
        # ≥73.8٪ من المقاطع (حدُّ حمام) تُحاسَب بدرجةِ مقطعٍ آخرَ لقارئٍ آخرَ وربّما روايةٍ أخرى.
        # فالتصفيةُ لم تكن «أسقطِ الضجيج» بل «أسقطْ كلَّ نسخِ آيةٍ رَسَبت نسخةٌ منها». المفتاحُ الآن
        # `key` (المسارُ النسبيّ، فريدٌ يقيناً)، و`basename` احتياطٌ لملفّاتِ تدقيقٍ قديمةٍ بلا `key`.
        import glob as _g
        match, legacy = {}, {}
        for f in _g.glob(f"{args.data}/*/audit.json"):
            for it in json.load(open(f, encoding="utf-8")).get("items", []):
                (match if it.get("key") else legacy)[it.get("key") or it["id"]] = it["match"]
        before = len(rows)
        score = lambda r: match.get(r["key"], legacy.get(os.path.basename(r["path"]), 1.0))
        rows = [r for r in rows if score(r) >= args.min_match]
        print(f"🔎 تصفيةُ العناوين ≥ {args.min_match:g}: {before} ⇒ {len(rows)} مقطعاً "
              f"({len(match)} مدقَّقاً بالمفتاح الفريد" + (f" · ⚠ {len(legacy)} بمفتاحٍ قديمٍ ملتبس" if legacy else "") + ")", flush=True)
    missing = sum(1 for r in rows if not os.path.exists(r["path"]))
    rows = [r for r in rows if os.path.exists(r["path"])]
    random.Random(args.seed).shuffle(rows)          # ترتيبٌ ثابتٌ ⇒ المحجوزُ نفسُه في كلِّ استئناف
    held, train, per = [], [], {}
    n_riw = max(1, len({x["riwaya"] for x in rows}))
    for r in rows:
        k = r["riwaya"]
        if per.get(k, 0) < args.eval_n // n_riw: held.append(r); per[k] = per.get(k, 0) + 1
        else: train.append(r)
    hours = sum(r.get("seconds", 0) for r in train) / 3600
    print(f"train {len(train)} ({hours:.1f} h) · held {len(held)} · riwayat {per} · missing {missing} · device {dev} · target={args.target} · no_trim={args.no_trim} · frozen_enc={args.freeze_encoder}", flush=True)

    proc = WhisperProcessor.from_pretrained(args.base)
    proc.tokenizer.set_prefix_tokens(language="arabic", task="transcribe")
    model = WhisperForConditionalGeneration.from_pretrained(args.resume or args.base).to(dev)
    if args.specaug:
        c = model.config
        c.apply_spec_augment, c.mask_time_prob, c.mask_time_length, c.mask_feature_prob, c.mask_feature_length = True, 0.05, 10, 0.05, 10
    if args.freeze_encoder:
        for q in model.model.encoder.parameters(): q.requires_grad_(False)
        model.model.encoder.eval()
        n_tr = sum(q.numel() for q in model.parameters() if q.requires_grad)
        print(f"🧊 المشفّرُ مجمَّد — يُدرَّب {n_tr/1e6:.1f}م من {sum(q.numel() for q in model.parameters())/1e6:.1f}م وسيط", flush=True)
    teacher = None
    if args.anchor_kl > 0:
        teacher = WhisperForConditionalGeneration.from_pretrained(args.base).to(dev).eval()
        for q in teacher.parameters(): q.requires_grad_(False)
        print(f"⚓ مرساةُ KL إلى {args.base} · λ={args.anchor_kl:g} · T={args.anchor_temp:g} · بالمطابقة={args.anchor_by_match}", flush=True)
    gen_kw = setup_generation(model, proc)
    bos = model.config.decoder_start_token_id
    fe = proc.feature_extractor

    steps_total = args.max_steps or int(math.ceil((len(train) // args.bs) * args.epochs / args.accum))
    trainable = [q for q in model.parameters() if q.requires_grad]
    opt = torch.optim.AdamW(trainable, lr=args.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / args.warmup) * max(0.0, 1 - s / steps_total))
    scaler = torch.amp.GradScaler("cuda", enabled=(dev == "cuda"))
    os.makedirs(args.out, exist_ok=True)
    # 📜 السجلُّ يرافق نقطةَ الحفظ: عند الاستئناف على جهازٍ جديد يُستعاد من last/ فيبقى تاريخُ الجولة كلُّه في ملفٍّ واحد
    prev_log = os.path.join(args.resume, "train_log.jsonl") if args.resume else ""
    if prev_log and os.path.exists(prev_log) and not os.path.exists(f"{args.out}/train_log.jsonl"):
        shutil.copy(prev_log, f"{args.out}/train_log.jsonl")
    log = open(f"{args.out}/train_log.jsonl", "a", encoding="utf-8")
    def jlog(**kw): log.write(json.dumps(kw, ensure_ascii=False) + "\n"); log.flush()

    step, epoch, micro_in_epoch, best = 0, 0, 0, None
    state_path = os.path.join(args.resume, "state.pt") if args.resume else ""
    if state_path and os.path.exists(state_path):
        st = torch.load(state_path, map_location=dev, weights_only=False)
        opt.load_state_dict(st["opt"]); sched.load_state_dict(st["sched"])
        # 🔁 الاستئنافُ عبر الأجهزة (‏CI على CPU ⇐ كولاب على GPU): مقياسُ fp16 معطَّلٌ على CPU فيُحفظ فارغاً، وتحميلُه في
        # مقياسٍ مفعَّل يرمي «source state dict is empty» — حالتُه لا تُنقل (تُعاد تهيئتُها بأمان)، وكلُّ ما سواها يُنقل.
        if dev == "cuda" and st.get("scaler"):
            try: scaler.load_state_dict(st["scaler"])
            except Exception as e: print(f"⚠️ حالةُ المقياس لم تُنقل ({str(e)[:60]}) — تهيئةٌ جديدة", flush=True)
        step, epoch, micro_in_epoch, best = st["step"], st["epoch"], st["micro_in_epoch"], st["best"]
        print(f"🔁 استئنافٌ من الخطوة {step}/{steps_total} (الدورة {epoch}، الدفعة {micro_in_epoch}) · أفضلُ WER {best}", flush=True)
        jlog(event="resume", step=step, epoch=epoch, micro_in_epoch=micro_in_epoch, best=best)
    else:
        base_wer = evaluate(model, proc, held, dev, gen_kw)
        print("WER قبل التدريب (محجوز):", base_wer, flush=True)
        best = base_wer[0]
        jlog(event="start", base_wer=base_wer, train=len(train), held=len(held), steps=steps_total, args=vars(args))

    up = Uploader()
    def save_last():
        save_dir(model, proc, f"{args.out}/last", {"opt": opt.state_dict(), "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                                                    "step": step, "epoch": epoch, "micro_in_epoch": micro_in_epoch, "best": best})
        log.flush(); shutil.copy(f"{args.out}/train_log.jsonl", f"{args.out}/last/train_log.jsonl")
        up.push(args.out, "last", args.upload_last)

    t0, seen0, run_loss, micro, done = time.time(), step, 0.0, 0, step >= steps_total
    run_kl = 0.0
    t_wall = t0
    model.train()
    while not done:
        ds = Clips(train, proc.tokenizer, aug_p=args.aug_p, epoch=epoch, no_trim=args.no_trim)
        perm = np.random.default_rng(args.seed + epoch).permutation(len(train))
        batches = [perm[i:i + args.bs].tolist() for i in range(0, len(perm) - args.bs + 1, args.bs)][micro_in_epoch:]
        dl = DataLoader(ds, batch_sampler=batches, num_workers=args.workers, collate_fn=lambda b: collate(b, bos))
        for waves, labels, metas in dl:
            x, labels = feats(fe, waves, dev), labels.to(dev)
            with autocast(dev):
                enc = None
                if args.freeze_encoder:
                    # المشفّرُ مجمَّدٌ ⇒ مخرَجُه لا يتغيّر بالتدريب وهو **عينُه** مخرَجُ المعلّم (وزنٌ واحد) ⇒ مرورٌ واحدٌ يكفي الثلاثة.
                    with torch.no_grad():
                        enc = model.model.encoder(x)
                out = model(labels=labels, **({"encoder_outputs": enc} if enc is not None else {"input_features": x}))
                loss = out.loss
                if teacher is not None:
                    with torch.no_grad():
                        t_logits = teacher(labels=labels, **({"encoder_outputs": enc} if enc is not None else {"input_features": x})).logits
                    mask = (labels != -100).float()
                    lp = torch.log_softmax(out.logits.float() / args.anchor_temp, -1)
                    tp = torch.softmax(t_logits.float() / args.anchor_temp, -1)
                    kl_tok = (tp * (torch.log(tp.clamp_min(1e-9)) - lp)).sum(-1)                 # [B, L]
                    kl_seq = (kl_tok * mask).sum(1) / mask.sum(1).clamp(min=1.0)                   # [B]
                    w = torch.tensor([float(m.get("anchor_w", 1.0)) for m in metas], device=kl_seq.device, dtype=kl_seq.dtype)
                    kl = (kl_seq * w).sum() / w.sum().clamp(min=1e-6)
                    loss = loss + args.anchor_kl * kl
                    run_kl += float(kl.item())
                loss = loss / args.accum
            scaler.scale(loss).backward(); run_loss += loss.item(); micro += 1; micro_in_epoch += 1
            if micro % args.accum: continue
            scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True); sched.step(); step += 1
            if step % 25 == 0:
                el = time.time() - t0; rate = (step - seen0) / max(el, 1e-6); eta = (steps_total - step) / max(rate, 1e-6)
                klt = f" kl {run_kl/(25*args.accum):.4f}" if teacher is not None else ""
                print(f"step {step}/{steps_total} loss {run_loss/25:.4f}{klt} lr {sched.get_last_lr()[0]:.2e} {el:.0f}s · {rate:.2f} خطوة/ث · باقٍ ~{eta/60:.0f} د", flush=True)
                jlog(step=step, loss=run_loss / 25, kl=(run_kl / (25 * args.accum) if teacher is not None else None), epoch=epoch); run_loss = 0.0; run_kl = 0.0
            if step % args.eval_every == 0 or step >= steps_total:
                w = evaluate(model, proc, held, dev, gen_kw)
                print(f"eval step {step}: WER {w}", flush=True); jlog(step=step, wer=w)
                if w[0] <= best:
                    best = w[0]; save_dir(model, proc, f"{args.out}/best"); up.push(args.out, "best", args.upload_best)
            if step >= steps_total: done = True; break
            if step % args.save_every == 0: save_last()
            if args.time_limit and (time.time() - t_wall) / 60 >= args.time_limit:
                if step % args.save_every: save_last()
                up.wait()
                print(f"⏸ حدُّ الوقت {args.time_limit:g} د — حُفظت الخطوة {step}/{steps_total} وتُستأنف في التشغيل التالي", flush=True)
                jlog(event="paused", step=step, epoch=epoch, micro_in_epoch=micro_in_epoch, best=best); return
        if not done: epoch += 1; micro_in_epoch = 0
    save_dir(model, proc, f"{args.out}/final")
    save_last(); up.wait()
    print("DONE best WER", best, "· steps", step, flush=True); jlog(event="done", best=best, step=step)

if __name__ == "__main__":
    main()
