#!/usr/bin/env python3
"""سائق أسطول رفيق: يوزّع القراء على العمليات المتوازية ويرفع كل فهرس فور اكتماله."""
import os, subprocess, sys, time, threading, queue, pathlib
ROOT = "/root/QuranRafiq"
JOBS = int(os.environ.get("JOBS", "4"))
SHARD = int(os.environ.get("SHARD", "0"))
SHARDS = int(os.environ.get("SHARDS", "1"))
# ⚠️ إضافة خادمٍ للأسطول تغيّر SHARDS على **كل** الخوادم، ولو كان الرقم في
# `restart.sh` وحده لوجب تحرير خمسة ملفات (أو عشرين) بيدٍ واحدة ليلاً — وأول
# خادمٍ يُنسى يعيد فهرسة ما فهرسه غيره بلا أن يشتكي أحد. فملفٌ واحد يُكتب
# بسطرٍ واحد `SHARD SHARDS`، ويُقدَّم على البيئة، ويُتجاهل بصمت إن غاب.
_SF = "/root/shards.txt"
try:
    with open(_SF, encoding="utf-8") as _f:
        _p = _f.read().split()
    if len(_p) >= 2:
        SHARD, SHARDS = int(_p[0]), int(_p[1])
        print(f"التقسيم من {_SF}: SHARD={SHARD} SHARDS={SHARDS}", flush=True)
except FileNotFoundError:
    pass
except Exception as _e:  # ملفٌ معطوب لا يوقف الأسطول، لكنه لا يمرّ صامتاً
    print(f"⚠️ {_SF} غير مقروء ({_e}) — يُعتمد SHARD/SHARDS من البيئة", flush=True)
if not (0 <= SHARD < SHARDS):
    sys.exit(f"⛔ تقسيم غير صالح: SHARD={SHARD} SHARDS={SHARDS}")
LIST = os.environ.get("LIST", f"{ROOT}/tools/cloud/reciters.tsv")
PY_BIN = f"{ROOT}/.venv/bin/python"
ENV = dict(os.environ, ALIGN_REFINE="1")  # ⛔ الجيل الثاني إلزامي: بدونه الفهارس Gen-1 (تغطية ~45%، MED أغلبية)
os.makedirs("/root/logs", exist_ok=True); os.makedirs("/root/done", exist_ok=True)

rows = []
for line in open(LIST, encoding="utf-8"):
    line = line.rstrip("\n\r")
    if not line or line.startswith("#"): continue
    p = line.split("\t")
    if len(p) < 4: continue
    rows.append((p[0], p[1], p[2], int(p[3])))
rows.sort(key=lambda r: r[3])
mine = [r for i, r in enumerate(rows) if i % SHARDS == SHARD]
print(f"شريحة {SHARD}/{SHARDS}: {len(mine)} قارئاً · {JOBS} عمليات متوازية", flush=True)

q = queue.Queue()
for r in mine: q.put(r)


GUARD_MIN_ENTRIES = 5900
def index_ok(rid):
    """حارس الرفع: تنزيل فاشل أو صوت معطوب ينتج «سوراً» في ثوانٍ بمداخل شبه فارغة — لا يُرفع شيء دون 114 سورة وآلاف المداخل."""
    import glob, json
    d = f"{ROOT}/tools/alignment/work/batch_{rid}"
    fs = glob.glob(f"{d}/s*.json")
    if len(fs) < 114: return False, f"سور {len(fs)}/114"
    n = 0
    for f in fs:
        try:
            j = json.load(open(f, encoding="utf-8"))
            n += sum(1 for e in j.get("entries", []) if e.get("startMs") is not None)
        except Exception as ex: return False, f"json معطوب: {ex}"
    if n < GUARD_MIN_ENTRIES: return False, f"مداخل {n} < {GUARD_MIN_ENTRIES}"
    # كل سورة يجب أن تحمل بصمة صوتها الحقيقي — غيابها = تنزيل فاشل مُشتق نصياً (غش صامت)
    nosha = [f for f in fs if not json.load(open(f, encoding="utf-8")).get("sha256")]
    if nosha: return False, f"سور بلا بصمة صوت: {len(nosha)}"
    try:
        lg = open(f"/root/logs/{rid}.log", encoding="utf-8", errors="ignore").read()
        bad = lg.count("Error opening input files") + lg.count("Traceback")
        if bad: return False, f"أخطاء صوت/تنفيذ في السجل: {bad}"
    except Exception: pass
    return True, f"مداخل {n} · بصمات 114/114"

MIN_SHIPPED = 5600          # ≥90% من 6236 بعد إسقاط LOW
def shipped_ok(idx):
    """الفهرس المشحون (بعد إسقاط LOW) يجب أن يغطي ≥90% وأن يكون HIGH فيه ≥50%، وألا يكون أسوأ من المنشور على R2."""
    import gzip, json, urllib.request
    try:
        d = json.load(gzip.open(idx, "rt", encoding="utf-8"))
    except Exception as ex:
        return False, f"jz معطوب: {ex}"
    n = len(d.get("entries", [])); hi = sum(1 for e in d["entries"] if e.get("confBand") == "HIGH")
    if n < MIN_SHIPPED: return False, f"تغطية {n}/6236 < {MIN_SHIPPED} — لا يُشحن فهرس ناقص"
    if hi < n * 0.5: return False, f"HIGH {hi}/{n} < 50% — صقل غائب أو صوت رديء"
    try:
        url = f"https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/timings/{d['riwaya']}/{d['reciterId']}.jz"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        cur = json.load(gzip.open(urllib.request.urlopen(req, timeout=30), "rt", encoding="utf-8"))
        cn = len(cur.get("entries", []))
        if cn > n: return False, f"المنشور أفضل ({cn} > {n}) — لا كتابة فوق فهرس أحسن"
    except Exception:
        pass  # 404 = لا منشور ⇒ يُرفع
    return True, f"مشحون {n} · HIGH {hi}"

def worker(n):
    while True:
        try: rid, riwaya, base, prio = q.get_nowait()
        except queue.Empty: return
        if pathlib.Path(f"/root/done/{rid}").exists():
            print(f"⏭ {rid} (منجز)", flush=True); continue
        t0 = time.time(); print(f"▶ {rid} ({riwaya}) {time.strftime('%H:%M:%S')}", flush=True)
        log = open(f"/root/logs/{rid}.log", "w", encoding="utf-8")
        rc = subprocess.call([PY_BIN, f"{ROOT}/tools/alignment/batch_run.py", "--reciter", rid,
                              "--riwaya", riwaya, "--base", base, "--surahs", "1-114"],
                             cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=None, env=ENV)
        idx = f"{ROOT}/tools/alignment/work/timings_{riwaya}_{rid}.jz"
        ok, why = index_ok(rid) if rc == 0 else (False, f"rc={rc}")
        if rc == 0 and not ok:
            print(f"🛑 {rid} رُفض الرفع: {why} — يُحذف مخرجه ليُعاد كاملاً", flush=True)
            import shutil; shutil.rmtree(f"{ROOT}/tools/alignment/work/batch_{rid}", ignore_errors=True)
            try: os.remove(idx)
            except Exception: pass
        if rc == 0 and ok and os.path.exists(idx):
            ok2, why2 = shipped_ok(idx)
            if not ok2:
                print(f"🛑 {rid} رُفض الرفع (بعد الإسقاط): {why2} — يُحذف مخرجه ليُعاد", flush=True)
                import shutil; shutil.rmtree(f"{ROOT}/tools/alignment/work/batch_{rid}", ignore_errors=True)
                try: os.remove(idx)
                except Exception: pass
                log.close(); continue
            print(f"🔒 {rid} حارس الرفع: {why} · {why2}", flush=True)
            u = subprocess.call([PY_BIN, f"{ROOT}/tools/alignment/upload_timings.py", "--index", idx],
                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            if u == 0:
                pathlib.Path(f"/root/done/{rid}").touch()
                print(f"✅ {rid} — {int(time.time()-t0)}ث", flush=True)
            else: print(f"⚠️ {rid} فُهرس ولم يُرفع", flush=True)
        else:
            print(f"❌ {rid} rc={rc} — {int(time.time()-t0)}ث", flush=True)
        log.close()
        wd = f"{ROOT}/tools/alignment/work/batch_{rid}"
        for f in pathlib.Path(wd).glob("*") if os.path.isdir(wd) else []:
            if f.suffix in (".mp3", ".wav"):
                try: f.unlink()
                except Exception: pass

ts = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(JOBS)]
[t.start() for t in ts]; [t.join() for t in ts]
print("FLEET_DONE", flush=True)
