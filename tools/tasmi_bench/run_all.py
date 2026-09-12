# -*- coding: utf-8 -*-
"""🎛️ **مشغّلُ الجولة الكاملة** — يفرّغ ويحكم على G1 وكلِّ شروط G2 ثم يكتب صفَّ اللوحة.

هذا هو الأمرُ الواحد الذي يُشغَّل بعد كل تغييرٍ في المحرك (خارطة الطريق §نقاط التقييم الدورية):

    python tools/tasmi_bench/run_all.py --model shipped --frontend old --label "المشحون (خط الأساس)"
    python tools/tasmi_bench/run_all.py --model shipped --frontend new --label "المشحون + أمامية v2"
    python tools/tasmi_bench/run_all.py --model tuned-v1 --frontend new --label "المضبوط v1 + أمامية v2"

- **يستأنف**: أيُّ شرطٍ اكتمل ملفُّ فرضياته لا يُعاد (والتفريغ ساعاتٌ على المعالج).
- **لا يكتب رقماً لشرطٍ ناقص**: يُعلَّم بـ`—` مع عدد ما تمّ، فلا يُقارَن جزءٌ بكلّ.
- يكتب الصفَّ في `docs/qa/TASMI_SCOREBOARD.md` وملفَّ نتائجٍ خاماً في `work/board/`.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(HERE, "work")
BOARD_DIR = os.path.join(WORK, "board")
SCOREBOARD = os.path.join(ROOT, "docs", "qa", "TASMI_SCOREBOARD.md")
sys.path.insert(0, HERE)

# ترتيبُ الأعمدة في اللوحة — ثابتٌ لا يُبدَّل (وإلا اختلطت الصفوف القديمة بالجديدة).
COLUMNS = [
    ("g1", "G1"),
    ("g2:gain-20", "−20"), ("g2:gain-30", "−30"), ("g2:gain-40", "−40"),
    ("g2:noise-fan-20", "مروحة 20"), ("g2:noise-fan-10", "مروحة 10"), ("g2:noise-fan-5", "مروحة 5"),
    ("g2:noise-babble-10", "ثرثرة 10"),
    ("g2:speed-0.8", "×0.8"), ("g2:speed-1.25", "×1.25"), ("g2:speed-1.5", "×1.5"),
    ("g2:phone", "هاتف"), ("g2:clip", "قصّ"), ("g2:reverb", "صدى"), ("g2:combo-hard", "صعب"),
    # G2b — سلوكُ المتعلّم: الحقيقةُ الأرضية هي النصُّ نفسُه، فالمطلوب **ثباتُ** الدقّة لا هبوطُها
    ("g2:learner-repeat", "تكرار"), ("g2:learner-pause", "سكتة"), ("g2:learner-restart", "بداية"),
    ("g2:learner-throat", "تنحنح"), ("g2:learner-basmala", "بسملة"), ("g2:learner-combo", "متعلّم"),
    # تجربةُ كتم الضجيج (‏denoise.py) — الأعمدةُ نفسُها بعد التنقية، للمقارنة المباشرة
    ("g2:dn-g1", "نقّي/G1"), ("g2:dn-noise-fan-10", "نقّي/مروحة10"),
    ("g2:dn-noise-fan-5", "نقّي/مروحة5"), ("g2:dn-combo-hard", "نقّي/صعب"),
]


def hyps_path(model, frontend, set_name):
    tag = "g1" if set_name == "g1" else "g2-" + set_name.split(":", 1)[1]
    if model == "emu":                      # مخرَجُ `emu_sweep.py` (المحرك الحقيقي)
        return os.path.join(WORK, f"hyps_emu_{tag}.json")
    if model.startswith("emu-"):            # emu-chain · emu-gate · emu-lvl
        return os.path.join(WORK, f"hyps_emu_{tag}_{model.split('-', 1)[1]}.json")
    suffix = "" if frontend == "old" else f"_fe-{frontend}"
    return os.path.join(WORK, f"hyps_{model}_{tag}{suffix}.json")


def common_ids(model, frontend, cols):
    """⚖️ **التقاطع**: البنودُ التي نجحت في **كل** الأعمدة المعروضة.

    بدونه يُقارَن عمودٌ قِيس على 144 آية بعمودٍ قِيس على 142 (الصوتُ يصل تباعاً)، فيبدو
    فرقٌ سببُه اختلافُ العيّنة لا اختلافُ المحرك — وهذا أخبثُ ما يفسد لوحةَ نتائج.
    """
    sets = None
    for key, _ in cols:
        p = hyps_path(model, frontend, key)
        if not os.path.exists(p):
            continue
        h = json.load(open(p, encoding="utf-8")).get("hyps", {})
        ok = {k for k, v in h.items() if "error" not in v and v.get("text") is not None}
        sets = ok if sets is None else (sets & ok)
    return sets or set()


def transcribe(model, frontend, set_name, limit=0):
    """يشغّل local_whisper لشرطٍ واحد إن لم يكتمل. يعيد (منجَز، مطلوب)."""
    out = hyps_path(model, frontend, set_name)
    src = os.path.join(WORK, "wav") if set_name == "g1" else \
        os.path.join(WORK, "g2", set_name.split(":", 1)[1])
    want = len([f for f in os.listdir(src) if f.endswith(".wav")]) if os.path.isdir(src) else 0
    if limit:
        want = min(want, limit)
    have = 0
    if os.path.exists(out):
        h = json.load(open(out, encoding="utf-8")).get("hyps", {})
        have = sum(1 for v in h.values() if "error" not in v)
    if have >= want > 0:
        return have, want
    cmd = [sys.executable, os.path.join(HERE, "local_whisper.py"),
           "--set", set_name, "--model", model, "--frontend", frontend]
    if limit:
        cmd += ["--limit", str(limit)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    print(f"▶ تفريغ {set_name} ({have}/{want} منجَز)", flush=True)
    subprocess.run(cmd, env=env, cwd=HERE)
    if os.path.exists(out):
        h = json.load(open(out, encoding="utf-8")).get("hyps", {})
        have = sum(1 for v in h.values() if "error" not in v)
    return have, want


def measure(model, frontend, set_name, restrict=None):
    """يحكم على فرضيات شرطٍ ويعيد (النسبة، مجال الثقة، العدد) أو None."""
    import json as _json
    import scorer  # noqa: F401  (يُحمّل عبر score)
    import score as sc
    path = hyps_path(model, frontend, set_name)
    if not os.path.exists(path):
        return None
    hyps = _json.load(open(path, encoding="utf-8")).get("hyps", {})
    items = sc.load_sample()["items"]
    have = {i["id"] for i in items} & {k for k, v in hyps.items() if "error" not in v}
    if restrict:
        have &= restrict
    if not have:
        return None
    rows = sc.run([i for i in items if i["id"] in have], hyps, cfg="proposed")
    ok = [r for r in rows if r.get("ok")]
    if not ok:
        return None
    correct = sum(r["correct"] for r in ok)
    total = sum(r["total"] for r in ok)
    lo, hi = bootstrap(ok)
    return {"pct": 100.0 * correct / total, "lo": lo, "hi": hi, "n": len(ok),
            "words": total, "clean": sum(1 for r in ok if r["correct"] == r["total"])}


def bootstrap(rows, reps=1000, seed=7):
    """مجالُ ثقة 95٪ **عنقودي على الآيات** (كلماتُ الآية مرتبطة، فالعنقود الآية)."""
    import random
    rnd = random.Random(seed)
    n = len(rows)
    pcts = []
    for _ in range(reps):
        pick = [rows[rnd.randrange(n)] for _ in range(n)]
        t = sum(r["total"] for r in pick)
        if t:
            pcts.append(100.0 * sum(r["correct"] for r in pick) / t)
    pcts.sort()
    if not pcts:
        return 0.0, 0.0
    return pcts[int(0.025 * len(pcts))], pcts[int(0.975 * len(pcts))]


def write_row(label, model, frontend, results, commit, note=""):
    """يضيف صفّاً إلى اللوحة (وينشئ الجدول إن لم يكن)."""
    cells = []
    for key, _ in COLUMNS:
        r = results.get(key)
        cells.append("—" if not r else f"{r['pct']:.2f}")
    ts = time.strftime("%Y-%m-%d %H:%M")
    row = f"| {label} | {ts} | `{commit}` | {model} | {frontend} | " + " | ".join(cells) + " | |"
    s = io.open(SCOREBOARD, encoding="utf-8").read()
    marker = "| — | — | — | — | — |"
    lines = s.split("\n")
    out, inserted = [], False
    for ln in lines:
        if not inserted and ln.startswith("| — |") and marker in ln:
            out.append(row)
            inserted = True
            continue
        out.append(ln)
    if not inserted:                        # لا صفَّ نائبٌ ⇒ يُضاف بعد آخر صفّ جدول
        idx = max(i for i, ln in enumerate(out) if ln.startswith("|"))
        out.insert(idx + 1, row)
    io.open(SCOREBOARD, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="shipped")
    ap.add_argument("--frontend", default="old", choices=["old", "new"])
    ap.add_argument("--label", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", action="append", help="شرطٌ واحدٌ أو أكثر (مفتاحُ العمود)")
    ap.add_argument("--score-only", action="store_true", help="بلا تفريغ — حكمٌ على الموجود")
    ap.add_argument("--no-common", action="store_true",
                    help="⛔ بلا تقاطع (كلُّ عمودٍ على بنوده) — للاستكشاف فقط لا للّوحة")
    args = ap.parse_args()

    os.makedirs(BOARD_DIR, exist_ok=True)
    cols = [c for c in COLUMNS if not args.only or c[0] in args.only]
    results, coverage = {}, {}
    if not args.score_only:
        for key, _ in cols:
            have, want = transcribe(args.model, args.frontend, key, args.limit)
            coverage[key] = f"{have}/{want}"
    shared = None if args.no_common else common_ids(args.model, args.frontend, cols)
    if shared is not None:
        print(f"⚖️ التقاطع: {len(shared)} بنداً مشتركاً بين كل الأعمدة", flush=True)
    for key, name in cols:
        r = measure(args.model, args.frontend, key, restrict=shared)
        if r:
            results[key] = r
            print(f"  {name}: {r['pct']:.2f}% [{r['lo']:.2f}–{r['hi']:.2f}] "
                  f"على {r['n']} آية · نظيفةٌ تماماً {100*r['clean']/r['n']:.1f}%", flush=True)
        else:
            print(f"  {name}: — (لا فرضيات)", flush=True)

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip() or "?"
    raw = {"model": args.model, "frontend": args.frontend, "commit": commit,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "coverage": coverage,
           "commonIds": len(shared) if shared is not None else None,
           "results": {k: v for k, v in results.items()}}
    tag = f"{args.model}_{args.frontend}_{time.strftime('%m%d-%H%M')}"
    json.dump(raw, io.open(os.path.join(BOARD_DIR, f"{tag}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    if not args.only and results:
        label = args.label or f"{args.model} · {args.frontend}"
        row = write_row(label, args.model, args.frontend, results, commit)
        print("\nصفُّ اللوحة:\n" + row)
    print(f"\nالخام: {os.path.join(BOARD_DIR, tag + '.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
