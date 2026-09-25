#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⚖️ الحكمُ القسريّ (teacher-forced) على المتعلّمين — البند (3-أ) من خطّة الحَكَم · **قياسٌ فقط، لا يُشحن**.

السؤال: اتحادُ الشهود الثلاثة لا يكشف إلا 29.4٪ من أخطاء المتعلّمين، لأنّ whisper يكتب أكثرَ الخطأ
صحيحاً. فهل تكشف **درجةُ النصّ المتوقَّع بتغذيةٍ قسريّة** (`forced_judge.cpp`) ما لا يكتبه التفريغ؟

الأجزاء:
1. **مولّدُ الصور** (`forms_for`) — صورٌ إملائيّةٌ مشكولةٌ للكلمة المرجعيّة كما يكتبها النموذج.
   ⛔ **مشتقٌّ من `scorer.variants` و`scorer._riwaya_forms` لا من قواعدَ مرتجلة**: كلُّ صورةٍ مرشّحة
   لا تُقبل إلا إذا كان تطبيعُها (`scorer.norm` بملفّ الرواية) **إحدى الصور التي يقبلها المسجّلُ نفسُه
   مطابقةً تامّة** للكلمة. فلا تُقاس كلمةٌ بصوتِ كلمةٍ أخرى. واختبارُ التماثل (`selftest`) يعيد الحكمَ
   بـ`scorer.score` على كلّ صورةٍ لكلّ كلمةٍ في المصحف (الروايات كلّها): **CORRECT وإلا سقط**.
2. **الترميز BPE بترتيب tiktoken**: تقطيعٌ مسبقٌ بنمط gpt2 (‏`regex`) ثمّ دمجُ الزوج الأدنى رتبةً،
   والرتبةُ = رقمُ الرمز في معجم النموذج (يُستخرج من ملفّ ggml نفسِه: `forced_judge MODEL vocab`).
   ويُفحص على مخرَج النموذج الحرّ: ترميزُنا لنصِّه يساوي رموزَه المولَّدة؟ (نسبةٌ تُكتب في النتائج).
3. **السياسات — والعتباتُ مسجّلةٌ هنا قبل رؤية أيّ نتيجة** (‏قواعدُ مئينيّة على السوالب وحدها):
   - **التأكيد** (`CONFIRM_Q`=p10): اتّهامُ SUBSTITUTED الذي درجتُه القسريّة ≥ مئين 10 للكلمات السليمة
     يُنزَّل إلى UNCERTAIN. العتبةُ من سوالب تسجيلاتٍ **أخرى** (تحقّقٌ متقاطعٌ بالتسجيل، 5 طيّات).
   - **الإنقاذ** (`RESCUE_Q`=p0.5 · استكشافيّ): كلمةٌ حكمها CORRECT ودرجتُها < مئين 0.5 للسليم ⇒ اتّهام.
   - **إعادةُ المزامنة** (`RESYNC_Q`=p0.5): تمريرةٌ ثانيةٌ بـ`--resync τ` حيث τ مئينُ 0.5 لسوالب
     التمريرة الأولى (سوالبُ فقط، لا نظرَ في الأخطاء) — علاجُ خطر الموضع +2.
4. **المسطرة**: `learner_gate.py` نفسُه (‏D-726 · D-724 · len==n_ref · حارسُ النصّ · Wilson ·
   bootstrap عنقوديٌّ بالتسجيل · McNemar · عدمُ الدونيّة).

    python forced_judge.py selftest                      # تماثلُ المولّد + BPE
    python forced_judge.py fetch --out work/learner_audio # على مشغّل GitHub (HF محجوبٌ في الجلسة)
    python forced_judge.py run --model tiny --bin bin/forced_judge --cli bin/whisper-cli --audio work/learner_audio
    python forced_judge.py analyze --raw work/fj_raw_*.json --out results/forced_judge_learners.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "finetune"))

import scorer  # noqa: E402
from detect_score import cfg_for  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

# ───────────── العتباتُ المسجّلةُ سلفاً (لا تُعدَّل بعد رؤية النتائج) ─────────────
CONFIRM_Q = 0.10     # التأكيد: ما فوق مئين 10 للسليم ⇒ SUBSTITUTED يُنزَّل إلى UNCERTAIN
RESCUE_Q = 0.005     # الإنقاذ (استكشافيّ): CORRECT تحت مئين 0.5 للسليم ⇒ اتّهام
RESYNC_Q = 0.005     # إعادةُ المزامنة: الكلمةُ السابقةُ «منخفضة» تحت مئين 0.5 لسوالب التمريرة الأولى
FOLDS = 5            # تحقّقٌ متقاطعٌ بالتسجيل
STAT = "sum"         # مجموعُ log p لرموز الكلمة (أفضلُ صورة)
MAX_FORMS = 12       # سقفُ الصور للكلمة (بعد الترشيح)
MAX_FORCED_SEC = 30  # مُرمِّزُ whisper يرى 30ث؛ ما زاد لا يُحكم قسريّاً (يبقى حكمُ الأساس)
FORCED_LANG = "ar"   # بادئةُ الحكم القسريّ: النموذجُ مدرَّبٌ على <|ar|> (كما قِيس النموذجُ الأوّليّ)

MODELS = {
    # الرابطُ والبصمةُ من WhisperModelStore.kt · ولغةُ الفكّ الحرّ = لغةُ الخدمة في WhisperDecode.SERVING
    "tiny": {"url": "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/models/whisper-tiny-ar-quran/ggml-q8_0.bin",
             "sha256": "ef01ab441b004f9e6f1ea98d397b43452b3a45efab7c3928ab37af655dde8b52", "free_lang": "en"},
    "tiny_v2": {"url": "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/models/whisper-tiny-ar-quran-v2/ggml-q8_0.bin",
                "sha256": "62f3459d6d18f58f148584b2fc122f75d98230cbc8b33a536aa897aa71756fc3", "free_lang": "en"},
    "base_q5_1": {"url": "https://github.com/mwqwf/rafiq-align-ci/releases/download/model-whisper-base-ar-quran-q51/ggml-q5_1.bin",
                  "sha256": "acc1f03c8b1468b674b4fab50e0b2312cff982ba0001cd16fe36ca23862b6536", "free_lang": "ar"},
}
HF = "https://huggingface.co/datasets/sobolev210/quran-recitation-errors"
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq forced-judge)"}
SR = 16000
ASSETS = os.path.join(ROOT, "core", "quran", "src", "main", "assets", "quran")

# ───────────────────────────── ١) مولّدُ الصور ─────────────────────────────
H = "ًٌٍَُِّْ"
SMALL = "۪ۣ۫۬"
CONS = "بتثجحخدذرزسشصضطظعغفقكلمنهي"


def _target(s: str) -> str:
    import prep  # tools/finetune/prep.py — تطبيعُ هدف التدريب (رسمٌ ⇐ إملاءُ النموذج المشكول)
    return prep.target_text(s)


def _imlai(s: str) -> str:
    s = s.replace("ءَا", "آ").replace("أٓ", "آ").replace("ءَٰا", "أَأَ").replace("ٓ", "")
    s = re.sub("ـ([َُِ])ٔ", r"ـٔ\1", s)
    s = re.sub("ْـٔ([َ])", r"ْأ\1", s)
    s = re.sub("ْـٔ([ِ])", r"ْئ\1", s)
    s = re.sub("ْـٔ([ُ])", r"ْؤ\1", s)
    s = re.sub("يْـٔ", "يْئ", s)
    s = s.replace("ـٔ", "ئ")
    s = s.replace("ۢ", "ْ").replace("ۭ", "")
    s = re.sub("ا([ًٗ])", r"\1ا", s)
    s = re.sub("وا[ْۡ]", "وا", s)
    s = re.sub("ا[ْۡ]", "ا", s)
    s = re.sub("^(.)([َُِ]?)ّ", r"\1\2", s)
    s = re.sub("^ا[" + H + SMALL + "]*ل([ذت])", r"الَّ\1", s)
    s = re.sub("^ٱل([ذت])", r"الَّ\1", s)
    return s


def _sukun(s: str) -> str:
    return re.sub("([" + CONS + "])(?=[" + CONS + "ا])", r"\1ْ", s)


def _raw_candidates(w: str, cfg) -> list:
    """مرشّحاتٌ خامٌ (قد يكون فيها ما لا يُقبل) — المرشِّحُ في `forms_for` هو الحَكَم."""
    out = []
    daggers = (lambda s: s, lambda s: s.replace("يٰ", "ا").replace("ىٰ", "ى"), lambda s: s.replace("ٰ", ""))
    for im, d, sh, wa, si, sk in itertools.product((0, 1), daggers, (0, 1), (0, 1), (0, 1), (0, 1)):
        s = _imlai(w) if im else w
        s = d(s)
        if sh:
            s = s.replace("ّ", "") if not im else re.sub("^(.)([َُِ]?)ّ", r"\1\2", s)
        if wa:
            s = re.sub("^([ٱا])[" + H + SMALL + "]+", r"\1", s)
        if si:
            s = s.replace("ۥ", "").replace("ۦ", "")
        t = _target(s)
        if sk:
            t = _sukun(t)
        out.append(t)
        if "ّ" in t and "ً" in t:
            out.append(t.replace("ّ" + "ً", "ًّ").replace("ًّ", "ّ" + "ً"))
    # صورُ الرواية (مرآةُ _riwaya_forms وبعلمها نفسِه: naql · sila): النقلُ يُسقط ألفَ الوصل وكرسيَّ الهمزة، والصلةُ تُشبع الميمَ واواً
    extra = []
    for t in out:
        m = re.match("^[ٱا][" + H + SMALL + "]*(ل.*)$", t)
        if m and cfg.naql:
            extra.append(m.group(1))
            m2 = re.match("^ل[" + H + SMALL + "]*[اأ][" + H + SMALL + "]*(.*)$", m.group(1))
            if m2:
                extra.append("ل" + m2.group(1))
        if cfg.sila and re.search("[هكت][" + H + "]*م[" + H + "]*$", t):
            b = re.sub("م[" + H + "]*$", "م", t)
            extra += [b + "ُو", b + "ُوا", b + "و"]
    return list(dict.fromkeys(out + extra))


def _verdict(word: str, cand: str, cfg) -> str:
    st = scorer.score([word], cand, cfg)["words"][0]
    return st[1] if isinstance(st, (list, tuple)) else str(st)


def forms_for(word: str, riwaya: str, cfg=None) -> list:
    """صورُ الكلمة المشكولة المقبولةُ عند المسجّل **مطابقةً تامّة** — الصورةُ القانونيّةُ أوّلاً."""
    cfg = cfg or cfg_for(riwaya)
    accepted = set(scorer._riwaya_forms(scorer.variants(word, cfg), cfg))
    canon = _target(word)
    out = []
    for c in [canon] + _raw_candidates(word, cfg):
        c = c.strip()
        if not c or " " in c or c in out:
            continue
        # القبول: تطابقٌ تامٌّ مع صور المسجّل، أو حكمُ المسجّل نفسِه CORRECT على الكلمة وحدها (قاعدةُ الخُمس
        # وحارسُ الأزواج الحرجة فيه) — فالصورةُ لا تُقبل إلا حيث يقبلها الحاكمُ المشحونُ من التفريغ.
        if scorer.norm(c, cfg) in accepted or _verdict(word, c, cfg) == "CORRECT":
            out.append(c)
    if not out and canon:
        out = [canon]  # الكلمةُ نفسُها (لا أخرى) — يُعدّ في الاختبار
    return out[:MAX_FORMS]


# ───────────────────────────── ٢) BPE بترتيب tiktoken ─────────────────────────────
GPT2_PAT = r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+"""


class BPE:
    def __init__(self, vocab_tsv: str):
        import regex
        self.pat = regex.compile(GPT2_PAT)
        self.rank = {}
        for line in open(vocab_tsv, encoding="utf-8"):
            i, h = line.rstrip("\n").split("\t")
            self.rank.setdefault(bytes.fromhex(h), int(i))

    def _piece(self, b: bytes) -> list:
        parts = [bytes([x]) for x in b]
        while len(parts) > 1:
            best, bi = None, -1
            for i in range(len(parts) - 1):
                r = self.rank.get(parts[i] + parts[i + 1])
                if r is not None and (best is None or r < best):
                    best, bi = r, i
            if bi < 0:
                break
            parts[bi:bi + 2] = [parts[bi] + parts[bi + 1]]
        return [self.rank.get(p, -1) for p in parts]

    def encode(self, text: str) -> list:
        ids = []
        for p in self.pat.findall(text):
            ids += self._piece(p.encode("utf-8"))
        return ids


# ───────────────────────────── ٣) اختبارُ التماثل ─────────────────────────────
def selftest(a) -> int:
    ok = True
    # (أ) أمثلةٌ معروفة: الصورةُ القانونيّةُ أوّلاً، وصورٌ إملائيّةٌ مقبولة
    ex = {("ءَامَنُواْ", "hafs"): "آمَنُوا", ("ذَٰلِكَ", "hafs"): "ذَلِكَ", ("عَلَيْهِمْ", "qalun"): "عَلَيْهِمُو",
          ("ٱلَّذِينَ", "hafs"): "الَّذِينَ"}
    for (w, rw), want in ex.items():
        f = forms_for(w, rw)
        hit = want in f
        ok &= hit
        print(f"{'✅' if hit else '❌'} {w} ({rw}) ⇐ {f[:6]}")
    # (ب) السلبيّ: كلمةٌ أخرى لا تدخل أبداً (حتى لو قاربت)
    for w, rw, bad in (("قَالَ", "hafs", "قُلْ"), ("ٱلْعَٰلَمِينَ", "hafs", "الْعَالِينَ"), ("كَانَ", "hafs", "كُنْ")):
        f = forms_for(w, rw)
        good = bad not in f
        ok &= good
        print(f"{'✅' if good else '❌'} {bad} ليست صورةً لـ{w}")
    # (ج) التماثلُ على المصحف كلّه: كلُّ صورةٍ يحكم لها المسجّلُ نفسُه CORRECT لكلمتها
    tot = words = bad_n = canon_out = 0
    per = {}
    for rw in a.riwayat:
        p = os.path.join(ASSETS, f"text_{rw}.jz")
        text = json.loads(zlib.decompress(open(p, "rb").read(), 47))
        cfg = cfg_for(rw)
        seen = set()
        nb = nf = 0
        for ay in text[:a.limit or None]:
            for w in ay.split():
                if w in seen:
                    continue
                seen.add(w)
                fs = forms_for(w, rw, cfg)
                if not fs:
                    continue
                words += 1
                acc = set(scorer._riwaya_forms(scorer.variants(w, cfg), cfg))
                if scorer.norm(fs[0], cfg) not in acc:
                    canon_out += 1
                for c in fs:
                    tot += 1
                    nf += 1
                    st = scorer.score([w], c, cfg)["words"][0]
                    st = st[1] if isinstance(st, (list, tuple)) else str(st)
                    if st != "CORRECT":
                        bad_n += 1
                        nb += 1
                        if nb <= 3:
                            print(f"  ❌ {rw}: {c} ⇐ {w}: {st}")
        per[rw] = {"distinct_words": len(seen), "forms": nf, "not_correct": nb}
    print(f"التماثل: {words} كلمةً فريدة · {tot} صورة · غيرُ CORRECT {bad_n} · قانونيّةٌ خارج المقبول {canon_out} · {per}")
    ok &= bad_n == 0
    # (د) BPE: وحداتٌ صغيرةٌ بمعجمٍ اصطناعيّ (الدمجُ بالرتبة لا بالطول)
    import tempfile
    fd, vp = tempfile.mkstemp()
    os.close(fd)
    with open(vp, "w", encoding="utf-8") as f:
        toks = [bytes([i]) for i in range(256)] + [b"ab", b"bc", b"abc", b" a"]
        for i, t in enumerate(toks):
            f.write(f"{i}\t{t.hex()}\n")
    bp = BPE(vp)
    os.remove(vp)
    t1 = bp.encode("abc") == [258]          # ab (256) أدنى رتبةً من bc (257) ثمّ ab+c = abc (258)
    t2 = bp.encode(" a") == [259]            # المسافةُ البادئةُ جزءٌ من القطعة
    t3 = bp.encode("a\u064eb") == [97, 0xd9, 0x8e, 98]   # الحركةُ قطعةٌ مستقلّةٌ (نمط gpt2) لا تُدمج بحرفها
    print(f"{'✅' if t1 and t2 and t3 else '❌'} BPE (دمجٌ بالرتبة · مسافةٌ بادئة · الحركةُ قطعةٌ مستقلّة)")
    ok &= t1 and t2 and t3
    if a.out:
        json.dump({"ok": bool(ok), "words": words, "forms": tot, "not_correct": bad_n, "canon_outside": canon_out,
                   "per_riwaya": per}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("selftest:", "✅" if ok else "❌")
    return 0 if ok else 1


# ───────────────────────────── ٤) جلبُ الصوت (على المشغّل) ─────────────────────────────
def _get(url: str, tries: int = 6) -> bytes:
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(min(2 * (i + 1), 12))
    raise RuntimeError(f"{url}: {last}")


def load_gold(path):
    rows = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    return [r for r in rows if r.get("type") != "meta"]


def fetch(a) -> int:
    os.makedirs(a.out, exist_ok=True)
    tree = json.loads(_get("https://huggingface.co/api/datasets/sobolev210/quran-recitation-errors/tree/main?recursive=1"))
    metas = [t["path"] for t in tree if t.get("type") == "file" and re.search(r"metadata.*\.jsonl$", t["path"])]
    print("ملفّاتُ الوصف:", metas, flush=True)
    if not metas:
        raise SystemExit("⛔ لا metadata*.jsonl في المجموعة: " + ", ".join(t["path"] for t in tree[:30]))
    paths = {}
    for m in metas:
        base = os.path.dirname(m)
        for line in _get(f"{HF}/resolve/main/{m}").decode("utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            fn = d["file_name"]
            paths.setdefault((d["recording_id"], f"{d.get('surah')}:{d.get('ayah')}"), f"{base}/{fn}" if base else fn)
    rows = [r for r in load_gold(a.gold) if r.get("audio_offset") == 0 or a.all]
    man, miss, byt = {}, [], 0
    for n, r in enumerate(rows, 1):
        p = paths.get((r["rec"], r["ref"]))
        if not p:
            miss.append(r["key"])
            continue
        dst = os.path.join(a.out, p.replace("/", "_"))
        if not (os.path.exists(dst) and os.path.getsize(dst) > 1024):
            try:
                data = _get(f"{HF}/resolve/main/{p}")
            except Exception as e:  # noqa: BLE001
                print("  ⛔", e, flush=True)
                miss.append(r["key"])
                continue
            open(dst, "wb").write(data)
        byt += os.path.getsize(dst)
        man[r["key"]] = os.path.basename(dst)
        if n % 25 == 0:
            print(f"  {n}/{len(rows)} · {byt / 1e6:.1f} م.ب", flush=True)
    json.dump({"dataset": "sobolev210/quran-recitation-errors", "license": "mit", "note": "للقياس فقط — لا يُشحن ولا يُعاد نشره",
               "items": man, "missing": miss}, open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print(f"✅ {len(man)} مقطعاً ({byt / 1e6:.1f} م.ب) · مفقود {len(miss)}")
    return 0


# ───────────────────────────── ٥) التشغيلُ لنموذجٍ واحد ─────────────────────────────
def read_audio(path: str) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True)
    return np.frombuffer(r.stdout, dtype="<f4").astype(np.float32)


def forced_pass(binp, model, items, threads, resync=None, free=None):
    cmd = [binp, model, "score", "--threads", str(threads)]
    if resync is not None:
        cmd += ["--resync", f"{resync:.4f}"]
    if free:
        cmd += ["--free", free]
    inp = "".join(it["line"] + "\n" for it in items)
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit(f"⛔ forced_judge rc={r.returncode}: {r.stderr[-400:]}")
    out = {}
    for line in r.stdout.splitlines():
        o = json.loads(line)
        out[o["id"]] = o
    return out


def run(a) -> int:
    import local_whisper as lw
    spec = MODELS[a.model]
    man = json.load(open(os.path.join(a.audio, "manifest.json"), encoding="utf-8"))["items"]
    rows = [r for r in load_gold(a.gold) if r["key"] in man]
    if a.limit:
        rows = rows[:a.limit]
    vocab = os.path.join(a.work, f"vocab_{a.model}.tsv")
    with open(vocab, "w", encoding="utf-8") as f:
        subprocess.run([a.bin, a.model_path, "vocab"], stdout=f, check=True, stderr=subprocess.DEVNULL)
    bpe = BPE(vocab)
    tr = lw.Transcriber(a.model_path, backend="cli", cli=a.cli, lang=spec["free_lang"], threads=a.threads)
    items, free, t0 = [], {}, time.time()
    long_rows = []
    for n, r in enumerate(rows, 1):
        raw = read_audio(os.path.join(a.audio, man[r["key"]]))
        h = tr.transcribe(raw)
        free[r["key"]] = h[0] if isinstance(h, tuple) else h
        x = lw.al_normalize(raw)
        if len(x) > MAX_FORCED_SEC * SR:
            long_rows.append(r["key"])
            continue
        fp = os.path.join(a.work, "f32", f"{n:04d}.f32")
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        x.astype("<f4").tofile(fp)
        cfg = cfg_for(r["riwaya"])
        slots = []
        for wi, w in enumerate(r["ref_text"].split()):
            vs = []
            for form in forms_for(w, r["riwaya"], cfg):
                vs.append(bpe.encode(" " + form))
                if wi == 0:
                    vs.append(bpe.encode(form))
            vs = [v for v in vs if v and min(v) >= 0]
            slots.append("|".join(",".join(map(str, v)) for v in dict.fromkeys(tuple(v) for v in vs)))
        items.append({"key": r["key"], "line": "\t".join([r["key"], fp, FORCED_LANG] + slots)})
        if n % 25 == 0:
            print(f"  حرٌّ {n}/{len(rows)} · {time.time() - t0:.0f}ث", flush=True)
    t1 = time.time()
    p1 = forced_pass(a.bin, a.model_path, items, a.threads, free=FORCED_LANG)
    t2 = time.time()
    # τ إعادة المزامنة: مئينُ RESYNC_Q لسوالب التمريرة الأولى (تسجيلاتٌ سليمةٌ وحدها — لا نظرَ في الأخطاء)
    neg = sorted(w[1] for r in rows if r["kind"] == "سالب" and r["key"] in p1
                 for w in (p1[r["key"]].get("w") or []) if w)
    tau = neg[min(int(RESYNC_Q * len(neg)), len(neg) - 1)] if neg else -1e9
    # ⚡ المزامنةُ لا تعمل إلا بعد كلمةٍ < τ؛ فالصفُّ الذي ليس فيه كلمةٌ كذلك نتيجتُه في التمريرة الثانية
    # مطابقةٌ للأولى بالبناء (السياقُ نفسُه والصورُ نفسُها) ⇒ لا يُعاد.
    low = [it for it in items if any(w and w[1] < tau for w in (p1.get(it["key"], {}).get("w") or []))]
    p2 = {k: v for k, v in p1.items()}
    p2.update(forced_pass(a.bin, a.model_path, low, a.threads, resync=tau) if low else {})
    t3 = time.time()
    # تماثلُ BPE: ترميزُنا لنصّ النموذج الحرّ (بادئة ar) يساوي رموزَه المولَّدة؟
    eq = tot = 0
    for o in p1.values():
        if "htok" in o and o.get("hyp", "").strip():
            tot += 1
            eq += bpe.encode(o["hyp"]) == o["htok"]
    json.dump({"model": a.model, "sha256": spec["sha256"], "free_lang": spec["free_lang"], "forced_lang": FORCED_LANG,
               "rows": len(rows), "forced_rows": len(items), "long_rows_skipped": long_rows, "resync_tau": tau, "resync_rows_rerun": len(low),
               "bpe_parity": {"equal": eq, "total": tot},
               "seconds": {"free": round(t1 - t0), "forced": round(t2 - t1), "forced_resync": round(t3 - t2)},
               "free": free, "p1": {k: v.get("w") for k, v in p1.items()}, "p2": {k: v.get("w") for k, v in p2.items()},
               "errors": {k: v["error"] for k, v in list(p1.items()) + list(p2.items()) if "error" in v}},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"✅ {a.model}: {len(rows)} صفّاً · قسريّ {len(items)} · τ_resync={tau:.3f} · BPE {eq}/{tot} · "
          f"زمن حرّ {t1 - t0:.0f}ث · قسريّ {t2 - t1:.0f}ث · مزامنة {t3 - t2:.0f}ث")
    return 0


# ───────────────────────────── ٦) التحليل ─────────────────────────────
def _q(vals, q):
    v = sorted(vals)
    return v[min(int(q * len(v)), len(v) - 1)] if v else None


def _fold(rec: str) -> int:
    return zlib.crc32(rec.encode()) % FOLDS


def _auc(pos, neg):
    if not pos or not neg:
        return None
    neg = sorted(neg)
    import bisect
    s = 0.0
    for x in pos:  # الموجبُ «أدنى» درجةً: AUC = P(pos < neg)
        lo = bisect.bisect_left(neg, x)
        hi = bisect.bisect_right(neg, x)
        s += (len(neg) - hi) + 0.5 * (hi - lo)
    return round(s / (len(pos) * len(neg)), 4)


def analyze(a) -> int:
    import learner_gate as lg
    meta_rows = load_gold(a.gold)
    lg.check_text(meta_rows)
    rows, why = lg.apply_ruler(meta_rows, {"tiny"})
    raws = {}
    for p in a.raw:
        d = json.load(open(p, encoding="utf-8"))
        raws[d["model"]] = d
    res = {"gold": os.path.basename(a.gold), "preregistered": {"CONFIRM_Q": CONFIRM_Q, "RESCUE_Q": RESCUE_Q, "RESYNC_Q": RESYNC_Q,
                                                             "FOLDS": FOLDS, "STAT": STAT, "MAX_FORMS": MAX_FORMS,
                                                             "FORCED_LANG": FORCED_LANG},
           "ruler": {"kept_rows_before_audio": len(rows), "dropped": why}, "models": {}}
    # الصفوفُ المشتركةُ بين كلّ النماذج (مقارنةٌ على عيّنةٍ واحدة)
    common = [r for r in rows if all(r["key"] in d["free"] for d in raws.values())]
    res["ruler"]["rows_with_audio_all_models"] = len(common)
    boot = lg.Boot(common, a.boot)
    res["ruler"]["recordings"] = boot.n_recordings
    rows = common
    # خطُّ الأساس المخزَّن (D-735 · HF) على الصفوف نفسِها — للمقارنة بإعادة الإنتاج
    stored = lg.verdicts(scorer, cfg_for, rows, "tiny")
    res["stored_tiny_D735"] = lg.summarize(rows, lg.arm_accusations({"t": stored}, ["t"], None), boot)
    md = [f"### ⚖️ الحكمُ القسريّ على المتعلّمين · {len(rows)} صفّاً · {boot.n_recordings} تسجيلاً (مسطرة learner_gate)",
          f"العتباتُ المسجّلةُ سلفاً: التأكيد p{CONFIRM_Q * 100:g} · الإنقاذ p{RESCUE_Q * 100:g} (استكشافيّ) · "
          f"المزامنة p{RESYNC_Q * 100:g} · تحقّقٌ متقاطعٌ {FOLDS} طيّاتٍ بالتسجيل", "",
          f"- المخزَّن tiny (D-735): اتّهام {res['stored_tiny_D735']['fa_pct']}٪ {res['stored_tiny_D735']['fa_wilson95']} · "
          f"كشف {res['stored_tiny_D735']['det_pct']}٪ ({res['stored_tiny_D735']['det']}/{res['stored_tiny_D735']['marked_words']})", ""]
    for m, d in raws.items():
        mm = {"sha256": d["sha256"], "free_lang": d["free_lang"], "forced_lang": d["forced_lang"], "resync_tau": d["resync_tau"],
              "bpe_parity": d["bpe_parity"], "seconds": d["seconds"], "long_rows_skipped": len(d["long_rows_skipped"]),
              "errors": len(d["errors"])}
        base_st = []
        for r in rows:
            st = [t[1] if isinstance(t, (list, tuple)) else str(t)
                  for t in scorer.score(r["ref_text"].split(), d["free"][r["key"]], cfg_for(r["riwaya"]))["words"]]
            base_st.append(st)

        def scores(p):
            out = []
            for r in rows:
                w = d[p].get(r["key"])
                n = len(r["ref_text"].split())
                if not w or len(w) != n:
                    out.append([None] * n)
                else:
                    out.append([x[1] if x else None for x in w])
            return out

        S = {"p1": scores("p1"), "p2": scores("p2")}
        # AUC: الكلماتُ الموسومةُ خطأً مقابل كلمات التسجيلات السليمة
        for p in ("p1", "p2"):
            neg = [s for r, ss in zip(rows, S[p]) if r["kind"] == "سالب" for s in ss if s is not None]
            pos = [s for r, ss in zip(rows, S[p]) if r["kind"] == "موجب" for j, s in enumerate(ss)
                   if s is not None and r["labels"][j] == "1"]
            # داخل الاتّهامات: الكاذبةُ (سالب) مقابل الصادقة (موسومة) — ما يستعمله «التأكيد»
            accn = [s for r, ss, bs in zip(rows, S[p], base_st) if r["kind"] == "سالب" for s, b in zip(ss, bs)
                    if s is not None and b == "SUBSTITUTED"]
            accp = [s for r, ss, bs in zip(rows, S[p], base_st) if r["kind"] == "موجب" for j, (s, b) in enumerate(zip(ss, bs))
                    if s is not None and b == "SUBSTITUTED" and r["labels"][j] == "1"]
            mm[f"auc_{p}"] = {"marked_vs_clean": _auc(pos, neg), "n_pos": len(pos), "n_neg": len(neg),
                              "within_substituted": _auc(accp, accn), "n_sub_true": len(accp), "n_sub_false": len(accn)}

        def taus(p, q):
            """عتبةٌ لكلّ طيّة من سوالب الطيّات الأخرى (+ عتبةُ العيّنة كلّها للتوثيق)."""
            per = {}
            for k in range(FOLDS):
                per[k] = _q([s for r, ss in zip(rows, S[p]) if r["kind"] == "سالب" and _fold(r["rec"]) != k
                             for s in ss if s is not None], q)
            full = _q([s for r, ss in zip(rows, S[p]) if r["kind"] == "سالب" for s in ss if s is not None], q)
            return per, full

        def policy(p, confirm, rescue):
            tc, tcf = taus(p, CONFIRM_Q)
            trs, trf = taus(p, RESCUE_Q)
            out = []
            for r, ss, bs in zip(rows, S[p], base_st):
                k = _fold(r["rec"])
                row = []
                for s, b in zip(ss, bs):
                    v = b
                    if s is not None:
                        if confirm and b == "SUBSTITUTED" and s >= tc[k]:
                            v = "UNCERTAIN"
                        if rescue and b == "CORRECT" and s < trs[k]:
                            v = "SUBSTITUTED"
                    row.append(v in lg.ACCUSE)
                out.append(row)
            return out, {"confirm_full": tcf, "rescue_full": trf}

        base_acc = [[b in lg.ACCUSE for b in bs] for bs in base_st]
        arms = {"baseline": base_acc}
        th = {}
        for p in ("p1", "p2"):
            tag = "" if p == "p1" else "+resync"
            arms["confirm" + tag], th["confirm" + tag] = policy(p, True, False)
            arms["rescue" + tag], th["rescue" + tag] = policy(p, False, True)
            arms["confirm+rescue" + tag], _ = policy(p, True, True)
        mm["thresholds_full_sample"] = th
        mm["arms"] = {k: lg.summarize(rows, v, boot) for k, v in arms.items()}
        mm["vs_baseline"] = {k: lg.paired(rows, base_acc, v, boot) for k, v in arms.items() if k != "baseline"}
        # الاتّهامُ البعيد (استكشافيّ): كلماتٌ في تسجيلٍ موجبٍ تبعد ≥2 عن كلّ كلمةٍ موسومة (ليست سوالبَ موثوقة)
        far = {}
        for k, acc in arms.items():
            n = f = 0
            for r, ac in zip(rows, acc):
                if r["kind"] != "موجب":
                    continue
                mk = [j for j, l in enumerate(r["labels"]) if l == "1"]
                for j, x in enumerate(ac):
                    if all(abs(j - q) >= 2 for q in mk):
                        n += 1
                        f += x
            far[k] = {"acc": f, "words": n, "pct": round(100 * f / n, 2) if n else None}
        mm["far_accusation_positive_rows"] = far
        # معيارُ الشحن للتأكيد (على المتعلّمين): أعلى مجال Δاتّهام ≤ 0 · الكشفُ لا يهبط أكثر من كلمتين · لا روايةَ تسوء
        for k in ("confirm", "confirm+resync"):
            v = mm["vs_baseline"][k]
            by_b, by_c = mm["arms"]["baseline"]["by_riwaya"], mm["arms"][k]["by_riwaya"]
            worse = [rw for rw in by_b if by_c[rw]["fa_pct"] > by_b[rw]["fa_pct"]]
            mm.setdefault("ship_criterion", {})[k] = {
                "fa_ci_upper_le_0": v["fa_delta_cluster95"][1] <= 0, "det_drop_le_2": v["det_delta_words"] >= -2,
                "no_riwaya_worse_fa": not worse, "pass": v["fa_delta_cluster95"][1] <= 0 and v["det_delta_words"] >= -2 and not worse}
        res["models"][m] = mm
        md += [f"#### {m} · حرٌّ `{d['free_lang']}` · قسريّ `{d['forced_lang']}` · BPE {d['bpe_parity']['equal']}/{d['bpe_parity']['total']} · "
               f"τ_resync={d['resync_tau']:.2f} · AUC (موسوم/سليم) {mm['auc_p1']['marked_vs_clean']} · داخل SUBSTITUTED {mm['auc_p1']['within_substituted']}"
               f" ({mm['auc_p1']['n_sub_true']} صادق/{mm['auc_p1']['n_sub_false']} كاذب)",
               "| الذراع | الاتّهام الكاذب | عنقودي 95٪ | الكشف | Δاتّهام [95٪] | Δكشف | McNemar اتّهام | بعيد (موجب) |", "|---|---|---|---|---|---|---|---|"]
        for k, s in mm["arms"].items():
            v = mm["vs_baseline"].get(k)
            dl = (f"{v['fa_delta_pts']:+} {v['fa_delta_cluster95']} | {v['det_delta_words']:+} | "
                  f"{v['fa_mcnemar']['a_only']}↔{v['fa_mcnemar']['b_only']} p={v['fa_mcnemar']['p']}") if v else "— | — | —"
            md.append(f"| {k} | {s['fa']}/{s['clean_words']} = {s['fa_pct']}٪ | {s['fa_cluster95']} | {s['det']}/{s['marked_words']} = {s['det_pct']}٪ "
                      f"| {dl} | {far[k]['pct']}٪ |")
        md.append("- معيارُ شحن التأكيد: " + " · ".join(f"{k} {'✅' if v['pass'] else '❌'}" for k, v in mm["ship_criterion"].items()))
        md.append("")
    md.append("⛔ قياسٌ لا شحن: «الإنقاذ» استكشافيّ ويبقى مطفأً ما لم يجتز ≤0.5٪ لكلّ رواية على g3r/g4n والحقن.")
    res["md"] = "\n".join(md)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(a.md, "w", encoding="utf-8").write(res["md"] + "\n")
    print(res["md"])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selftest")
    s.add_argument("--riwayat", nargs="*", default=["hafs", "qalun", "warsh"])
    s.add_argument("--limit", type=int, default=0, help="عددُ الآيات لكلّ رواية (0 = المصحف كلّه)")
    s.add_argument("--out")
    gold = os.path.join(HERE, "learner_gold_v1.jsonl")
    f = sub.add_parser("fetch")
    f.add_argument("--gold", default=gold)
    f.add_argument("--out", default=os.path.join(HERE, "work", "learner_audio"))
    f.add_argument("--all", action="store_true", help="كلُّ الصفوف لا audio_offset==0 وحدها")
    r = sub.add_parser("run")
    r.add_argument("--model", required=True, choices=sorted(MODELS))
    r.add_argument("--model-path", required=True)
    r.add_argument("--bin", required=True)
    r.add_argument("--cli", required=True)
    r.add_argument("--audio", required=True)
    r.add_argument("--gold", default=gold)
    r.add_argument("--work", default=os.path.join(HERE, "work", "fj"))
    r.add_argument("--threads", type=int, default=4)
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--out", required=True)
    z = sub.add_parser("analyze")
    z.add_argument("--raw", nargs="+", required=True)
    z.add_argument("--gold", default=gold)
    z.add_argument("--boot", type=int, default=2000)
    z.add_argument("--out", required=True)
    z.add_argument("--md", required=True)
    a = ap.parse_args()
    if a.cmd == "run":
        os.makedirs(a.work, exist_ok=True)
    return {"selftest": selftest, "fetch": fetch, "run": run, "analyze": analyze}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
