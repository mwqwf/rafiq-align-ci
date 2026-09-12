#!/usr/bin/env python3
"""
🎓 تحضير مجموعة تدريب whisper على ورش/قالون (+ حفص لمنع النسيان) من فهارس التوقيت على R2.

يعمل على كولاب (أو أي لينكس فيه ffmpeg): ينزّل ملفات السور من مرآتنا العامة، يفكّها مرّةً
واحدة إلى 16ك.هز، ويقصّ الآيات ذات الثقة العالية (HIGH، بلا startApprox) بين 0.8 و28ث،
ويكتبها flac مع نصّ الرواية **بصيغة الهدف** (`target_text`: مرآة `RecitationScorer.norm`
مع إبقاء الحركات — الخنجرية ألفٌ، ٱ ألف، ے ياء، علامات الوقف والضبط تُحذف).

⛔ قرّاء الاختبار (عيّنة G1) مستبعدون من التدريب: dosary/yassin (ورش) · husary_qalun ·
قرّاء حفص في everyayah. الحكم على النموذج يكون على عيّنةٍ لم يرها.
"""
import argparse, gzip, json, os, random, subprocess, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

PUB = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"
SR = 16000
TEST_RECITERS = {"dosary", "yassin", "husary_qalun", "husary_muallim", "minshawi", "abdulbasit", "alafasy"}

# ── تطبيع الهدف (مرآة RecitationScorer.norm مع الحركات) ─────────────────────────
import re
DROP = re.compile("[ۖ-ۜ۞-ۤۧ-ۭـؕ-ؚ۬]")
# ⛔ **D-291:** حراسةُ D-274/275 قبل قلبِ الخنجرية ألفاً — حرفاً بحرف كما في `scorer.norm`
# (`عَلَىٰ` نطقُها «على» لا «علىا» · `اٰمَنَ` نطقُها «آمن» لا «اامن»). كانت ناقصةً هنا وحدَها،
# فهدفُ `--target stored` (وهو **الافتراضُ** في `train.py`) يعلّم صورةً يردُّها الحاكمُ المشحون في
# 2,212 موضعاً من المصحف (‏على · إلى · حتى · بلى · عسى …) ⇒ «غيرُ متبيَّن». ومسارُ `--target norm`
# (v3) كان قد أُصلح وحدَه في `train.target_from_ref` ⇒ هذا سدُّ البابِ الآخر لا تغييرُ سلوكِ v3.
SUBS = [("ىٰ", "ى"), ("اٰ", "ا"),
        ("ٰ", "ا"), ("ٱ", "ا"), ("ۥ", "و"), ("ۦ", "ي"), ("ے", "ي"),
        ("ۡ", "ْ"), ("ٖ", "ٍ"), ("ٗ", "ً"), ("ٞ", "ٌ"), ("ٓ", "")]  # ⚠️ ٞ في رسم المغاربة ضمّتان (وَعَادٞ = وعادٌ) — قِيس على العيّنة

def target_text(t: str) -> str:
    for a, b in SUBS:
        t = t.replace(a, b)
    t = DROP.sub("", t)
    return re.sub(r"\s+", " ", t).strip()

UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq finetune prep)"}  # r2.dev يردّ 403 على وكيل بايثون الافتراضي

def fetch(url, dst, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(dst, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            return dst
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(2 + 2 * i)

def fetch_json_gz(url):
    return json.loads(gzip.decompress(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()))

def decode16k(path):
    """mp3 → int16 mono 16k عبر ffmpeg (أنبوب، بلا ملف وسيط)."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr[-300:].decode(errors="ignore"))
    return np.frombuffer(r.stdout, dtype=np.int16)

def plan_entries(index, max_n, rng, min_s=0.8, max_s=28.0, per_surah_cap=0):
    """يختار حتى [max_n] آيةً عاليةَ الثقة.

    ⚡ **بالسورة لا بالآية (2026-09-11):** الاختيارُ العشوائيّ المحض يلمس كلَّ سورةٍ تقريباً،
    فيُنزَّل المصحفُ كلُّه لكلِّ قارئ (‏سورةُ البقرة وحدَها 40–320 م.ب) — وهذا ما جعل البناءَ
    على كولاب يموت قبل ساعة. هنا تُرتَّب السورُ عشوائياً **بوزن عدد آياتها** (فلا تُهمَل الطوالُ
    ولا تطغى)، وتؤخذ من كلٍّ حتى [per_surah_cap] آية، حتى يكتمل العدد ⇒ نحوُ عشرِ سورٍ لا 114.
    و[per_surah_cap]=0 يعيد السلوكَ القديم (خلطٌ حرّ).
    """
    ok = [e for e in index["entries"]
          if e.get("confBand") == "HIGH" and not e.get("startApprox") and not e.get("endApprox")
          and min_s * 1000 <= (e["endMs"] - e["startMs"]) <= max_s * 1000]
    if not per_surah_cap:
        rng.shuffle(ok)
        return ok[:max_n]
    by = {}
    for e in ok:
        by.setdefault(int(e["ayahId"].split(":")[0]), []).append(e)
    pool = sorted(by); w = [len(by[s]) for s in pool]; order = []
    while pool:
        i = rng.choices(range(len(pool)), weights=w)[0]
        order.append(pool.pop(i)); w.pop(i)
    out = []
    for s in order:
        es = by[s]; rng.shuffle(es)
        out += es[:per_surah_cap]
        if len(out) >= max_n: break
    return out[:max_n]

def process_reciter(riwaya, rid, texts, out, max_n, seed, log, per_surah_cap=0, rel_root=""):
    import numpy as np, soundfile as sf
    rng = random.Random(f"{seed}:{rid}")
    idx = fetch_json_gz(f"{PUB}/timings/{riwaya}/{rid}.jz")
    plan = plan_entries(idx, max_n, rng, per_surah_cap=per_surah_cap)
    by_surah = {}
    for e in plan:
        s = int(e["ayahId"].split(":")[0]); by_surah.setdefault(s, []).append(e)
    rows, tmpdir = [], f"/tmp/ft_{rid}"
    os.makedirs(tmpdir, exist_ok=True); os.makedirs(f"{out}/{riwaya}/{rid}", exist_ok=True)
    for s in sorted(by_surah):
        mp3 = f"{tmpdir}/{s:03d}.mp3"
        try:
            fetch(f"{PUB}/audio/{riwaya}/{rid}/{s:03d}.mp3", mp3)
            pcm = decode16k(mp3)
        except Exception as ex:
            log(f"⚠ {rid} {s}: {ex}"); continue
        finally:
            if os.path.exists(mp3): os.remove(mp3)
        for e in by_surah[s]:
            a, b = e["startMs"] * SR // 1000, e["endMs"] * SR // 1000
            if b > len(pcm) + SR: continue
            clip = pcm[a:min(b, len(pcm))]
            if len(clip) < SR * 0.8: continue
            gi = ayah_global(e["ayahId"])
            path = f"{out}/{riwaya}/{rid}/{e['ayahId'].replace(':', '_')}.flac"
            sf.write(path, clip, SR, subtype="PCM_16")
            # 📦 مسارٌ نسبيّ متى طُلب: المجموعةُ تُبنى على جهازٍ وتُدرَّب على آخر (‏train.py يحلّه على --data)
            rec_path = os.path.relpath(path, rel_root) if rel_root else path
            rows.append({"path": rec_path, "riwaya": riwaya, "reciter": rid, "ayahId": e["ayahId"],
                         "seconds": round(len(clip) / SR, 2), "ref_text": texts[riwaya][gi],
                         "target_text": target_text(texts[riwaya][gi])})
        log(f"{rid} surah {s}: +{len(by_surah[s])} (total {len(rows)})")
    return rows

# عدّ كوفي: مجموع الآيات لكل سورة (6236)
COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6]
OFFS = [0]
for c in COUNTS: OFFS.append(OFFS[-1] + c)
def ayah_global(ayah_id):
    s, a = map(int, ayah_id.split(":")); return OFFS[s - 1] + a - 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/content/data")
    ap.add_argument("--reciters", nargs="+", required=True, help="riwaya:id1,id2 ...")
    ap.add_argument("--max-per-reciter", type=int, default=2500)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1446)
    ap.add_argument("--text-base", default=f"{PUB}/tools-snapshots/finetune")
    ap.add_argument("--per-surah-cap", type=int, default=0, help="آياتٌ لكل سورةٍ للقارئ (0 = خلطٌ حرٌّ يلمس كلَّ السور)")
    ap.add_argument("--rel-root", default="", help="اكتب المسارات نسبيةً إلى هذا الجذر (للنقل بين الأجهزة)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    jobs = []
    for spec in args.reciters:
        rw, ids = spec.split(":"); jobs += [(rw, i) for i in ids.split(",") if i]
    bad = [j for j in jobs if j[1] in TEST_RECITERS]
    if bad: sys.exit(f"⛔ قارئ اختبار في التدريب: {bad}")
    texts = {rw: fetch_json_gz(f"{args.text_base}/text_{rw}.jz") for rw in {j[0] for j in jobs}}
    for rw, t in texts.items(): assert len(t) == 6236, rw
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)
    manifest = open(f"{args.out}/manifest.jsonl", "a", encoding="utf-8")
    done = {(json.loads(l)["reciter"]) for l in open(f"{args.out}/manifest.jsonl", encoding="utf-8")} if os.path.getsize(f"{args.out}/manifest.jsonl") else set()
    jobs = [j for j in jobs if j[1] not in done]
    failed = []
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(process_reciter, rw, rid, texts, args.out, args.max_per_reciter, args.seed, log,
                          args.per_surah_cap, args.rel_root): (rw, rid) for rw, rid in jobs}
        for f in futs:
            try:
                rows = f.result()
            except Exception as ex_:               # ⚠️ قارئٌ واحدٌ لا يُسقط المجموعة — يُسجَّل ويُتخطّى
                failed.append(futs[f]); log(f"⛔ {futs[f]}: {ex_}"); continue
            for r in rows: manifest.write(json.dumps(r, ensure_ascii=False) + "\n")
            manifest.flush(); log(f"✅ {futs[f]}: {len(rows)} clips · {sum(r['seconds'] for r in rows)/3600:.2f} h")
    manifest.close()
    rows = [json.loads(l) for l in open(f"{args.out}/manifest.jsonl", encoding="utf-8")]
    hours = sum(r["seconds"] for r in rows) / 3600
    log(f"DONE manifest rows = {len(rows)} · {hours:.2f} h · failed reciters = {failed}")

if __name__ == "__main__":
    main()
