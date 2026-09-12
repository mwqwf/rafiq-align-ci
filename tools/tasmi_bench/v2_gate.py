# -*- coding: utf-8 -*-
"""⚖️ **بوّابةُ `tuned-v2` على المحرك الحقيقي** — الشرطُ زوجٌ لا رقم: الدقّةُ ترتفع **والاتّهامُ الكاذبُ لا يرتفع**.

    python tools/tasmi_bench/v2_gate.py                 # يجلب q8 من R2، يدفعه للمحاكي، يقيس الذراعين مجموعةً مجموعة، ويطبع الجدول
    python tools/tasmi_bench/v2_gate.py --score-only    # الجدولُ ممّا قِيس حتى الآن (بلا محاكٍ)
    python tools/tasmi_bench/v2_gate.py --arm v2 --sets g1 g2:noise-fan-5

المبادئ المدفوعة الثمن (اللوحة D-264…D-271):
- **الذراعان على البنود عينِها** (تقاطعُ المعرّفات) وبالإعداد نفسِه: `--chain cap` (البوّابةُ + سقفُ 10ث) والدفعةُ 12.
- **المحركُ لا مرآتُه**: كلُّ رقمٍ هنا من `whisperBatch` على المحاكي (‏whisper.cpp q8 عبر JNI). والحكمُ (الاتّهام) بمرآة الحاكم
  البايثونية المتماثلة مع `RecitationScorer` (‏حزمةُ التماثل) — وهي التي تقيس حارسَ الانهيار (0.60) ونطاقَ الشكّ.
- **الاتّهامُ الكاذب** في g3r = `MISSED`+`SUBSTITUTED` خارج نطاق الحقن ±1، مع تخطّي الآيات التي تجاوز اتّهامُها 0.60 (يكبحها الحارس).
- سائقٌ واحدٌ للمحاكي: يُنتظَر قفلُ `emu_sweep` إن كان سائقٌ آخر حيّاً. و`emu_sweep` يستأنف الملفَّ الناقص بنفسه.
- الترتيبُ بالحسم: g3r ضجيجاً (أخطرُ رقمٍ في اللوحة) ثم الضجيجُ الشديد ثم النظيف ثم g3r نظيفاً ثم سلوكُ المتعلّم.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work")
sys.path.insert(0, HERE)
import score  # noqa: E402
import scorer  # noqa: E402
import detect_score as D  # noqa: E402
import emu_sweep as E  # noqa: E402

PUB = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq v2 gate)"}   # r2.dev يردّ 403 على الوكيل الافتراضي
ARMS = {
    "shipped": ("/data/local/tmp/q8_shipped.bin", f"{PUB}/models/whisper-tiny-ar-quran/ggml-q8_0.bin", os.path.join(WORK, "q8_shipped.bin")),
}
def arm_of(name):
    """أيُّ مرشَّحٍ `vN` يُشتقّ آلياً: `finetune/out_vN/ggml-q8_0.bin` على R2 ⇒ `/data/local/tmp/q8_vN.bin` على الجهاز."""
    if name not in ARMS:
        ARMS[name] = (f"/data/local/tmp/q8_{name}.bin", f"{PUB}/finetune/out_{name}/ggml-q8_0.bin", os.path.join(WORK, f"q8_{name}.bin"))
    return ARMS[name]
ACC_SETS = ("g1", "g2:noise-fan-5", "g2:learner-combo")
G3R_SETS = ("g3r:noisy", "g3r:clean")
def plan_for(cand):
    return [("g3r:noisy", cand), ("g3r:noisy", "shipped"), ("g2:noise-fan-5", cand), ("g1", cand),
            ("g3r:clean", cand), ("g3r:clean", "shipped"), ("g2:learner-combo", cand),
            ("g1", "shipped"), ("g2:noise-fan-5", "shipped"), ("g2:learner-combo", "shipped")]
CONF = {scorer.MISSED, scorer.SUBSTITUTED}
COLLAPSE = 0.60
CMP = ("shipped", "v2")     # الذراعان المقارَنان (‏--arms)
PATTERN = ""                # نمطُ ملفّات الفرضيات بدل المحاكي (‏--pattern "work/hyps_{arm}_{tag}_gate_cap10.json")


def out_file(set_name, arm):
    if PATTERN:
        return os.path.join(HERE, PATTERN.format(arm=arm, tag=E.tag_of(set_name)))
    return os.path.join(WORK, f"hyps_emu_{E.tag_of(set_name)}_cap_{arm}.json")


def ids_for(set_name):
    d = E.local_dir(set_name)
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".wav")) if os.path.isdir(d) else []


def load_hyps(set_name, arm):
    p = out_file(set_name, arm)
    if not os.path.exists(p):
        return {}
    h = json.load(open(p, encoding="utf-8")).get("hyps", {})
    return {k: v for k, v in h.items() if v.get("text") is not None and "error" not in v}


def complete(set_name, arm):
    ids = ids_for(set_name)
    return bool(ids) and all(i in load_hyps(set_name, arm) for i in ids)


def adb(*args):
    return E.sh([E.ADB, "-s", E.SERIAL] + list(args))


def ensure_model(arm):
    dev, url, local = arm_of(arm)
    r = adb("shell", "ls", "-l", dev)
    if r.returncode == 0 and "No such file" not in r.stdout + r.stderr:
        print(f"📱 {arm}: {dev} موجودٌ على الجهاز — {r.stdout.strip()[-60:]}")
        return
    if not os.path.exists(local):
        print(f"⬇️ {arm}: {url}")
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(local + ".part", "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        os.replace(local + ".part", local)
    print(f"📲 {arm}: دفعُ {os.path.getsize(local)/1e6:.1f} م.ب إلى {dev}")
    r = adb("push", local, dev)
    if r.returncode:
        raise SystemExit(f"⛔ adb push: {r.stderr[-200:]}")
    adb("shell", "chmod", "644", dev)


def pid_alive(pid):
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        return str(pid) in r.stdout
    except Exception:
        return True


def wait_lock():
    while os.path.exists(E.LOCK):
        try:
            pid = int(open(E.LOCK, encoding="utf-8").read().strip())
        except Exception:
            pid = 0
        age = time.time() - os.path.getmtime(E.LOCK)
        if not pid_alive(pid) or age > 3600:
            print(f"🔓 القفلُ يتيم (pid {pid}، منذ {age/60:.0f} د) — يُزال")
            os.remove(E.LOCK)
            return
        print(f"⏳ سائقٌ آخر على المحاكي (pid {pid}، منذ {age/60:.0f} د) — أنتظر", flush=True)
        time.sleep(60)


def run_arm(set_name, arm, tries=3):
    for t in range(tries):
        if complete(set_name, arm):
            return True
        wait_lock()
        ensure_model(arm)
        cmd = [sys.executable, os.path.join(HERE, "emu_sweep.py"), "--set", set_name, "--chain", "cap", "--chunk", "12",
               "--tag", arm, "--model-path", arm_of(arm)[0]]
        print(f"▶ [{t+1}/{tries}] {' '.join(cmd[2:])}", flush=True)
        subprocess.run(cmd, env=dict(os.environ, PYTHONIOENCODING="utf-8", MSYS_NO_PATHCONV="1"))
        time.sleep(5)
    return complete(set_name, arm)


# ── القياس ────────────────────────────────────────────────────────────────────
def _boot_diff(pairs, seed=7, boot=2000):
    """[pairs] = [(a_correct, a_total, b_correct, b_total)] بالآية — bootstrap عنقوديّ مزدوج على فرق النسب."""
    if not pairs:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    diffs = []
    for _ in range(boot):
        pick = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
        ta = sum(p[1] for p in pick) or 1
        tb = sum(p[3] for p in pick) or 1
        diffs.append(sum(p[2] for p in pick) / tb - sum(p[0] for p in pick) / ta)
    diffs.sort()
    return (diffs[int(0.025 * boot)], diffs[int(0.975 * boot) - 1], sum(1 for d in diffs if d > 0) / boot)


def pool_items():
    """بنودُ المرجع كلُّها: عيّنةُ الآية الواحدة (202) **مع** خطّة التلاوة الطويلة (60).

    ⛔ **ثغرةٌ مقيسة (‏2026-09-12):** `score_accuracy` كانت تقرأ `sample.json` وحدَها (202 بنداً بلا بندٍ
    طويلٍ واحد) ⇒ كلُّ مجموعةٍ من `g4*` تُعطي `common ∩ sample = ∅` فترجع الدالّةُ **None صامتةً**،
    فلا رقمَ ولا شكوى. وموضعُ شحن `guardScope=FINAL` هو **التلاوةُ الطويلة** بعينها ⇒ كنّا نقرّر في
    منطقةٍ لا تقيسها بوّابتُنا. و`long_plan.json` يحمل `refText` و`riwaya` فيصلح لـ`score.run` كما هو.
    """
    items = list(score.load_sample()["items"])
    lp = os.path.join(WORK, "long_plan.json")
    if os.path.exists(lp):
        items += json.load(open(lp, encoding="utf-8"))["items"]
    return items


def score_accuracy(set_name, arms=None):
    arms = arms or CMP
    ha, hb = load_hyps(set_name, arms[0]), load_hyps(set_name, arms[1])
    common = set(ha) & set(hb)
    if not common:
        return None
    mis = os.path.join(WORK, "misaligned.json")
    exclude = {m["id"] for m in json.load(open(mis, encoding="utf-8"))["items"]} if os.path.exists(mis) else set()
    items = [it for it in pool_items() if it["id"] in common and it["id"] not in exclude]
    if not items:
        # ⛔ لا صمتَ عند الصفر: بنودٌ موجودةٌ في الذراعَين ولا مرجعَ لها ⇒ عطبُ مرجعٍ لا «لا فرق».
        raise SystemExit(f"⛔ {set_name}: {len(common)} بنداً في الذراعَين ولا واحدَ منها في المرجع "
                         f"(`sample.json` + `long_plan.json`) ⇒ لا رقمَ يُحتسب. مثال: {sorted(common)[0]}")
    ra, rb = score.run(items, ha, "proposed"), score.run(items, hb, "proposed")
    aa, ab = score.aggregate(ra), score.aggregate(rb)
    pairs = [(x["correct"], x["total"], y["correct"], y["total"]) for x, y in zip(ra, rb) if x["ok"] and y["ok"]]
    lo, hi, p = _boot_diff(pairs)
    by = {k: (score.by_key(ra, "riwaya").get(k, {}).get("accuracy", 0), score.by_key(rb, "riwaya").get(k, {}).get("accuracy", 0))
          for k in sorted({it["riwaya"] for it in items})}
    return {"set": set_name, "n": len(items), "acc": (aa["accuracy"], ab["accuracy"]), "diff": ab["accuracy"] - aa["accuracy"],
            "ci": (lo, hi), "p_gain": p, "perfect": (aa["perfectRate"], ab["perfectRate"]), "by_riwaya": by}


def judge_arm(plan, hyps):
    """(كشف، اتّهامٌ كاذب، ن، أزواجُ الآيات) بالطريقة المعتمدة (‏CLOUD_DUTY_PROMPT §T=2)."""
    j = D.judge(plan, hyps)
    det = n = 0
    per = {}
    for it in plan:
        s = j.get(it["id"])
        if not s:
            continue
        n += 1
        ws = s["words"]
        if sum(1 for w in ws if w[1] in CONF) / max(len(ws), 1) > COLLAPSE:
            per[it["id"]] = (0, 0, 0)          # يكبحه الحارس: لا اتّهامَ ولا كشف
            continue
        d = 1 if any(w[1] in CONF for w in ws if abs(w[0] - it["wordIndex"]) <= 1) else 0
        o = [w for w in ws if abs(w[0] - it["wordIndex"]) > 1]
        fa, tot = sum(1 for w in o if w[1] in CONF), len(o)
        det += d
        per[it["id"]] = (fa, tot, d)
    fa = sum(v[0] for v in per.values())
    tot = sum(v[1] for v in per.values())
    return det / max(n, 1), fa / max(tot, 1), n, per


def score_g3r(set_name, arms=None):
    arms = arms or CMP
    ha, hb = load_hyps(set_name, arms[0]), load_hyps(set_name, arms[1])
    common = set(ha) & set(hb)
    if not common:
        return None
    plan = [it for it in json.load(open(os.path.join(HERE, "inject_plan_riwaya.json"), encoding="utf-8"))["items"] if it["id"] in common]
    da, fa_a, n, pa = judge_arm(plan, ha)
    db, fa_b, _, pb = judge_arm(plan, hb)
    pairs = [(pa[i][0], pa[i][1], pb[i][0], pb[i][1]) for i in pa if i in pb]
    lo, hi, p = _boot_diff(pairs)
    by = {}
    for riw in sorted({it["riwaya"] for it in plan if "riwaya" in it}):
        sub = [it for it in plan if it.get("riwaya") == riw]
        by[riw] = (judge_arm(sub, ha)[1], judge_arm(sub, hb)[1])
    return {"set": set_name, "n": n, "detect": (da, db), "fa": (fa_a, fa_b), "fa_diff": fa_b - fa_a, "ci": (lo, hi),
            "p_fa_up": p, "by_riwaya": by}


def table():
    rows = []
    a, b = CMP
    where = "مرآةُ المحرك (whisper-cli q8 + الواجهة الأمامية بايثونياً)" if PATTERN else "المحرك (المحاكي، `--chain cap`، دفعة 12)"
    print(f"\n## ⚖️ بوّابةُ {b} على {where} — الذراعان على البنود عينِها\n")
    print(f"| المجموعة | ن | {a} | **{b}** | الفرق [95٪] | احتمالُ الارتفاع | بالرواية ({a} ⇐ {b}) |")
    print("|---|---:|---:|---:|---|---:|---|")
    for s in ACC_SETS:
        r = score_accuracy(s)
        if not r:
            print(f"| {s} · تتبّع | — | ⏳ | ⏳ | | | |")
            continue
        rows.append(r)
        riw = " · ".join(f"{k} {a*100:.1f}⇐{b*100:.1f}" for k, (a, b) in r["by_riwaya"].items())
        print(f"| {s} · تتبّع | {r['n']} | {r['acc'][0]*100:.2f}٪ | **{r['acc'][1]*100:.2f}٪** | "
              f"{r['diff']*100:+.2f} [{r['ci'][0]*100:+.2f}..{r['ci'][1]*100:+.2f}] | {r['p_gain']*100:.0f}٪ | {riw} |")
    for s in G3R_SETS:
        r = score_g3r(s)
        if not r:
            print(f"| {s} · اتّهامٌ كاذب | — | ⏳ | ⏳ | | | |")
            continue
        rows.append(r)
        riw = " · ".join(f"{k} {a*100:.1f}⇐{b*100:.1f}" for k, (a, b) in r["by_riwaya"].items())
        print(f"| {s} · اتّهامٌ كاذب | {r['n']} | {r['fa'][0]*100:.2f}٪ | **{r['fa'][1]*100:.2f}٪** | "
              f"{r['fa_diff']*100:+.2f} [{r['ci'][0]*100:+.2f}..{r['ci'][1]*100:+.2f}] | {r['p_fa_up']*100:.0f}٪ | {riw} |")
        print(f"| {s} · كشف | {r['n']} | {r['detect'][0]*100:.1f}٪ | **{r['detect'][1]*100:.1f}٪** | "
              f"{(r['detect'][1]-r['detect'][0])*100:+.1f} | | |")
    json.dump(rows, open(os.path.join(WORK, f"{b}_gate_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n⛔ الحكمُ زوجٌ: يُقبل {b} إن ارتفعت الدقّةُ **ولم يرتفع** الاتّهامُ الكاذب (الحدُّ الأعلى لمجال الفرق ≤ 0). "
          "ولا يُحكم بعيّنةٍ جزئية.")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--arm", help="ذراعٌ واحدة فقط (shipped · v2 · v3 …)")
    ap.add_argument("--cand", default="v2", help="المرشَّحُ المقارَن بالمشحون على المحاكي (v2 · v3 …)")
    ap.add_argument("--sets", nargs="*")
    ap.add_argument("--arms", nargs=2, metavar=("A", "B"), help="الذراعان المقارَنان (افتراضاً shipped v2)")
    ap.add_argument("--pattern", default="", help='ملفّاتٌ جاهزة بدل المحاكي، مثل "work/hyps_{arm}_{tag}_gate_cap10.json" (يستلزم --score-only)')
    ap.add_argument("--md", help="اكتب الجدولَ أيضاً إلى هذا الملفّ (لملخّص CI)")
    a = ap.parse_args()
    global CMP, PATTERN
    CMP = ("shipped", a.cand)
    if a.arms: CMP = tuple(a.arms)
    if a.pattern: PATTERN, a.score_only = a.pattern, True
    if not a.score_only:
        plan = [(s, arm) for s, arm in plan_for(a.cand) if (not a.arm or arm == a.arm) and (not a.sets or s in a.sets)]
        for s, arm in plan:
            if complete(s, arm):
                print(f"✅ {s} · {arm}: مكتمل ({len(ids_for(s))})")
                continue
            t0 = time.time()
            ok = run_arm(s, arm)
            print(f"{'✅' if ok else '⚠️ ناقص'} {s} · {arm} في {(time.time()-t0)/60:.0f} د", flush=True)
            table()
    if a.md:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            table()
        open(a.md, "w", encoding="utf-8").write(buf.getvalue()); print(buf.getvalue())
    else:
        table()


if __name__ == "__main__":
    main()
