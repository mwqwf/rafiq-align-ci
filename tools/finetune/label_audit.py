#!/usr/bin/env python3
"""🔎 **تدقيقُ عناوين التدريب** — هل يطابق نصُّ كلِّ مقطعٍ صوتَه؟ (‏2026-09-11، بعد رسوب v1·v2·v3 كلِّها في بوّابة الاتّهام)

الفرضيةُ المقيسة: مقاطعُ التدريب مقصوصةٌ من فهارس التوقيت بحوافَّ ملصوقة (`endsPolicy: contiguous`)، فقد يحمل المقطعُ ذيلَ
الآية المجاورة أو يفقد رأسَه، أو يكون التوقيتُ نفسُه مزاحاً — فيتعلّم النموذجُ «كلمةً لم تُنطق» أو «صمتاً عن كلمةٍ نُطقت»، وهذا
بعينِه الاتّهامُ الكاذب. يُقاس بالنموذج المشحون (المرجعُ الموثوق): نسبةُ تطابق كلمات الهدف مع ما يسمعه بعد التطبيع.

    python tools/finetune/label_audit.py --data /mnt/ft/data --n 600 --out audit.json [--base tarteel-ai/whisper-tiny-ar-quran]

المخرَج: توزيعُ نسب التطابق، ونسبةُ المقاطع دون 0.8 و0.9، وأسوأُ الأمثلة (نصٌّ مقابل مسموع) — ومنه يُختار مرشِّحُ v4.
"""
import argparse, json, os, random, re, sys
import numpy as np, soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tasmi_bench"))
import scorer                                   # مرآةُ الحاكم — يحرس تماثلَها اختبارُ Kotlin

STRIP = re.compile("[ً-ٰٟۖ-ۭـ]")
NONAR = re.compile("[^ء-ي ]")
def norm(t):
    t = t.replace("ىٰ", "ى").replace("اٰ", "ا").replace("ٰ", "ا")
    t = STRIP.sub("", t)
    for a, b in [("ٱ","ا"),("أ","ا"),("إ","ا"),("آ","ا"),("ؤ","و"),("ئ","ي"),("ى","ي"),("ة","ه"),("ء",""),("ے","ي")]:
        t = t.replace(a, b)
    return NONAR.sub("", t).split()

# ⛔ **D-292 — العتبةُ كانت تُصفّي مِسطرةً لا ضجيجاً.** `norm` أعلاه هو `scorer.norm` حرفاً بحرف
# (قِيس: 18,708 آيةً، صفرُ اختلاف)، لكنّه صورةٌ **واحدة**، والحاكمُ المشحون يقبل صوراً أخرى
# (`scorer.variants` + `_riwaya_forms`: خنجريّةٌ اختيارية · صلةُ ۦ/ۥ · نقلُ ورش وصلةُ ميم الجمع)
# أُضيفت **لأنّ whisper يكتبها**: `ٱلرَّحْمَٰنُ` مرجعُه الصارم «الرحمان» وwhisper يكتب «الرحمن».
# فكان القارئُ التامُّ يُحاسَب، وبنسبٍ غيرِ متساوية (D-276: حفص 11.25٪ · قالون 20.40٪ · ورش 31.33٪
# من الكلمات) ⇒ عتبةُ `--min-match` الواحدة تُسقط ورشاً وقالون لسببٍ ليس ضجيجاً فتعيد المجموعةَ
# نحوَ حفص — نقيضُ غرضِ v4. لذلك صار `match` **بصور الحاكم**، ويُحفظ `match_strict` للمقارنة.
def ref_forms(text, riwaya):
    """صورُ كلِّ كلمةٍ مرجعيّةٍ التي يقبلها الحاكم، بإعداد الرواية نفسِه الذي يقيسه اختبارُ التماثل."""
    cfg = scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=riwaya == "warsh",
                        sila=riwaya in ("warsh", "qalun"), mark_sila=True)
    out = []
    for w in text.split():
        forms = tuple(f for f in scorer._riwaya_forms(scorer.variants(w, cfg), cfg) if f)
        if forms: out.append(forms)
    return out

def align(ref, hyp):
    """(مطابَق، مفقود، مُبدَل، زائد) بمحاذاة Levenshtein على الكلمات.

    `ref` قائمةُ كلماتٍ أو قائمةُ **صورٍ مقبولة** لكلِّ كلمة (tuple) — والمطابقةُ حينئذٍ
    عضويّةٌ في الصور، وهي مطابقةُ الحاكم نفسِه (`scorer._matches` بلا رخصةِ التحريف الجزئيّ).
    """
    eq = lambda r, h: (h in r) if isinstance(r, tuple) else (r == h)
    n, m = len(ref), len(hyp)
    d = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): d[i][0] = i
    for j in range(m+1): d[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            d[i][j] = min(d[i-1][j]+1, d[i][j-1]+1, d[i-1][j-1] + (not eq(ref[i-1], hyp[j-1])))
    i, j, ok, miss, sub, ins = n, m, 0, 0, 0, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i-1][j-1] + (not eq(ref[i-1], hyp[j-1])):
            ok += eq(ref[i-1], hyp[j-1]); sub += not eq(ref[i-1], hyp[j-1]); i, j = i-1, j-1
        elif i > 0 and d[i][j] == d[i-1][j] + 1: miss += 1; i -= 1
        else: ins += 1; j -= 1
    return ok, miss, sub, ins

# ⛔ **D-293 — مفتاحُ المقطع كان اسمَ ملفِّه، واسمُ الملفِّ رقمُ آيته.** `prep.py` يكتب
# `<part>/<riwaya>/<reciter>/<سورة>_<آية>.flac` ⇒ `basename` مشتركٌ بين 32 قارئاً وثلاثِ رواياتٍ
# لا يخصُّ مقطعاً بعينِه، بينما `path` في البيان (`g0/warsh/rid/2_255.flac`) فريدٌ يقيناً.
# لذلك يُحفظ `key` (المسارُ النسبيّ) إلى جانب `id` — و`id` يبقى كما كان لأنّ `audit_rescore.py`
# يستعيد منه نصَّ الآية. ويقرأ `train.py` الـ`key` متى وُجد.
def relkey(path, data):
    return (os.path.relpath(path, data) if os.path.isabs(path) else path).replace(os.sep, "/")

def summarize(res):
    m = np.array([r["match"] for r in res])
    ms = np.array([r["match_strict"] for r in res])
    edge = sum(1 for r in res if r["ins"] > 0)
    return {"n": len(res), "mean": float(m.mean()), "median": float(np.median(m)),
            # D-292: الصورةُ الواحدة — تُحفظ لأنّ كلَّ رقمٍ سابقٍ قِيس بها (ولا تصلح لعتبةِ تصفية)
            "mean_strict": float(ms.mean()), "below_0.85_strict": float((ms < 0.85).mean()),
            "below_0.85": float((m < 0.85).mean()),
            "below_0.8": float((m < 0.8).mean()), "below_0.9": float((m < 0.9).mean()), "perfect": float((m >= 0.999).mean()),
            "with_insertions": edge / len(res), "miss_total": sum(r["miss"] for r in res), "sub_total": sum(r["sub"] for r in res),
            "ins_total": sum(r["ins"] for r in res), "words": sum(r["n"] for r in res),
            "by_riwaya": {k: float(np.mean([r["match"] for r in res if r["riwaya"] == k])) for k in sorted({r["riwaya"] for r in res})},
            "by_riwaya_strict": {k: float(np.mean([r["match_strict"] for r in res if r["riwaya"] == k])) for k in sorted({r["riwaya"] for r in res})},
            "dropped_at_0.85_by_riwaya": {k: float(np.mean([r["match"] < 0.85 for r in res if r["riwaya"] == k])) for k in sorted({r["riwaya"] for r in res})}}

def dump(res, out, partial):
    """يُكتب بذرّيّةٍ (‏tmp ثم replace) كي لا يترك القتلُ في منتصف الكتابة ملفّاً مبتوراً."""
    worst = sorted(res, key=lambda r: r["match"])[:25]
    body = {"summary": summarize(res), "worst": worst, "items": res}
    if partial: body["partial"] = True
    tmp = out + ".tmp"
    json.dump(body, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, out)
    return body["summary"]

def select_rows(rows, n, seed, shard):
    """الترتيبُ ثابتٌ بالبذرة، ثمّ `--n`، ثمّ الشريحةُ بالتخطّي (‏i::k) فتبقى الرواياتُ ممزوجةً في كلِّ شريحة."""
    rows = list(rows)
    random.Random(seed).shuffle(rows)
    if n: rows = rows[:n]              # --n 0 = المجموعةُ كلُّها (مسارُ التصفية)
    if shard:
        i, k = shard
        rows = rows[i::k]
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--n", type=int, default=600, help="عددُ المقاطع (0 = الكلّ)")
    ap.add_argument("--base", default="tarteel-ai/whisper-tiny-ar-quran")
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--seed", type=int, default=11)
    # 🧭 D-293: المعدّلُ المقيس على مشغّل GitHub ‏14.5 ث/مقطع ⇒ الجزءُ (‏~5,960 مقطعاً) نحوُ 24 ساعة.
    # فالشريحةُ (`--shard i/k`) تجعل المصفوفةَ تتّسع بلا حدٍّ، و`--resume` يلتقط ما نجا من مهلةٍ سابقة.
    ap.add_argument("--shard", default="", help="‏i/k — الشريحةُ رقم i من k (بالتخطّي بعد الخلط)")
    ap.add_argument("--resume", action="store_true", help="أكملْ من `--out` الموجود بدل إعادة المقيس")
    ap.add_argument("--ckpt", type=int, default=25, help="احفظْ كلَّ كذا دفعة (0 = لا حفظَ دوريّ)")
    ap.add_argument("--out", default="label_audit.json")
    # ⚡ D-294: مسارُ whisper-cli بالنموذج q8 المشحون نفسِه — المقيسُ على المشغّل نفسِه في tasmi-gate ≈ 1.5 ث/مقطع
    # مقابل 14.5 ث/مقطع لمسار transformers fp32 (‏D-293) ⇒ الجزءُ في ~2.5 ساعة لا 24، وهو ما يسمعه التطبيقُ فعلاً.
    ap.add_argument("--cli", default=os.environ.get("WHISPER_CLI", ""), help="مسارُ whisper-cli (يُغني عن transformers)")
    ap.add_argument("--model", default="", help="نموذجُ ggml q8 مع --cli")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    shard = None
    if a.shard:
        i, k = (int(x) for x in a.shard.split("/"))
        if not 0 <= i < k: sys.exit(f"⛔ --shard {a.shard}: يجب 0 ≤ i < k")
        shard = (i, k)
    use_cli = bool(a.cli)
    if use_cli:
        if not (os.path.exists(a.cli) and os.path.exists(a.model)): sys.exit(f"⛔ --cli/--model غيرُ موجودَين: {a.cli} · {a.model}")
        import subprocess, tempfile
        def hear(wave):
            fd, tmp = tempfile.mkstemp(suffix=".wav"); os.close(fd)
            sf.write(tmp, wave, 16000, subtype="PCM_16")
            r = subprocess.run([a.cli, "-m", a.model, "-f", tmp, "-l", "en", "-t", str(a.threads), "-bo", "1", "-bs", "1", "-nt", "-np"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")   # مرآةُ jni.c: greedy · en
            os.remove(tmp)
            if r.returncode: raise RuntimeError(f"whisper-cli rc={r.returncode}: {r.stderr[-160:]}")
            return " ".join(r.stdout.split())
    else:
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        torch.set_num_threads(os.cpu_count() or 4)
    rows = [json.loads(l) for l in open(f"{a.data}/manifest.jsonl", encoding="utf-8")]
    for r in rows:
        r["key"] = relkey(r["path"], a.data)
        if not os.path.isabs(r["path"]): r["path"] = os.path.join(a.data, r["path"])
    rows = select_rows(rows, a.n, a.seed, shard)
    done = []
    if a.resume and os.path.exists(a.out):
        done = json.load(open(a.out, encoding="utf-8")).get("items", [])
        seen = {it.get("key") for it in done if it.get("key")}
        before = len(rows)
        rows = [r for r in rows if r["key"] not in seen]
        print(f"↩️ استئناف: {len(done)} مقيسٌ سلفاً ⇒ بقي {len(rows)} من {before}", flush=True)
    if not use_cli:
        proc = WhisperProcessor.from_pretrained(a.base)
        model = WhisperForConditionalGeneration.from_pretrained(a.base).eval()
        model.config.forced_decoder_ids = None
    res = list(done)
    for i in range(0, len(rows), a.bs):
        chunk = rows[i:i+a.bs]
        waves = []
        for r in chunk:
            w, sr = sf.read(r["path"], dtype="float32")
            if w.ndim > 1: w = w.mean(1)
            waves.append(w[:30*16000])
        if use_cli:
            hyps = [hear(w) for w in waves]
        else:
            x = proc(waves, sampling_rate=16000, return_tensors="pt").input_features
            with torch.no_grad():
                ids = model.generate(x, max_new_tokens=200, num_beams=1, do_sample=False)
            hyps = proc.batch_decode(ids, skip_special_tokens=True)
        for r, h in zip(chunk, hyps):
            h = re.sub(r"<\|[^|]*\|>", " ", h)
            ref, hyp = norm(r["ref_text"]), norm(h)
            forms = ref_forms(r["ref_text"], r["riwaya"])
            ok, miss, sub, ins = align(forms, hyp)                 # D-292: بصور الحاكم
            ok_s = align(ref, hyp)[0]                              # الصورةُ الواحدة (للمقارنة)
            res.append({"id": os.path.basename(r["path"]), "key": r["key"],   # D-293: `key` وحدَه فريد
                        "riwaya": r["riwaya"], "reciter": r["reciter"], "seconds": r.get("seconds"),
                        "n": len(forms), "ok": ok, "miss": miss, "sub": sub, "ins": ins,
                        "match": ok / max(len(forms), 1), "match_strict": ok_s / max(len(ref), 1),
                        "ref": " ".join(ref), "hyp": " ".join(hyp)})
        print(f"{min(i+a.bs, len(rows))}/{len(rows)}", flush=True)
        # 💾 D-293: حفظٌ دوريّ — مهلةُ CI تقتل الخطوةَ فتتخطّى خطوةُ الرفع، فيضيع كلُّ المقيس.
        # بهذا يبقى `--out` صالحاً في كلِّ لحظة، ويكمله شوطٌ تالٍ بـ`--resume`.
        if a.ckpt and (i // a.bs + 1) % a.ckpt == 0: dump(res, a.out, partial=True)
    if not res: sys.exit("⛔ لا مقطعَ مقيسٌ (شريحةٌ فارغةٌ أو استئنافٌ مكتمل)")
    summ = dump(res, a.out, partial=False)
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    worst = sorted(res, key=lambda r: r["match"])[:25]
    for r in worst[:12]:
        print(f"  {r['match']:.2f} {r['id']} ({r['riwaya']}/{r['reciter']}, {r['seconds']}s) miss={r['miss']} sub={r['sub']} ins={r['ins']}\n     ref: {r['ref'][:90]}\n     hyp: {r['hyp'][:90]}")

if __name__ == "__main__":
    main()
