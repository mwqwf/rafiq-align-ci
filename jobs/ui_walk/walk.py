#!/usr/bin/env python3
# 🚶 سائقُ جولة الواجهة على المحاكي السحابي (دراسة المستشار 2026-11-05):
#    يفتح كلَّ مدخلٍ معروفٍ في «مصحفك» (التبويبات، الأقسام، القائمة الجانبية، الإعدادات، المداخل التصحيحية)،
#    ويلتقط لكلِّ شاشةٍ صورةً وشجرةَ الواجهة ونصوصَها، ثمّ يزحف على الأزرار بميزانيةٍ زمنية،
#    ويقيس زمنَ الفتح والذاكرةَ والانهيارات. قراءةٌ محضة: لا يكتب في أيّ مستودع ولا دلو.
import argparse, hashlib, json, os, re, subprocess, sys, time, xml.etree.ElementTree as ET

PKG = "com.mushafak.app"
ACT = "com.ali.rafiq.MainActivity"
# ⛔ أزرارٌ لا يضغطها الزاحف: تمسح بياناتِ المحاكي أو تُخرج من التطبيق بلا فائدة.
DENY = re.compile(r"حذف|مسح|إعادة ضبط|إعادة تعيين|إلغاء الاشتراك|تسجيل الخروج|امسح|delete|reset|sign out|log out|uninstall", re.I)
ONBOARD = re.compile(r"^(التالي|ابدأ|متابعة|تخطّ|تخطي|تخطى|موافق|فهمت|حسناً|لاحقاً|ليس الآن|Next|Start|Skip|Continue|OK|Got it|Allow|السماح)$")

A = argparse.ArgumentParser()
A.add_argument("--out", required=True)
A.add_argument("--deadline", type=float, required=True)   # زمن unix يجب أن ينتهي الزحف قبله
A.add_argument("--wav", default="")
A.add_argument("--ask", type=int, default=1)               # عددُ أسئلة «اسأل» الفعلية (كلٌّ منها سنتات)
ARGS = A.parse_args()
OUT = ARGS.out
os.makedirs(f"{OUT}/shots", exist_ok=True)
os.makedirs(f"{OUT}/xml", exist_ok=True)
STEPS, EVENTS, METRICS = [], [], {}
T0 = time.time()


def log(msg):
    print(f"[{int(time.time()-T0):4d}s] {msg}", flush=True)


def adb(*args, timeout=90):
    try:
        r = subprocess.run(["adb", *args], capture_output=True, timeout=timeout)
        return r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def sh(cmd, timeout=90):
    return adb("shell", cmd, timeout=timeout)


def left():
    return ARGS.deadline - time.time()


# ───────── حجم الشاشة ─────────
m = re.search(r"(\d+)x(\d+)", sh("wm size"))
W, H = (int(m.group(1)), int(m.group(2))) if m else (1080, 1920)
log(f"الشاشة {W}x{H}")


# ───────── شجرة الواجهة ─────────
def dump():
    for _ in range(3):
        sh("uiautomator dump /sdcard/ui.xml", timeout=60)
        x = adb("exec-out", "cat", "/sdcard/ui.xml", timeout=30)
        if "<hierarchy" in x:
            return x
        time.sleep(1.0)
    return ""


def parse(x):
    nodes = []
    if not x:
        return nodes
    try:
        root = ET.fromstring(x[x.index("<hierarchy"):])
    except Exception:
        return nodes
    for n in root.iter("node"):
        b = re.findall(r"\d+", n.get("bounds", ""))
        if len(b) != 4:
            continue
        x1, y1, x2, y2 = map(int, b)
        nodes.append({
            "text": (n.get("text") or "").strip(),
            "desc": (n.get("content-desc") or "").strip(),
            "rid": n.get("resource-id") or "",
            "cls": (n.get("class") or "").split(".")[-1],
            "pkg": n.get("package") or "",
            "click": n.get("clickable") == "true",
            "scroll": n.get("scrollable") == "true",
            "check": n.get("checkable") == "true",
            "checked": n.get("checked") == "true",
            "sel": n.get("selected") == "true",
            "en": n.get("enabled") != "false",
            "b": (x1, y1, x2, y2),
        })
    return nodes


def label(n):
    return n["text"] or n["desc"]


def texts(nodes):
    seen, outl = set(), []
    for n in nodes:
        for t in (n["text"], n["desc"]):
            if t and t not in seen and n["pkg"] == PKG:
                seen.add(t)
                outl.append(t)
    return outl


def signature(nodes):
    return hashlib.md5("|".join(texts(nodes)[:40]).encode()).hexdigest()[:10]


def focus():
    f = sh("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -2")
    m2 = re.search(r"([\w.]+)/([\w.]+)", f)
    return (m2.group(1), m2.group(2)) if m2 else ("?", "?")


def crashes():
    c = adb("logcat", "-d", "-b", "crash", timeout=30)
    return [l.strip()[:220] for l in c.splitlines() if "FATAL" in l or "AndroidRuntime" in l][:20]


# ───────── أفعال ─────────
def tap(x, y):
    sh(f"input tap {int(x)} {int(y)}")


def tap_node(n):
    x1, y1, x2, y2 = n["b"]
    tap((x1 + x2) / 2, (y1 + y2) / 2)


def swipe(d):
    cx, cy = W // 2, int(H * 0.55)
    if d == "up":     sh(f"input swipe {cx} {int(H*0.78)} {cx} {int(H*0.30)} 400")
    if d == "down":   sh(f"input swipe {cx} {int(H*0.30)} {cx} {int(H*0.78)} 400")
    if d == "left":   sh(f"input swipe {int(W*0.85)} {cy} {int(W*0.15)} {cy} 350")
    if d == "right":  sh(f"input swipe {int(W*0.15)} {cy} {int(W*0.85)} {cy} 350")
    time.sleep(1.2)


def back():
    sh("input keyevent 4")
    time.sleep(1.0)


def stop():
    sh(f"am force-stop {PKG}")
    time.sleep(0.8)


def launch(extras=None, wait=4.0, fresh=True):
    """يشغّل النشاط الرئيسيّ مع مداخلَ تصحيحيّةٍ اختياريّة؛ ويعيد TotalTime إن أمكن."""
    if fresh:
        stop()
    cmd = f"am start -W -n {PKG}/{ACT}"
    for k, v in (extras or {}).items():
        if isinstance(v, bool):
            cmd += f" --ez {k} {'true' if v else 'false'}"
        else:
            cmd += f" --es {k} {v}"
    o = sh(cmd, timeout=60)
    time.sleep(wait)
    m2 = re.search(r"TotalTime:\s*(\d+)", o)
    return int(m2.group(1)) if m2 else None


SHOT_N = [0]
LAST_SIG = [""]


def step(name, note="", force=False):
    """يسجّل شاشةً: صورة + شجرة + نصوص + النشاط الأماميّ + انهيارات جديدة."""
    nodes = parse(dump())
    sig = signature(nodes)
    if not force and sig == LAST_SIG[0] and nodes:
        EVENTS.append({"t": int(time.time()-T0), "skip_same": name})
        return nodes, sig, False
    LAST_SIG[0] = sig
    SHOT_N[0] += 1
    i = SHOT_N[0]
    safe = re.sub(r"[^\w؀-ۿ]+", "_", name)[:60]
    fn = f"{i:03d}_{safe}"
    # الصورة خامٌ ثنائيّة (لا تمرّ بفكّ ترميز adb())
    try:
        raw = subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout
        with open(f"{OUT}/shots/{fn}.png", "wb") as f:
            f.write(raw)
    except Exception as e:
        EVENTS.append({"t": int(time.time()-T0), "shot_err": str(e)[:100]})
    x = dump()
    with open(f"{OUT}/xml/{fn}.xml", "w", encoding="utf-8") as f:
        f.write(x)
    pk, ac = focus()
    cr = crashes()
    clickables = [label(n) for n in nodes if n["click"] and label(n) and n["pkg"] == PKG]
    rec = {
        "i": i, "name": name, "note": note, "file": f"{fn}.png", "t": int(time.time()-T0),
        "focus": f"{pk}/{ac.split('.')[-1]}", "sig": sig, "in_app": pk == PKG,
        "n_nodes": len(nodes), "texts": texts(nodes)[:60], "clickables": clickables[:40],
        "crash": len(cr),
    }
    STEPS.append(rec)
    log(f"📸 {i:03d} {name} · {rec['focus']} · نصوص {len(rec['texts'])} · أزرار {len(clickables)}" + (f" · ⛔ انهيار {len(cr)}" if cr else ""))
    return nodes, sig, True


def ensure_in_app():
    pk, _ = focus()
    if pk != PKG:
        back()
        pk, _ = focus()
        if pk != PKG:
            launch(fresh=False, wait=3)


def find(nodes, pat, click=True):
    rx = re.compile(pat)
    for n in nodes:
        if (not click or n["click"]) and n["pkg"] == PKG and (rx.search(n["text"]) or rx.search(n["desc"])):
            return n
    return None


def bottom_tabs(nodes):
    tabs = [n for n in nodes if n["click"] and n["pkg"] == PKG and n["b"][1] >= H * 0.84
            and (n["b"][2] - n["b"][0]) < W * 0.5 and label(n)]
    if not tabs:
        tabs = [n for n in nodes if n["click"] and n["pkg"] == PKG and n["b"][1] >= H * 0.86
                and (n["b"][2] - n["b"][0]) < W * 0.5]
    tabs.sort(key=lambda n: -n["b"][0])   # من اليمين إلى اليسار (RTL)
    return tabs


# ═══════════ ١) الإطلاق الأوّل والتهيئة ═══════════
def phase_launch():
    log("① الإطلاق الأوّل")
    adb("logcat", "-c", "-b", "crash")
    adb("logcat", "-c")
    tt = launch(wait=8)
    METRICS["first_launch_total_ms"] = tt
    nodes, _, _ = step("الإطلاق_الأول", force=True)
    for k in range(10):
        n = find(nodes, ONBOARD.pattern)
        if not n:
            break
        tap_node(n); time.sleep(1.5)
        nodes, _, _ = step(f"تهيئة_{k+1}_{label(n)}")
    swipe("up"); step("الإطلاق_بعد_تمرير")
    swipe("down")


# ═══════════ ٢) التبويبات والأقسام ═══════════
TAB_NAMES = []


def phase_tabs():
    log("② التبويبات السفلية والأقسام بالسحب")
    launch(wait=5)
    nodes = parse(dump())
    tabs = bottom_tabs(nodes)
    METRICS["bottom_tabs"] = [label(t) or f"tab{i}" for i, t in enumerate(tabs)]
    log(f"التبويبات: {METRICS['bottom_tabs']}")
    for i, t in enumerate(tabs):
        name = label(t) or f"tab{i}"
        TAB_NAMES.append(name)
        tap_node(t); time.sleep(2.0)
        nodes, sig0, _ = step(f"تبويب_{name}", force=True)
        # تمريرٌ رأسيّ
        swipe("up"); step(f"تبويب_{name}_تمرير")
        swipe("down"); swipe("down")
        # أقسامٌ بالسحب الأفقيّ (الاتجاهان؛ يُسجَّل ما تغيّر فقط)
        for d in ("left", "left", "left", "right", "right", "right", "right", "right"):
            swipe(d)
            _, _, new = step(f"تبويب_{name}_سحب_{d}")
        tap_node(t); time.sleep(1.0)


# ═══════════ ٣) المداخل التصحيحيّة (كلُّ ميزةٍ بابُها) ═══════════
INTENTS = [
    ("المصحف_مصوّر_الفاتحة", {"openMushaf": "1,images"}),
    ("المصحف_نصّ_البقرة", {"openMushaf": "2,text"}),
    ("المصحف_طباعة_الكهف", {"openMushaf": "18,print"}),
    ("المصحف_ورش_الفاتحة", {"setRiwaya": "warsh", "openMushaf": "1,images"}),
    ("المصحف_قالون_يس", {"setRiwaya": "qalun", "openMushaf": "36,images"}),
    ("المصحف_الدوري_الملك", {"setRiwaya": "douri", "openMushaf": "67,images"}),
    ("المصحف_حفص_عودة", {"setRiwaya": "hafs", "openMushaf": "112,images"}),
    ("سمّع", {"openTasmi": True}),
    ("سمّع_معي", {"openReciteWithMe": True}),
    ("التسميع_المطوّل", {"openLongTasmi": "1,3,hafs"}),
    ("حفظي", {"openHifz": True}),
    ("وِردي", {"openWird": True}),
    ("اختبرني", {"openQuiz": True}),
    ("يومي", {"openDaily": True}),
    ("مواقيت_الصلاة", {"openPrayer": True}),
    ("التفسير", {"openTafsir": True}),
    ("التجويد", {"openTajweed": True}),
    ("خريطة_الأخطاء", {"openErrorMap": True}),
    ("المقارنة", {"openCompare": True}),
    ("الدعم_والتبرّع", {"openSupport": True}),
    ("المعلّم", {"openTeacher": True}),
    ("اسأل", {"openAsk": True}),
    ("حول_التطبيق", {"openAbout": True}),
    ("متابعة_القراءة", {"openContinue": True}),
    ("التذكير_الآن", {"reminderNow": True}),
    ("التهيئة_القسريّة", {"forceOnboarding": True}),
]


def phase_intents():
    log("③ المداخل التصحيحيّة")
    asked = 0
    for name, ex in INTENTS:
        if left() < 20 * 60:
            log("⏳ الميزانية تضيق؛ تُختصر المداخل"); break
        try:
            launch(ex, wait=5)
            nodes, _, _ = step(f"مدخل_{name}", note=json.dumps(ex, ensure_ascii=False), force=True)
            if name == "اسأل" and asked < ARGS.ask:
                chip = None
                for n in nodes:
                    if n["click"] and n["pkg"] == PKG and len(n["text"]) > 14 and ("?" in n["text"] or "؟" in n["text"]):
                        chip = n; break
                if chip:
                    tap_node(chip); asked += 1
                    time.sleep(20); step("اسأل_جواب_1", force=True)
                    swipe("up"); step("اسأل_جواب_2")
            elif name in ("سمّع", "سمّع_معي"):
                time.sleep(6); step(f"مدخل_{name}_بعد_6ث")
            elif name == "التهيئة_القسريّة":
                for k in range(8):
                    n = find(nodes, ONBOARD.pattern)
                    if not n: break
                    tap_node(n); time.sleep(1.5)
                    nodes, _, _ = step(f"تهيئة_قسرية_{k+1}_{label(n)}")
            else:
                swipe("up"); step(f"مدخل_{name}_تمرير")
                # زرّان من الشاشة نفسها (عمقٌ واحد) ليظهر ما خلفها
                nodes2 = parse(dump())
                cands = [n for n in nodes2 if n["click"] and n["pkg"] == PKG and label(n)
                         and not DENY.search(label(n)) and n["b"][1] < H * 0.84 and n["b"][1] > H * 0.08][:3]
                for c in cands:
                    tap_node(c); time.sleep(1.8)
                    step(f"مدخل_{name}_زر_{label(c)[:20]}")
                    ensure_in_app(); back()
        except Exception as e:
            EVENTS.append({"t": int(time.time()-T0), "intent_err": name, "err": str(e)[:200]})
            log(f"⚠ {name}: {e}")


# ═══════════ ٤) القائمة الجانبية والإعدادات ═══════════
def open_menu():
    launch(wait=4)
    nodes = parse(dump())
    n = find(nodes, r"^(القائمة|Menu|Open navigation drawer|فتح القائمة)$")
    if not n:
        # أعلى يمين الشاشة غالباً (RTL)
        cands = [k for k in nodes if k["click"] and k["pkg"] == PKG and k["b"][1] < H * 0.1]
        cands.sort(key=lambda k: -k["b"][0])
        n = cands[0] if cands else None
    if n:
        tap_node(n); time.sleep(1.5)
        return parse(dump())
    return []


def phase_menu():
    log("④ القائمة الجانبية")
    nodes = open_menu()
    if not nodes:
        log("⚠ لم تُفتح القائمة"); return
    step("القائمة_الجانبية", force=True)
    swipe("up"); nodes_b = parse(dump()); step("القائمة_الجانبية_تمرير")
    swipe("down")
    rows = []
    seen = set()
    for n in nodes + nodes_b:
        t = label(n)
        if n["click"] and n["pkg"] == PKG and t and t not in seen and not DENY.search(t) and n["b"][1] > H * 0.06:
            seen.add(t); rows.append(t)
    METRICS["menu_rows"] = rows[:40]
    log(f"صفوف القائمة: {rows[:40]}")
    for t in rows[:28]:
        if left() < 18 * 60: break
        try:
            nodes = open_menu()
            n = find(nodes, "^" + re.escape(t) + "$")
            if not n:
                swipe("up"); nodes = parse(dump()); n = find(nodes, "^" + re.escape(t) + "$")
            if not n: continue
            tap_node(n); time.sleep(2.0)
            nodes, _, _ = step(f"قائمة_{t[:24]}", force=True)
            pk, _ = focus()
            if pk == PKG:
                swipe("up"); step(f"قائمة_{t[:24]}_تمرير")
                if re.search(r"الإعدادات|Settings", t):
                    for k in range(7):
                        swipe("up"); _, _, new = step(f"الإعدادات_صفحة_{k+2}")
                        if not new: break
                    nodes3 = parse(dump())
                    toggles = [label(n) for n in nodes3 if (n["check"] or "Switch" in n["cls"]) and label(n)]
                    METRICS.setdefault("settings_toggles", []).extend(toggles)
        except Exception as e:
            EVENTS.append({"t": int(time.time()-T0), "menu_err": t, "err": str(e)[:200]})


# ═══════════ ٥) أوضاعٌ: داكن · خطّ كبير · بلا شبكة · إنجليزية ═══════════
def shots_of_tabs(prefix, limit=5):
    launch(wait=5)
    nodes = parse(dump())
    tabs = bottom_tabs(nodes)
    for i, t in enumerate(tabs[:limit]):
        tap_node(t); time.sleep(1.8)
        step(f"{prefix}_{label(t) or i}", force=True)


def phase_modes():
    log("⑤ الوضع الداكن")
    sh("cmd uimode night yes"); time.sleep(2)
    shots_of_tabs("داكن")
    launch({"openMushaf": "1,images"}, wait=5); step("داكن_المصحف", force=True)
    sh("cmd uimode night no"); time.sleep(2)
    log("⑤ خطّ النظام الكبير 1.3")
    sh("settings put system font_scale 1.3"); time.sleep(2)
    shots_of_tabs("خط_كبير", limit=3)
    launch({"openMushaf": "2,text"}, wait=5); step("خط_كبير_المصحف_نص", force=True)
    sh("settings put system font_scale 1.0"); time.sleep(1)
    log("⑤ بلا شبكة")
    sh("svc wifi disable"); sh("svc data disable"); time.sleep(3)
    launch({"openMushaf": "300,images"}, wait=6); step("بلا_شبكة_مصحف_صفحة_غير_محمّلة", force=True)
    launch({"openAsk": True}, wait=5); step("بلا_شبكة_اسأل", force=True)
    launch({"openReciteWithMe": True}, wait=8); step("بلا_شبكة_سمّع_معي", force=True)
    launch({"openTasmi": True}, wait=8); step("بلا_شبكة_سمّع", force=True)
    launch({"openDaily": True}, wait=5); step("بلا_شبكة_يومي", force=True)
    sh("svc wifi enable"); sh("svc data enable")
    for _ in range(20):
        if "1 received" in sh("ping -c1 -W2 1.1.1.1"): break
        time.sleep(2)


def phase_english():
    log("⑥ الواجهة الإنجليزية (لغة التطبيق)")
    sh(f"cmd locale set-app-locales {PKG} --user 0 --locale-tags en-US")
    time.sleep(2)
    shots_of_tabs("english")
    launch({"openMushaf": "1,images"}, wait=5); step("english_mushaf", force=True)
    launch({"openSupport": True}, wait=5); step("english_support", force=True)
    sh(f"cmd locale set-app-locales {PKG} --user 0 --locale-tags ar-EG")
    time.sleep(2)


# ═══════════ ٧) التسميع بصوتٍ محقون ═══════════
def phase_tasmi(wav):
    if not wav or not os.path.isfile(wav):
        log("⑦ لا ملفَّ صوتٍ للحقن؛ تُتخطّى تجربة التسميع الفعليّة"); return
    log("⑦ التسميع بصوتٍ محقون (الحصري 18:22)")
    adb("push", wav, "/data/local/tmp/inj.wav")
    stop()
    sh(f"run-as {PKG} cp /data/local/tmp/inj.wav files/tasmi_inject.wav")
    got = sh(f"run-as {PKG} stat -c %s files/tasmi_inject.wav").strip()
    METRICS["tasmi_inject_bytes"] = got
    adb("logcat", "-c")
    launch({"setRiwaya": "hafs", "openReciteWithMe": True, "autoRecite": True}, wait=10)
    for k in range(6):
        step(f"سمّع_معي_محقون_{k+1}", force=True)
        time.sleep(12)
    lg = adb("logcat", "-d", "-s", "recite:D", timeout=60)
    lines = [l[:200] for l in lg.splitlines() if re.search(r"audio|locate|locked|done|error|cloud|munsit|engine", l, re.I)]
    METRICS["recite_log_lines"] = len(lines)
    with open(f"{OUT}/recite_log.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines[:400]))
    stop()
    sh(f"run-as {PKG} rm -f files/tasmi_inject.wav")
    # التسميع العاديّ (سمّع) بالصوت نفسه
    adb("push", wav, "/data/local/tmp/inj.wav")
    sh(f"run-as {PKG} cp /data/local/tmp/inj.wav files/tasmi_inject.wav")
    launch({"openTasmi": True}, wait=6)
    nodes, _, _ = step("سمّع_محقون_شاشة", force=True)
    n = find(nodes, r"^(ابدأ|سمّع|ابدأ التسميع|تسجيل|Start|Record)")
    if n:
        tap_node(n); time.sleep(3)
        for k in range(4):
            step(f"سمّع_محقون_{k+1}", force=True); time.sleep(12)
    stop()
    sh(f"run-as {PKG} rm -f files/tasmi_inject.wav")


# ═══════════ ٨) الزحف العامّ بميزانية ═══════════
VISITED = set()


def crawl_screen(root_name, depth, stop_at):
    if time.time() > stop_at or depth > 2:
        return
    nodes = parse(dump())
    sig0 = signature(nodes)
    cands = [n for n in nodes if n["click"] and n["pkg"] == PKG and label(n) and not DENY.search(label(n))
             and n["b"][1] > H * 0.06 and n["b"][1] < H * 0.84]
    for n in cands[:14]:
        if time.time() > stop_at: return
        key = (root_name, depth, label(n)[:40])
        if key in VISITED: continue
        VISITED.add(key)
        tap_node(n); time.sleep(1.6)
        nodes2 = parse(dump())
        if signature(nodes2) == sig0:
            continue
        step(f"زحف_{root_name}_{label(n)[:22]}")
        if depth < 2:
            crawl_screen(f"{root_name}>{label(n)[:12]}", depth + 1, stop_at)
        ensure_in_app(); back()
        if signature(parse(dump())) != sig0:
            back()
            if signature(parse(dump())) != sig0:
                return   # ضاع السياق؛ يعيد المستدعي الإطلاق


def phase_crawl():
    stop_at = ARGS.deadline - 7 * 60
    log(f"⑧ الزحف العامّ ({int((stop_at-time.time())/60)} د متاحة)")
    for name in TAB_NAMES or ["home"]:
        for rnd in range(3):
            if time.time() > stop_at: return
            launch(wait=4)
            nodes = parse(dump())
            t = find(nodes, "^" + re.escape(name) + "$") if TAB_NAMES else None
            if t: tap_node(t); time.sleep(1.5)
            crawl_screen(name, 0, stop_at)


# ═══════════ ٩) قياسات ═══════════
def phase_metrics():
    log("⑨ القياسات")
    colds = []
    for _ in range(3):
        tt = launch(wait=2)
        if tt: colds.append(tt)
    METRICS["cold_start_ms"] = colds
    launch(wait=6)
    for ex in ({"openMushaf": "1,images"}, {"openTasmi": True}, {"openDaily": True}):
        launch(ex, wait=4)
    mem = sh(f"dumpsys meminfo {PKG}")
    mt = re.search(r"TOTAL PSS:\s*(\d+)", mem) or re.search(r"\n\s*TOTAL\s+(\d+)", mem)
    jh = re.search(r"Java Heap:\s*(\d+)", mem)
    METRICS["pss_mb"] = int(mt.group(1)) // 1024 if mt else None
    METRICS["java_heap_mb"] = int(jh.group(1)) // 1024 if jh else None
    with open(f"{OUT}/meminfo.txt", "w") as f: f.write(mem)
    pkgi = sh(f"dumpsys package {PKG} | grep -E 'versionName|versionCode' | head -2")
    METRICS["version"] = " ".join(pkgi.split())
    METRICS["crash_lines"] = crashes()
    lg = adb("logcat", "-d", timeout=90)
    METRICS["anr_count"] = len(re.findall(r"ANR in " + re.escape(PKG), lg))
    err = [l[:200] for l in lg.splitlines() if re.search(r"\b[EF]/?\s", l) and ("mushafak" in l.lower() or "rafiq" in l.lower())]
    METRICS["app_error_lines"] = len(err)
    with open(f"{OUT}/logcat_errors.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(err[:600]))
    with open(f"{OUT}/logcat_tail.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lg.splitlines()[-1500:]))
    du = sh(f"du -sh /data/data/{PKG} 2>/dev/null || run-as {PKG} du -sh . 2>/dev/null")
    METRICS["app_data_size"] = du.strip()[:40]


# ═══════════ التقرير ═══════════
def write_report():
    rep = {"metrics": METRICS, "steps": STEPS, "events": EVENTS, "elapsed_s": int(time.time()-T0)}
    with open(f"{OUT}/walk_report.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    L = ["# 🚶 جولة الواجهة على المحاكي — التقرير الخام", "",
         f"- الخطوات المصوّرة: {len(STEPS)} · الزمن: {int(time.time()-T0)//60} د · الأحداث: {len(EVENTS)}",
         f"- القياسات: `{json.dumps({k: v for k, v in METRICS.items() if k not in ('crash_lines',)}, ensure_ascii=False)[:1500]}`",
         f"- الانهيارات: {len(METRICS.get('crash_lines', []))}", ""]
    for c in METRICS.get("crash_lines", [])[:10]:
        L.append(f"  - `{c}`")
    L += ["", "| # | الشاشة | النشاط | نصوص | أزرار | انهيار | أوّل النصوص |", "|---|---|---|---|---|---|---|"]
    for s in STEPS:
        L.append(f"| {s['i']} | {s['name']} | {s['focus'].split('/')[-1]} | {len(s['texts'])} | {len(s['clickables'])} | {s['crash'] or ''} | {' · '.join(s['texts'][:8])[:160]} |")
    with open(f"{OUT}/walk_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L))


PHASES = [
    ("launch", phase_launch), ("tabs", phase_tabs), ("intents", phase_intents), ("menu", phase_menu),
    ("tasmi", lambda: phase_tasmi(ARGS.wav)), ("modes", phase_modes), ("english", phase_english),
    ("crawl", phase_crawl), ("metrics", phase_metrics),
]
for pname, fn in PHASES:
    if left() < 5 * 60 and pname not in ("metrics",):
        log(f"⏳ تخطّي {pname}: لم يبقَ وقت"); continue
    try:
        fn()
    except Exception as e:
        EVENTS.append({"t": int(time.time()-T0), "phase_err": pname, "err": str(e)[:300]})
        log(f"⚠ مرحلة {pname} تعثّرت: {e}")
    write_report()
write_report()
log(f"✅ انتهت الجولة: {len(STEPS)} لقطة")
