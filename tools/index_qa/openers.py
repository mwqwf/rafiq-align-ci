#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعادةُ قياسِ مطالعِ السور بقطعٍ متدرّج — **لا بنافذةٍ واحدة**.

    python tools/index_qa/openers.py timings/qalun/tareq_qalun.jz
    python tools/index_qa/openers.py --state          # كل ما برّأه محرّك الخادم

**سببُ وجودها (درسٌ مقيسٌ 2026-09-02):** برّأتُ ‏`tareq_qalun` 88:1 لأن تفريغ
الخادم لنافذةٍ من الصفر قال «هَلْ أَتَاكَى» بلا بسملة. وعلى **البصمة نفسها**
(‏sha256 المصدر = sha256 المرآة = e438ace9… متطابقان بايتاً) قال المحرّك المحلي
«بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ هَلْ أَتَاكَ». والقطعُ المتدرّج حسم:
1.5ث «بسم الله» · 3ث «بسم الله الرحمن الرحيم» · 6ث «… هل أتاكر».

⇒ **«لم أسمع شيئاً» ليست شهادةَ غياب.** المحرّك يُسقط صدرَ النافذة بلا أثر،
كما تُسقطه النافذةُ الطويلة. وإثباتُ غيابِ البسملة لا يصحّ إلا بسُلَّمٍ يرى
النموّ: إن كبر النصّ مع كبر النافذة من الصفر فالصوت هناك.

**القاعدة المطبَّقة هنا:** المطلع مُدانٌ إن ظهرت بسملةٌ في أيّ درجةٍ من السُّلَّم
داخل حدود المدخل؛ ومبرَّأٌ إن **لم تظهر في أيّ درجة** (لا في درجةٍ واحدة).
⛔ ولا يبرَّأ بدرجةٍ واحدة أبداً — وهذا الملفُّ كلُّه ثمنُ تلك الغلطة.
"""
from __future__ import annotations
import argparse, difflib, json, os, sys, glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run as R                                       # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except Exception: pass

class _Lock:
    """قفلٌ يمنع نسختين من الكتابة إلى المخرَج نفسه.

    ⛔ درسٌ بثمنه (2026-09-02): أوقفتُ مسحاً معطوباً بـ`TaskStop` فقتل الصَّدَفة
    **ولم يقتل عمليةَ ويندوز**، فبقيت النسخةُ المعطوبة تعمل 14 دقيقة إلى جانب
    النسخة المصحَّحة وكلتاهما تكتب إلى `openers_restate.log`. ونظيرُه وقع عند
    8e بثلاث نسخ (‏`pkill` من Git Bash لا يقتل عمليات ويندوز أيضاً) فكاد
    يُخرج حصيلةً نصفُها من أداةٍ معطوبة. ⇒ **لا يُوثق بأن نسخةً واحدة تعمل؛
    المخرَجُ يحمل قفلَه.** والتحقّق من القتل بـ`Get-CimInstance` لا بالظنّ.
    """
    def __init__(self, path):
        self.p = Path(path)

    def acquire(self):
        if self.p.exists():
            try:
                pid = int(self.p.read_text())
            except Exception:
                pid = -1
            import subprocess
            alive = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Id {pid} -EA SilentlyContinue) -ne $null"],
                capture_output=True, text=True).stdout.strip().lower()
            if alive.startswith("true"):
                sys.exit(f"⛔ نسخةٌ أخرى تعمل (PID {pid}) — لا تشغّل ثانيةً على المخرَج نفسه.")
        self.p.write_text(str(os.getpid()))

    def release(self):
        try:
            self.p.unlink()
        except Exception:
            pass


# ترتيبُ الطابور — **بالمشحون لا بترتيب الفهرسة** (بأمر البوابة github-bd،
# وسببُه قياس): كلُّ هؤلاء أحياءٌ في `timings/manifest.json`، فالخطر ليس
# ترقيةً قادمة بل **ما يسمعه الحافظ الآن**. ⇒ الكاملاتُ المشحونة أولاً.
PRIORITY = ("husary_warsh", "a_majed", "hawashi", "koshi_warsh",
            "sneineh_qalun", "a_maasaraawi", "qazabri")

# ⏸️ مؤجَّلاتٌ عمداً: على قائمة إعادة بناء الجيل الأول
# (`tools/ci_fleet/reciters_gen1_redo.tsv`) ⇒ **قياسُها الآن قياسُ ما سيزول**،
# ويُقاس المُعادُ ببصمته الجديدة لا يُورَّث عنه حكم. اكتُشف الخطأ بعد أن أنفق
# المسحُ عشرين دقيقة على `3siri` (منها) والمشحونُ الكامل ينتظر.
DEFER = ("a_klb", "soufi_sousi", "kshidan_qalun", "a_alemadi", "a_alhazmi",
         "abkar", "a_alqrafi", "a_alshahhat", "3siri", "a_ahmed")


def _rank(key):
    for i, n in enumerate(PRIORITY):
        if n in key:
            return (0, i)
    return (2, 0) if any(n in key for n in DEFER) else (1, 0)


LADDER = (1500, 2000, 2500, 3000, 4000, 6000)   # درجاتُ السُّلَّم بالملّي
BASMALA = R.skel("بسم الله الرحمن الرحيم")

def _has_basmala(t):
    """أفي صدرِ التفريغ بسملةٌ — بالمقارن **المتسامح** نفسه الذي يحكم به `run.py`.

    ⛔ عيبٌ وقعتُ فيه ثم كشفه نظيرُه عند 8e (2026-09-02): كان الكشف هنا
    ببادئةٍ **صارمة** (`startswith`) بينما بقيّةُ الأداة تقارن بمجموع الكتل.
    فاختبرتُه على تفريغاتٍ حقيقية ففاته ثلاثةٌ من أربع: «بسم الله الرحمن
    **اقحيم**» و«**واسم** الله الرحمن اقحيم» و«**قل** اسم الله الرحمن الرحيم»
    — بسملاتٌ تامّة يُخطئ النموذجُ حرفاً أو حرفين في أوّلها أو آخرها فتمرّ
    **بريئة**. ⇒ مقارنان في أداةٍ واحدة عيبٌ بذاته: المقارنُ واحدٌ أو لا يكون.
    """
    hs = R.skel(t)
    if not hs:
        return False
    pref = hs[:len(BASMALA) + 8]          # الصدر وحده — لا وسطُ النصّ
    span = min(len(BASMALA), len(pref))
    sm = difflib.SequenceMatcher(None, BASMALA, pref, autojunk=False)
    # كتلةُ 3 تُحتسب هنا خلافاً لـ`run.py`: «حيم» من «الرحيم» شاهدٌ معتبَر على
    # البسملة لتميّزها، وإسقاطُها أضاع «واسم الله الرحمن اقحيم» بفارق 0.3.
    hit = sum(b.size for b in sm.get_matching_blocks() if b.size >= 3)
    # أرضيةٌ مطلقة مع النسبة: تفريغٌ من ثلاثة أحرف («الر» مطلعُ يونس وهود
    # ويوسف) يجعل `span` ثلاثةً فيكفيه تداخلُ «الر» مع «الرحمن» ليُدان
    # بسملةً كاذبة. و«بسم الله» وحدها سبعةُ أحرفٍ ⇒ الأرضية سبعة.
    return hit >= max(0.6 * span, 7)


def check(key, only=None):
    idx, sha = R.fetch_index(key)
    E = {e["ayahId"]: e for e in idx["entries"]}
    out = []
    for s in range(1, 115):
        if s in (1, 9) or (only and s not in only): continue
        e = E.get(f"{s}:1")
        if not e: continue
        st, en = e["startMs"], e["endMs"]
        jobs = [{"id": f"{s}@{d}", "url": e["fileRef"], "startMs": st,
                 "endMs": min(st + d, en)} for d in LADDER if st + d <= en + 1500]
        if not jobs: continue
        res, _ = R.local_run(jobs)
        rungs = [(int(k.split("@")[1]), res[k]["text"]) for k in res]
        rungs.sort()
        hit = next(((d, t) for d, t in rungs if _has_basmala(t)), None)
        out.append({"surah": s, "startMs": st, "sha256": sha,
                    "verdict": "بسملة مبتلعة" if hit else "بُرِّئ بالسُّلَّم",
                    "at": hit[0] if hit else None,
                    "ladder": [{"ms": d, "heard": t[:60]} for d, t in rungs]})
    return out

def main():
    ap = argparse.ArgumentParser(description="قياس المطالع بقطعٍ متدرّج")
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--state", action="store_true",
                    help="أعد قياس كل مطلعٍ برّأه محرّك الخادم في state/")
    ap.add_argument("--surah", type=int, action="append")
    a = ap.parse_args()

    lock = _Lock(Path(__file__).parent / '.openers.lock')
    targets = {}
    if a.state:
        CUT = 1788345000                       # حدُّ الانتقال إلى المحرّك المحلي
        for p in glob.glob(str(Path(__file__).parent / "state" / "*.json")):
            r = json.loads(Path(p).read_text(encoding="utf-8"))
            if not isinstance(r, dict) or (r.get("sampleFrom") or r.get("ts") or 0) >= CUT:
                continue
            ss = [o["surah"] for o in (r.get("openers") or [])
                  if o["verdict"].startswith("بُرِّئ")]
            if ss: targets.setdefault(r["key"], set()).update(ss)
    for k in a.keys:
        targets.setdefault(k, set(a.surah or []))

    if not targets:
        sys.exit("لا هدف — مرّر مفتاحاً أو --state")
    order = sorted(targets, key=_rank)
    # ⛔ الأداةُ التي تُنتج رقماً تطبع سُلَّمها معه (درسُ 2026-09-02): كُنست
    # درجتا القاع (1000 و1500) من أداة 8e في `stash` عشرين دقيقة، فظلّت
    # تُخرج «مبرَّأ» من سُلَّمٍ مبتورٍ من طرفه الكاشف بلا أن يظهر ذلك في
    # مخرَجها. وفقدُ درجةٍ من الأسفل **لا يُنتج إدانةً كاذبة بل براءةً
    # كاذبة** — والبراءةُ الصامتة أخطرُ من الإدانة الصاخبة.
    # ⇒ ما لا يُطبع مع الرقم لا يُعرف بعد ساعة.
    print(f"السُّلَّم المستعمَل: {' · '.join(str(d) for d in LADDER)}م.ث "
          f"({len(LADDER)} درجات) · الإدانة: ظهورُ البسملة في أيّ درجة · "
          f"البراءة: غيابُها في كلّها")
    print("الطابور بالمشحون أولاً، والمؤجَّل (إعادةُ بناء الجيل الأول) آخراً:")
    for k in order:
        tag = {0: "مشحونٌ كامل", 1: "—", 2: "⏸️ مؤجَّل"}[_rank(k)[0]]
        print(f"   {tag:14s} {k}  ({len(targets[k])} مطلعاً)")
    print()
    bad = 0
    # القفل يخصّ الحالة المشتركة (--state) وحدها: تشغيلٌ مستهدَفٌ على مفتاحٍ
    # بعينه يكتب إلى stdout لا إلى مخرَجٍ مشترك، فلا يزاحم أحداً.
    if a.state:
        lock.acquire()
    for key in order:
        ss = targets[key]
        print(f"\n■ {key}  ({len(ss) or 'كل'} مطلعاً)")
        for r in check(key, ss or None):
            mark = "⛔" if r["at"] else "✅"
            print(f"  {mark} {r['surah']}:1 عند {r['startMs']}م.ث — {r['verdict']}"
                  + (f" (ظهرت عند {r['at']}م.ث)" if r["at"] else ""))
            for g in r["ladder"]:
                print(f"       [{g['ms']:5d}م.ث] «{g['heard']}»")
            bad += bool(r["at"])
    print(f"\nالحصيلة: {bad} مطلعاً مبتلعاً بالسُّلَّم.")
    print("⛔ البراءة هنا تعني: لم تظهر البسملة في أيّ درجة — لا في درجةٍ واحدة.")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
