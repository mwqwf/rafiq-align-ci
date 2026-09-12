# -*- coding: utf-8 -*-
"""📱 **سائقُ المحاكي — القياس بالمحرك الحقيقي** (خارطة الطريق M0-3، مسارُ الحقيقة).

المرآةُ البايثونية (`local_whisper.py`) سريعةٌ لكنها **مرآة**؛ والحقيقةُ هي `whisper.cpp` عبر
JNI بالنموذج المكمَّم q8 داخل التطبيق. مسبارُ `whisperBatch` يمرّ بـ`LongAudioTranscriber`
نفسِه (‏تسويةُ المستوى · التقطيع · النوافذ)، فمخرَجُه **حكمٌ لا تقدير**.

    python tools/tasmi_bench/emu_sweep.py --set g1 --limit 5          # طيّارٌ أولاً
    python tools/tasmi_bench/emu_sweep.py --set g2:gain-30
    python tools/tasmi_bench/emu_sweep.py --all                       # G1 وكلُّ شروط G2

⚠️ دروسٌ مدفوعةُ الثمن مطبَّقةٌ هنا:
- `am force-stop` قبل كل دفعة: `onNewIntent` لا يعالج هذه المسابر، فالنيّةُ الثانية تُهمَل بصمت.
- `MSYS_NO_PATHCONV=1` مع كل مسارٍ يبدأ بـ`/data`: Git Bash على وندوز يحوّله إلى
  `C:/Program Files/Git/data/...` فيُقرأ ملفٌّ آخر **بلا خطأ**.
- المجلدُ المدفوع يُعطى 777: التطبيق مستخدمٌ آخر غير `shell`، ولولا ذلك لرأى مجلداً فارغاً.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(HERE, "work")
WAV = os.path.join(WORK, "wav")
G2 = os.path.join(WORK, "g2")

PKG = "com.mushafak.app"
ACT = f"{PKG}/com.ali.rafiq.MainActivity"
MODEL = f"/data/data/{PKG}/files/models/whisper-tiny-ar-quran-q8_0.bin"
# ⚙️ يُبدَّل بـ`--model-path` لمقارنة نموذجٍ بنموذجٍ **على المحرك نفسِه** (لا على المرآة).
# ⛔ ولا يُقارَن نموذجٌ مكمَّم بنموذجٍ كاملِ الدقّة — يُحوَّل الطرفان بالطريقة نفسِها.
REMOTE = "/data/local/tmp/bench"
ADB = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk", "platform-tools", "adb.exe")
# 🐧 D-305: السائقُ نفسُه يعمل على عدّاء لينكس (محاكي CI) — `RAFIQ_ADB` يغلب، ثمّ `adb` من المسار إن غاب مسارُ وندوز.
if os.environ.get("RAFIQ_ADB"):
    ADB = os.environ["RAFIQ_ADB"]
elif not os.path.exists(ADB):
    import shutil as _sh
    ADB = _sh.which("adb") or ADB

CONDITIONS = ["g1"] + ["g2:" + c for c in [
    "gain-20", "gain-30", "gain-40",
    "noise-fan-20", "noise-fan-10", "noise-fan-5", "noise-babble-10",
    "speed-0.8", "speed-1.25", "speed-1.5",
    "phone", "clip", "reverb", "combo-hard",
    # G2b — سلوكُ المتعلّم (‏augment_learner.py): ليست أخطاءَ حفظٍ، فيجب ألّا تُخفض الدقّة
    "learner-repeat", "learner-pause", "learner-restart",
    "learner-throat", "learner-basmala", "learner-combo",
    "dn-g1", "dn-noise-fan-10", "dn-noise-fan-5", "dn-combo-hard",
]]


def sh(args, **kw):
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, **kw)


# ⛔ المحاكي **بالاسم** لا بالافتراض: هاتفُ المالك يُوصَل أحياناً فيصير جهازان،
# فيرمي adb «more than one device» ويقف المسحُ صامتاً عند 0/N (وقع 2026-09-08).
# وأمرُ المالك أن يكون القياسُ على المحاكي لا على الهاتف.
SERIAL = os.environ.get("RAFIQ_ADB_SERIAL", "emulator-5554")


def adb(*args, **kw):
    return sh([ADB, "-s", SERIAL] + list(args), **kw)


G3 = os.path.join(WORK, "g3")
G3R = os.path.join(WORK, "g3r")   # حقنُ ورشٍ وقالون (‏inject_riwaya.py)
G4 = os.path.join(WORK, "g4")     # التلاوةُ الطويلة (عدّةُ آيات) — مسارُ المستخدم الحقيقيّ


def local_dir(set_name):
    """‏`g1` · `g2:<شرط>` · **`g3:<clean|noisy|dn-noisy>`** (الحقنُ الجراحيّ — بوّابةُ الإنذار الكاذب)."""
    if set_name.startswith("g4"):        # g4 · g4n ضجيج · g4q خافت · g4c صعب
        return os.path.join(WORK, set_name)
    if set_name == "g1":
        return WAV
    kind, name = set_name.split(":", 1)
    return os.path.join({"g3": G3, "g3r": G3R}.get(kind, G2), name)


def tag_of(set_name):
    if set_name == "g1" or set_name.startswith("g4"):
        return set_name
    kind, name = set_name.split(":", 1)
    return f"{kind}-{name}"


TAG = ""   # 🏷️ وسمُ الذراع (‏--tag): نموذجان على المحرك نفسِه لا يكتبان في ملفٍّ واحد

def out_path(set_name, chain=False):
    """[chain]: `""` بلا شيء · `"chain"` كلاهما · `"gate"` البوّابةُ وحدها · `"lvl"` الجهارةُ وحدها."""
    suffix = (f"_{chain}" if chain else "") + (f"_{TAG}" if TAG else "")
    return os.path.join(WORK, f"hyps_emu_{tag_of(set_name)}{suffix}.json")


def run_set(set_name, limit=0, chunk=60, timeout_per_file=90, chain=False):
    src = local_dir(set_name)
    if not os.path.isdir(src):
        print(f"⛔ لا مجلد {src}")
        return None
    ids = sorted(f[:-4] for f in os.listdir(src) if f.endswith(".wav"))
    if limit:
        ids = ids[:limit]
    out = out_path(set_name, chain)
    done = {}
    if os.path.exists(out):
        done = json.load(open(out, encoding="utf-8")).get("hyps", {})
    todo = [i for i in ids if i not in done or "error" in done.get(i, {})]
    print(f"▶ {set_name}: {len(ids)} بنداً ({len(ids)-len(todo)} منجَز) — المتبقّي {len(todo)}", flush=True)
    if not todo:
        return done

    meta = {"engine": "whisper.cpp/JNI عبر whisperBatch (المحرك الحقيقي)",
            "device": "emulator-5554", "model": MODEL, "set": tag_of(set_name),
            "frontEnd": {"chain": "noiseGate+levelV2", "gate": "noiseGate", "lvl": "levelV2",
                         "cap": "noiseGate+groupCap10", "caponly": "groupCap10",
                         "gateonly": "noiseGate"}.get(chain, "shipped(v1)")}
    # دفعاتٌ صغيرة: سجلُّ المحاكي حلقيٌّ، ودفعةٌ طويلةٌ تُفقد أوائلَها.
    for start in range(0, len(todo), chunk):
        batch = todo[start:start + chunk]
        remote = f"{REMOTE}/{tag_of(set_name)}"
        adb("shell", f"rm -rf {remote}; mkdir -p {remote}; chmod 777 {REMOTE} {remote}")
        # خريطةُ الاسمِ المدفوع ⇒ المعرّف (‏انظر probe_name)
        names = {}
        for i in batch:
            nm = probe_name(i)
            if nm in names and names[nm] != i:
                raise SystemExit(f"⛔ تضاربُ أسماء: {i} و {names[nm]} يُدفعان بـ{nm}")
            names[nm] = i
            adb("push", os.path.join(src, i + ".wav"), f"{remote}/{nm}.wav")
        fixed = sum(1 for nm, i in names.items() if nm != i)
        if fixed:
            print(f"    🕋 {fixed} بنداً دُفعت باسمٍ يُقرأ منه الروايةُ صحيحةً (مثال: {next(nm for nm, i in names.items() if nm != i)})", flush=True)
        unknown = [i for nm, i in names.items() if nm == i and i.split("_")[0] not in RIWAYAT]
        if unknown:
            print(f"    ⚠️ {len(unknown)} بنداً لا تُشتقّ روايتُها من الاسم ⇒ حاكمُ المسبار سيسقط إلى حفص "
                  f"(مثال: {unknown[0]}) — أحكامُه على هذه البنود لا تُحتسب.", flush=True)
        adb("shell", f"chmod 777 {remote}/*.wav")
        adb("shell", "logcat", "-c")
        adb("shell", "am", "force-stop", PKG)
        time.sleep(1)
        args = ["shell", "am", "start", "-W", "-n", ACT, "--es", "whisperBatch", f"{MODEL},{remote}"]
        # 🎚️ كلُّ مكوّنٍ يُقاس **وحده** أيضاً: الفرقُ المركَّب لا يقول أيُّهما فعله.
        # "cap" = البناءُ الجديد (سقفُ المجموعة 10ث) بالبوّابة المفعَّلة افتراضاً — وسمٌ للمخرَج لا مفتاح.
        gate = "true" if chain in ("chain", "gate", "cap", "gateonly") else "false"
        lvl = "true" if chain in ("chain", "lvl") else "false"
        args += ["--ez", "noiseGate", gate, "--ez", "frontendV2", lvl]
        # 🧪 عزلُ السقف: `caponly` = سقفٌ 10 بلا بوّابة · `gateonly` = بوّابةٌ بسقفِ 25 (المشحون)
        cap = {"caponly": 10, "gateonly": 25, "cap": 10, "chain": 10}.get(chain, 25)
        args += ["--ei", "groupCap", str(cap)]
        # 🔤 D-303: إضافاتُ نيّةٍ حرّةٌ (‏`--es lang=ar`) تُمرَّر كما هي — بها يُقاس رمزُ اللغة على البناء نفسِه بلا إعادة بناء.
        for kv in EXTRA_ES:
            k, _, v = kv.partition("=")
            args += ["--es", k, v]
        # ⛔ **والمنطقيُّ يُمرَّر بـ`--ez` لا بـ`--es`:** المحركُ يقرأ `getBooleanExtra`، وإضافةٌ نصّيّةٌ باسم المفتاح
        # **لا يراها** فيبقى على افتراضه ⇒ يُقاس الضابطُ مرّتين ويُحكم كذباً أنّ «المفتاحَ لا أثرَ له».
        for kv in EXTRA_EZ:
            k, _, v = kv.partition("=")
            args += ["--ez", k, v or "true"]
        # 🔢 وعددٌ صحيحٌ بـ`--ei` (مثل `decodeBeam`) — بابٌ ثالثٌ لا يصلح فيه نصٌّ ولا منطقيّ.
        for kv in EXTRA_EI:
            k, _, v = kv.partition("=")
            args += ["--ei", k, v]
        adb(*args)
        # 🚨 **إضافةُ نيّةٍ تُتجاهَل بصمتٍ = ذراعان متطابقتان وحكمٌ كاذب** («اللغةُ لا أثرَ لها»).
        # المحركُ يطبع `RafiqFrontEnd … lang=<x>` عند استقبالها ⇒ تُتحقَّق مرّةً في أوّل دفعة، وإلا وقف المسح.
        global _ES_VERIFIED
        if (EXTRA_ES or EXTRA_EZ) and not _ES_VERIFIED:
            time.sleep(3)
            fe = adb("shell", "logcat", "-d", "-s", "RafiqFrontEnd:*").stdout or ""
            # ⚠️ **تُطابَق بالمفتاح لا بـ`مفتاح=قيمة`** (‏درسُ 2026-09-12): المحركُ قد يطبع اسماً أطولَ من اسم الإضافة
            # (‏`criticalPairs` ⇒ `criticalPairsUncertain=true`) فالمطابقةُ الحرفيّةُ تُطلق **إنذاراً كاذباً** وتوقف
            # مسحاً صحيحاً. فيُتحقَّق من ظهور المفتاح، ومن القيمة متى ظهرت بصيغتها الحرفيّة.
            flat = fe.replace(" ", "")
            want = list(EXTRA_ES) + list(EXTRA_EI) + [(kv if "=" in kv else kv + "=true") for kv in EXTRA_EZ]
            missing = []
            for kv in want:
                k, _, v = kv.partition("=")
                if k not in flat:
                    missing.append(kv)
                elif f"{k}={v}" not in flat and f"={v}" not in flat:
                    missing.append(f"{kv} (المفتاحُ ظهر والقيمةُ لم تُطابق)")
            if missing:
                raise SystemExit(f"⛔ المسبارُ لم يُقرّ بإضافات النيّة {missing} — سطرُ RafiqFrontEnd: "
                                 f"{fe.strip().splitlines()[-1] if fe.strip() else 'لا شيء'!r}. "
                                 "‏APK لا يدعمها ⇒ الذراعان ستتطابقان والحكمُ سيكذب.")
            _ES_VERIFIED = True
            print(f"✅ المسبارُ أقرّ بالإضافات: {' · '.join(EXTRA_ES)}", flush=True)
        deadline = time.time() + timeout_per_file * len(batch) + 120
        seen, last_n, times, judges = {}, -1, {}, {}
        while time.time() < deadline:
            time.sleep(15)
            log = adb("shell", "logcat", "-d", "-s", "RafiqBatch:*", "RafiqJudge:*").stdout
            seen = parse_log(log, times, judges, names)
            if "__done__" in log or len(seen) >= len(batch):
                break
            if len(seen) != last_n:
                last_n = len(seen)
                print(f"    … {len(seen)}/{len(batch)}", flush=True)
        for i in batch:
            t = seen.get(i)
            done[i] = ({"text": t, "rc": 0, **({"ms": times[i]} if i in times else {}),
                        **({"judge": judges[i]} if i in judges else {})}
                       if t is not None else {"error": "لم يظهر في السجل"})
        json.dump({"meta": meta, "hyps": done}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
        ok = sum(1 for i in batch if i in seen)
        print(f"  دفعة {start//chunk + 1}: {ok}/{len(batch)} ⇒ {out}", flush=True)
        adb("shell", f"rm -rf {remote}")
    return done


# 🕋 **اسمٌ يقرأُه حاكمُ المسبار صحيحاً** — درسٌ مدفوع (‏2026-09-12 · D-326):
# مسبارُ `whisperBatch` يشتقّ الروايةَ من **أوّل مقطعٍ في اسم الملفّ** (`^([a-z]+)_…(\d{3})(\d{3})\.wav$`)
# فاسمُ بنود الحشو `inj_warsh_omit_084021.wav` يعطيه `inj` ⇒ **يسقط صامتاً إلى حفص**، فقابل تلاوةَ
# ورشٍ وقالون بنصّ حفصٍ وبروفايلِه في **160/160 بنداً**، وبدا أنّ «المرآةَ تُقلّل الاتّهامَ 2.09 نقطة»
# وهو كذبٌ سببُه المرجعُ لا المرآة. فالعلاجُ عندنا: نُقدّم الروايةَ في الاسم المدفوع ونُعيد الخريطة.
RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")


def probe_name(i):
    """اسمٌ للملفّ المدفوع يستخرج منه المسبارُ الروايةَ والآيةَ صحيحةً (أو الاسمُ كما هو إن كان سليماً)."""
    parts = i.split("_")
    if parts[0] in RIWAYAT:
        return i
    rw = next((q for q in parts if q in RIWAYAT), None)
    m = re.search(r"(\d{3})(\d{3})$", i)
    if not rw or not m:
        return i
    mid = "".join(q for q in parts if q not in RIWAYAT and not q.isdigit())
    return f"{rw}_{mid or 'x'}_{m.group(1)}{m.group(2)}"


def parse_log(log, times=None, judges=None, names=None):
    """أسطرُ `RafiqBatch` بصيغة `<id>.wav<TAB><text>`.

    ⏱️ ومتى أُعطي [times] تُستخرج **أزمنةُ البنود** من طوابع logcat: زمنُ البند = الفارقُ بين سطره والسطر
    قبلَه (وأوّلُ بندٍ يحمل زمنَ تحميل النموذج فيُستثنى) — طريقةُ `emu_score.py` نفسُها.
    ولماذا يلزم: مفتاحٌ كـ`beam 5` يُشترى بالزمن، والتسميعُ الحيُّ يفكّ **أثناء** التلاوة ⇒ RTF > 1 تأخيرٌ
    متراكمٌ لا يلحق فيه الشيخُ القارئ. فلا يُحكم على مفتاحٍ بالدقّة وحدَها.
    """
    out = {}
    prev = None
    first = True
    for ln in log.split("\n"):
        if "RafiqBatch" not in ln and "RafiqJudge" not in ln:
            continue
        t = None
        ts = re.match(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)", ln)
        if ts:
            import datetime as _dt
            try:
                t = _dt.datetime.strptime("2026-" + ts.group(1), "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                t = None
        body = ln.rstrip()
        # 🧾 سطرُ **حاكم المحرك** (‏`RafiqJudge`): أحكامُ الكلمات كما حكم بها `RecitationScorer` داخل التطبيق.
        # قيمتُه مزدوجة: يقيس المفاتيحَ التي تمسّ الحاكمَ (لا يراها مسبارُ النصّ)، **ويصدّق مرآتَنا البايثونية**
        # (`scorer.py`) على بنودٍ حقيقيّةٍ من مخرَج المحرك — وكلُّ أرقام اللوحة تستند إلى تلك المرآة.
        if judges is not None and "RafiqJudge" in body:
            j = re.search(r"([A-Za-z0-9_\-.]+)\.wav\t(.*)$", body)
            if j:
                judges[(names or {}).get(j.group(1), j.group(1))] = j.group(2).strip()
            continue
        m = re.search(r"([A-Za-z0-9_\-.]+)\.wav\t(.*)$", body)
        if m:
            key = (names or {}).get(m.group(1), m.group(1))
            out[key] = " ".join(m.group(2).split())
            if times is not None and t and prev:
                if first:
                    first = False        # أوّلُ بندٍ يحمل زمنَ تحميل النموذج معه فلا يُحتسب
                else:
                    times[key] = int((t - prev).total_seconds() * 1000)
            if t:
                prev = t
        elif body.endswith("done"):
            out["__done__"] = ""
        elif body.rstrip().endswith("start") or " start " in body:
            if t:
                prev, first = t, True
    out.pop("__done__", None)
    return out


EXTRA_ES = []        # إضافاتُ نيّةٍ نصّيّة من `--es` (D-303)
EXTRA_EZ = []        # إضافاتُ نيّةٍ منطقيّة من `--ez` — المحركُ يقرؤها بـgetBooleanExtra فلا تصلح `--es`
EXTRA_EI = []        # إضافاتُ نيّةٍ عدديّة من `--ei` (‏`decodeBeam=3`)
_ES_VERIFIED = False # تُتحقَّق مرّةً من سجلّ المحرك: إضافةٌ مُتجاهَلةٌ بصمتٍ تُنتج ذراعَين متطابقتين
LOCK = os.path.join(WORK, ".emu_sweep.lock")


def acquire_lock():
    """🔒 **سائقٌ واحدٌ للمحاكي لا غير.**

    ⚠️ عطبٌ وقع فعلاً (2026-09-08 ‏00:00): `pkill` غير موجودٍ في هذه البيئة فأخفقت محاولاتُ
    إيقاف طابورٍ قديم **صامتةً**، فجرى سائقان معاً قرابةَ ساعة. والخطرُ ليس البطء: المعرّفاتُ
    **متطابقةٌ بين الشروط** (‏`hafs_abdulbasit_003160.wav` في كل مجلد)، و`logcat -c` و`am force-stop`
    مشتركان — فقد يقرأ سائقٌ سطرَ الآخر فيُنسب تفريغُ شرطٍ إلى شرطٍ آخر بصمت. (فُحص الأثرُ بعدُ
    فلم يظهر خلط: نِسبُ التطابق مع النظيف بقيت مرتّبةً فيزيائياً — 74.6٪ ثم 46.5 ثم 20.4 مع اشتداد
    الضجيج. لكنّ الفحصَ بعد الوقوع ليس بديلاً عن المنع.)
    """
    if os.path.exists(LOCK):
        try:
            age = time.time() - os.path.getmtime(LOCK)
            pid = open(LOCK, encoding="utf-8").read().strip()
        except OSError:
            age, pid = 0.0, "?"
        if age < 3600:
            print(f"[منع] سائقٌ آخر يعمل على المحاكي (pid {pid}، منذ {age/60:.0f} دقيقة).")
            print("      إن كان ميتاً فاحذف: " + LOCK)
            return False
        print(f"[تنبيه] قفلٌ قديم ({age/60:.0f} دقيقة) — يُتجاوز.")
    os.makedirs(WORK, exist_ok=True)
    open(LOCK, "w", encoding="utf-8").write(str(os.getpid()))
    return True


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-path", help="نموذجٌ بديلٌ على الجهاز (مسارٌ مطلق)")
    ap.add_argument("--es", action="append", default=[], metavar="KEY=VAL",
                    help="إضافةُ نيّةٍ نصّيّةٌ تُمرَّر إلى المسبار كما هي (تتكرّر) — مثل `--es lang=ar`")
    ap.add_argument("--ez", action="append", default=[], metavar="KEY[=BOOL]",
                    help="إضافةُ نيّةٍ **منطقيّة** (تتكرّر) — مثل `--ez decodeGuard` أو `--ez criticalPairs=true`")
    ap.add_argument("--ei", action="append", default=[], metavar="KEY=INT",
                    help="إضافةُ نيّةٍ **عدديّة** (تتكرّر) — مثل `--ei decodeBeam=3`")
    ap.add_argument("--set", default="g1")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=60)
    ap.add_argument("--chain", default="", choices=["", "chain", "gate", "lvl", "cap", "caponly", "gateonly"],
                    help="ما يُفعَّل في المحرك: كلاهما (chain) · البوّابة (gate) · الجهارة (lvl)")
    ap.add_argument("--tag", default="", help="وسمُ الذراع في اسم ملفّ المخرَج (مثلاً shipped · v2)")
    args = ap.parse_args()
    if args.tag:
        global TAG
        TAG = args.tag
    if args.model_path:
        global MODEL
        MODEL = args.model_path
        print(f"⚙️ النموذج: {MODEL}")
    if args.es:
        global EXTRA_ES
        EXTRA_ES = list(args.es)
        print(f"🔤 إضافاتٌ نصّيّة: {' · '.join(EXTRA_ES)}")
    if args.ez:
        global EXTRA_EZ
        EXTRA_EZ = list(args.ez)
        print(f"🎚️ إضافاتٌ منطقيّة: {' · '.join(EXTRA_EZ)}")
    if args.ei:
        global EXTRA_EI
        EXTRA_EI = list(args.ei)
        print(f"🔢 إضافاتٌ عدديّة: {' · '.join(EXTRA_EI)}")

    if not os.path.exists(ADB):
        print(f"⛔ لا adb في {ADB}")
        return 1
    if "device" not in adb("devices").stdout:
        print("⛔ لا محاكٍ متصل")
        return 1

    if not acquire_lock():
        return 2
    try:
        sets = CONDITIONS if args.all else [args.set]
        for s in sets:
            t0 = time.time()
            run_set(s, args.limit, args.chunk, chain=args.chain)
            print(f"✅ {s} في {(time.time()-t0)/60:.1f} دقيقة\n", flush=True)
    finally:
        release_lock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
