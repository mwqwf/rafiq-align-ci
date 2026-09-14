# -*- coding: utf-8 -*-
"""🛡️ **حارسُ الترويسة** — أداةٌ تُنزّل بلا وسمِ وكيلٍ تسقط بـ403 عند `r2.dev`.

⛔ **لِمَ وُجد — عطبٌ وقع ثلاثَ مرّاتٍ مكتوباتٍ في دفتر الأعطاب:** «`fetch_retry` بلا ترويسة
وكيل ⇒ **403** من `r2.dev` (درسٌ متكرّر للمرة الثالثة)». وعلاجُه في كلّ مرّةٍ كان **موضعيّاً**
في الدالّة التي عضّت — ولم يُسأل قطُّ: **ومَن غيرُها ينزّل بلا ترويسة؟** فهذا الحارسُ يسأله.

⭐ **وأخطرُ صورةٍ `urlretrieve`**: لا تقبل ترويسةً أصلاً (تفتح بالوسم الافتراضيّ
`Python-urllib/x.y`) ⇒ **لا يكفي أن تُراجَع، يجب أن تُستبدَل**. وقِيس اليومَ (2026-09-14):
**أربعةُ مواضعَ** منها في العدّة، كلُّها تنزّل روابطَ خطّةٍ قد تكون من `r2.dev`.

⛔⛔ **وصفرُ ملفّاتٍ ليس سلامةً** (‏D-442): إن لم يُقرأ ملفٌّ واحدٌ (مسارٌ خطأٌ أو مجلّدٌ فارغ)
**يُردّ برمزٍ** ولا يُطبع «✅»؛ ويُطبع مع كلّ حكمٍ **عددُ ما فُحص** فلا تُقرأ خضرةٌ بلا سندها.

⚠️ **وحدُّ الحارس مكتوبٌ:** فحصٌ **نصّيٌّ** لا تنفيذ — يقرأ النداءَ وما يليه في السطور القليلة،
فيُمسك الصورَ الشائعةَ لا كلَّ صورةٍ ممكنة (وسيطٌ يُبنى في دالّةٍ أخرى مثلاً). ⇒ **صفرُ ملاحظةٍ
ليس شهادةَ سلامةٍ مطلقة**، وإنّما «لا صورةَ معروفةً باقية».

    python tools/tasmi_bench/net_guard.py tools/tasmi_bench tools/finetune
    python tools/tasmi_bench/net_guard.py --selftest
"""
import argparse
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# نداءاتٌ تُنزّل: `urlretrieve` (‏لا ترويسةَ لها بحال) · و`urlopen` (‏ترويستُها من `Request`).
RETRIEVE = re.compile(r"\burlretrieve\s*\(")
URLOPEN = re.compile(r"\burlopen\s*\(")
REQUEST = re.compile(r"\bRequest\s*\(")
HEADERS = re.compile(r"headers\s*=")
UA_HINT = re.compile(r"User-Agent|\bUA\b|Mozilla")
# سطرٌ يُنشئ `Request` بمتغيّرٍ ثمّ يُمرَّر لاحقاً — يُتتبَّع باسمه في السطور القليلة قبله.
ASSIGN_REQ = re.compile(r"(\w+)\s*=\s*.*\bRequest\s*\(")

FATAL = {
    "retrieve_no_ua": "⛔ `urlretrieve` — **لا تقبل ترويسةً أصلاً** ⇒ 403 عند `r2.dev`",
    "urlopen_bare_url": "⛔ `urlopen` على عنوانٍ نصّيٍّ مباشرةً (بلا `Request`) ⇒ بلا ترويسة",
    "request_no_headers": "⛔ `Request(...)` بلا `headers=` ⇒ الوسمُ الافتراضيُّ",
}


def scan_text(text, lookback=6):
    """يفحص نصَّ ملفٍّ ويعيد [(السطر، الرمز، النصّ)] — والفحصُ نصّيٌّ بحدّه المكتوب أعلاه."""
    out = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("#"):
            continue                      # شرحٌ لا شفرة (ومنه أمثلةُ هذا الملفّ نفسِه)
        if RETRIEVE.search(s):
            out.append((i + 1, "retrieve_no_ua", s))
            continue
        if not URLOPEN.search(s):
            if REQUEST.search(s) and not HEADERS.search(s):
                # `Request` يُبنى وحدَه في سطرٍ (أو سطرَين) بلا ترويسة — يُقرأ ما بعده أيضاً.
                nxt = " ".join(x.strip() for x in lines[i + 1:i + 3])
                if not HEADERS.search(nxt):
                    out.append((i + 1, "request_no_headers", s))
            continue
        # ① `urlopen(Request(...))` في السطر نفسِه: تُطلب الترويسةُ فيه أو في تاليه.
        if REQUEST.search(s):
            nxt = " ".join(x.strip() for x in lines[i + 1:i + 3])
            if not (HEADERS.search(s) or HEADERS.search(nxt)):
                out.append((i + 1, "request_no_headers", s))
            continue
        # ② `urlopen(x, …)`: إن كان `x` متغيّرَ `Request` بُني قريباً فحكمُه حكمُ بنائه،
        #    وإن كان **نصّاً أو متغيّرَ عنوانٍ** فلا ترويسةَ له.
        inner = s[s.index("urlopen") + len("urlopen"):]
        m = re.match(r"\s*\(\s*([A-Za-z_]\w*)", inner)
        if m:
            name = m.group(1)
            back = lines[max(0, i - lookback):i]
            built = [b for b in back if re.search(rf"\b{name}\s*=\s*.*Request\s*\(", b)]
            if built:
                continue                  # بُني `Request` بمتغيّره — وحكمُه حيث بُني
            if re.search(rf"\b{name}\s*=", " ".join(back)) or name in ("url", "u", "src"):
                out.append((i + 1, "urlopen_bare_url", s))
            continue
        if re.match(r"\s*\(\s*[\"'f]", inner):
            out.append((i + 1, "urlopen_bare_url", s))
    return out


def scan_paths(paths):
    """يفحص ملفّاتِ `.py` في المسارات ويعيد (المسار → الملاحظات) — و**عدُّ ما فُحص** يُعاد معها.

    ⛔⛔ **ولا خضرةَ بلا شهادة** (‏D-442): كان الفاحصُ يطبع «✅ لا صورةَ معروفةً باقية» ويخرج
    بصفرٍ **ولو لم يقرأ ملفّاً واحداً** (مسارٌ خطأٌ أو مجلّدٌ فارغ) — وهو العطبُ نفسُه الذي وقع
    في `judge_parity` (صفرُ كلماتٍ ⇒ «✅ صفرُ انحراف»). **فصفرُ ملفّاتٍ غيابُ قياسٍ لا سلامة.**
    """
    found = {}
    scanned = 0
    for p in paths:
        files = []
        if os.path.isdir(p):
            for root, _d, names in os.walk(p):
                files += [os.path.join(root, n) for n in sorted(names) if n.endswith(".py")]
        elif p.endswith(".py"):
            files = [p]
        for f in files:
            if os.path.basename(f) == os.path.basename(__file__):
                continue                  # الحارسُ نفسُه: أمثلتُه نصوصٌ لا نداءات
            scanned += 1
            hits = scan_text(open(f, encoding="utf-8", errors="replace").read())
            if hits:
                found[f] = hits
    return found, scanned


def selftest():
    bad = 0

    def ok(name, got, want):
        nonlocal bad
        good = got == want
        print(f"  {'✅' if good else '⛔'} {name}: {got} · المتوقَّع {want}")
        bad += 0 if good else 1

    codes = lambda t: [c for _l, c, _s in scan_text(t)]   # noqa: E731

    # ⛔ الصورةُ التي عضّت ثلاثَ مرّات.
    ok("`urlretrieve` يُمسَك", codes('urllib.request.urlretrieve(it["url"], mp3)'),
       ["retrieve_no_ua"])
    ok("والسليمُ يمرّ",
       codes('with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:'), [])
    ok("و`Request` بلا ترويسةٍ يُمسَك",
       codes('req = urllib.request.Request(url, method="HEAD")'), ["request_no_headers"])
    # ⭐ والترويسةُ في السطر التالي **تُقرأ** (‏نمطُنا الشائع: نداءٌ على سطرَين).
    ok("وترويسةٌ في السطر التالي تُقبل", codes(
        'req = urllib.request.Request(src["url"], method="HEAD",\n'
        '                             headers={"User-Agent": "Mozilla/5.0"})'), [])
    ok("و`urlopen` على نصٍّ مباشرةً", codes('urllib.request.urlopen("https://x/y.mp3")'),
       ["urlopen_bare_url"])
    ok("و`urlopen` على متغيّر عنوانٍ", codes('url = plan["url"]\nurllib.request.urlopen(url, timeout=30)'),
       ["urlopen_bare_url"])
    # ⭐ ومتغيّرُ `Request` بُني قبله بترويسة ⇒ **لا يُنذَر** (وإلّا صار الحارسُ يصرخ بما لا يضرّ).
    ok("ومتغيّرٌ بُني `Request`اً قبله لا يُنذَر", codes(
        'req = urllib.request.Request(url, headers=UA)\n'
        'with urllib.request.urlopen(req, timeout=30) as r:'), [])
    ok("والشرحُ ليس شفرةً", codes('# urllib.request.urlretrieve(url, dst)  مثالٌ في شرح'), [])
    ok("وسطرٌ لا شبكةَ فيه", codes('x = 1 + 2'), [])
    # ⚠️ وحدٌّ يُقال: عنوانٌ يُبنى في دالّةٍ أخرى ويُمرَّر ⇒ **لا يراه الفحصُ النصّيّ**.
    ok("وحدُّه المكتوب: نداءٌ غيرُ مباشرٍ لا يُرى", codes('fetch(url, dst)'), [])

    # ---- ⛔ ولا خضرةَ بلا شهادة: صفرُ ملفّاتٍ **ليس سلامةً** (D-442) ----
    import tempfile
    empty = tempfile.mkdtemp()
    ok("مجلّدٌ بلا ملفّاتٍ ⇒ صفرُ مفحوص", scan_paths([empty])[1], 0)
    ok("ومسارٌ لا وجودَ له ⇒ صفرُ مفحوص", scan_paths(["/لا/وجود/له"])[1], 0)
    ok("وملفٌّ واحدٌ يُعَدّ مفحوصاً",
       scan_paths([os.path.join(os.path.dirname(os.path.abspath(__file__)), "score.py")])[1], 1)

    print("✅ الحارسُ سليمٌ على حالاته" if not bad else f"⛔ الحارسُ نفسُه معطوبٌ في {bad} حالة")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="مجلّداتٌ أو ملفّاتُ بايثون")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    found, scanned = scan_paths(a.paths or ["tools/tasmi_bench"])
    print("# 🛡️ حارسُ الترويسة — ما يُنزّل بلا وسمِ وكيل\n")
    n = sum(len(v) for v in found.values())
    if not scanned:
        print("⛔ **صفرُ ملفّاتٍ فُحصت — ولا يُقرأ هذا سلامةً**: أخطأ المسارُ أم المجلّدُ فارغ؟")
        return 1
    print(f"<sub>فُحص **{scanned}** ملفَّ بايثون.</sub>\n")
    if not found:
        print("✅ لا صورةَ معروفةً باقية. ⚠️ وهذا «لا صورةَ معروفة» لا «سلامةٌ مطلقة».")
        return 0
    print("| الملفّ | السطر | الحكم |\n|---|---:|---|")
    for f, hits in sorted(found.items()):
        for line, code, _s in hits:
            print(f"| `{os.path.basename(f)}` | {line} | {FATAL.get(code, code)} |")
    print(f"\n**الحصيلة: {n} موضعاً** — وكلُّ موضعٍ **403 ينتظر** عند `r2.dev`.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

# 🧪 مسبارُ زناد (10:20Z): أتشتعل `bench-selftest` على دفعةٍ بلا وسمِ تخطٍّ؟ — قياسٌ لا ظنّ.
