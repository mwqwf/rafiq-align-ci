# -*- coding: utf-8 -*-
"""📦 **حارسُ عناوين النماذج وأحجامها** — يقرأ `WhisperModelStore.Variant` ويقابلها بـR2.

⛔ **لِمَ وُجد:** `WhisperModelStore.ensure` **يرفض الملفَّ إن خالف الحجمُ المعلَن** — وهو حارسٌ
صحيحٌ (‏درسُ بصمات منبر: نصفُ ملفٍّ لا يُحسب نموذجاً). لكنّ أثرَه الجانبيّ أنّ **رفعَ نموذجٍ
مُعاداً بحجمٍ يختلف بايتاً واحداً يُعطّل التنزيلَ إلى الأبد** لكلّ مستخدم: يُنزَّل كاملاً ثمّ
يُرفض ثمّ يُمحى ثمّ يُعاد… بلا رسالةٍ تقول السبب. ⇒ **عطبٌ كامل، صامت، وعلى شبكة المستخدم.**

والفحصُ رخيص: `HEAD` واحدٌ لكلّ نموذج (‏لا تنزيل) — فيُشغَّل قبل أيّ إصدار.

    python tools/tasmi_bench/model_urls_check.py            # HEAD: العنوانُ والحجم
    python tools/tasmi_bench/model_urls_check.py --sha      # تنزيلٌ تدفّقيٌّ ⇒ `sha256`
    python tools/tasmi_bench/model_urls_check.py --selftest # بلا شبكة

⚠️ وهو **لا يصلح اختباراً وحدةً**: يمسّ الشبكة، والاختباراتُ لا تمسّها. فبقي أداةً تُشغَّل.
"""
import io
import os
import re
import sys
import urllib.request

# ⛔ **أداةٌ تُشغَّل بلا بيئةٍ مضبوطة تفرض ترميزَها بنفسها** — وقع هذا مرّتين الليلةَ: تسقط
# الأداةُ بـ`UnicodeEncodeError` على رسالةِ **نجاحها** فيُظنّ العطبُ في المفحوص لا في الفاحص.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.join(HERE, "..", "..", "engine", "recitation", "src", "main", "kotlin",
                  "com", "ali", "rafiq", "recitation", "WhisperModelStore.kt")
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq model check)"}   # r2.dev يردّ 403 على الوكيل الافتراضي


def variants(path):
    """(اسمٌ، عنوانٌ، حجمٌ معلَن) لكلّ قيمةٍ في `enum class Variant`."""
    src = io.open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"^\s{8}([A-Z_0-9]+)\(\s*$", src, re.M):
        name = m.group(1)
        body = src[m.end():src.index("),", m.end()) + 2]
        url = "".join(re.findall(r'"([^"]*)"', body.split("url =", 1)[1].split("bytes", 1)[0])) \
            if "url =" in body else None
        b = re.search(r"bytes\s*=\s*([\d_]+)L", body)
        if url and b:
            out.append((name, url, int(b.group(1).replace("_", ""))))
    return out


def sha_of(url, timeout=300, chunk=1 << 20):
    """بصمةُ ملفٍّ بعيدٍ **بلا حفظه**: تُقرأ تدفّقاً وتُحسب `sha256` مع عدّ البايتات.

    ⛔ **ولِمَ يلزم هذا أصلاً:** `WhisperModelStore` يعتمد الملفَّ **بالحجم وحدَه**
    (`length() == variant.bytes`) ولا بصمةَ فيه. فملفٌّ بالحجم الصحيح ومحتوًى تالفٍ
    (‏استئنافٌ أَلحقَ بايتاتٍ بعد زبدِ بوّابةٍ أسيرة · أو وسيطٌ خلط الجسمَ) **يُقبل
    نموذجاً** فيُحمَّل في whisper ⇒ **أحكامٌ هَراءٌ للمستخدم بلا رسالةٍ واحدة**.
    والبصمةُ لا تُكتب في الشفرة إلا إن **قِيست** — وهذه الدالّةُ تقيسها.
    """
    import hashlib
    h = hashlib.sha256()
    n = 0
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        while True:
            b = r.read(chunk)
            if not b:
                break
            h.update(b)
            n += len(b)
    return h.hexdigest(), n


def sha_report():
    """جدولُ بصماتٍ يُقرأ ثمّ **يُنقل بيدٍ** إلى `Variant` — ولا يُكتب رقمٌ لم يُقَس."""
    vs = variants(KT)
    if not vs:
        raise SystemExit("⛔ لم يُقرأ نموذجٌ واحدٌ من الشفرة — القارئُ تعطّل")
    bad = 0
    print("| النموذج | الحجمُ المنزَّل | المعلَنُ في الشفرة | `sha256` | الحكم |")
    print("|---|---:|---:|---|:-:|")
    for name, url, declared in vs:
        try:
            digest, n = sha_of(url)
        except Exception as e:
            print(f"| `{name}` | ⛔ {type(e).__name__} | {declared:,} | — | ⛔ |")
            bad += 1
            continue
        ok = n == declared
        bad += 0 if ok else 1
        print(f"| `{name}` | {n:,} | {declared:,} | `{digest}` | {'✅' if ok else '⛔'} |")
    print("\n⭐ **وتُنقل البصماتُ إلى `WhisperModelStore.Variant` بيدٍ** مع سطرٍ يقول متى "
          "قِيست — فيصير رفضُ الملفِّ التالف ممكناً، وهو اليومَ **غيرُ ممكن**: الحجمُ وحدَه "
          "لا يكشف تلفاً بالحجم نفسِه.")
    if bad:
        print("⛔ وحجمٌ لا يطابق المعلَن ⇒ **لا تُنقل بصمتُه**: الملفُّ أو الشفرةُ يُصحَّح أوّلاً.")
    return 1 if bad else 0


def selftest():
    """يفحص الحسابَ على ملفٍّ محلّيٍّ معلومِ البصمة — بلا شبكة."""
    import hashlib
    import tempfile
    data = b"rafiq" * 1000
    want = hashlib.sha256(data).hexdigest()
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "m.bin")
        with open(f, "wb") as fh:
            fh.write(data)
        got, n = sha_of("file://" + f)
    ok = got == want and n == len(data)
    print(f"{'✅' if ok else '⛔'} بصمةُ ملفٍّ محلّيّ: {got[:16]}… · {n} بايتاً · المنتظر {want[:16]}…")
    # ⛔ وضابطٌ سالبٌ: بايتٌ واحدٌ يتغيّر ⇒ بصمةٌ أخرى (وإلّا فالحسابُ لا يحسب)
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "m.bin")
        with open(f, "wb") as fh:
            fh.write(data[:-1] + b"X")
        got2, _ = sha_of("file://" + f)
    ok2 = got2 != got
    print(f"{'✅' if ok2 else '⛔'} وبايتٌ واحدٌ يغيّر البصمة: {got2[:16]}…")
    # ⛔ وقارئُ الشفرة يجب أن يقرأ النماذجَ الثلاثةَ بأحجامها (‏لا صفراً يُقرأ نجاحاً)
    vs = variants(KT) if os.path.exists(KT) else []
    ok3 = len(vs) >= 3 and all(u.startswith("https://") and b > 1_000_000 for _n, u, b in vs)
    print(f"{'✅' if ok3 else '⛔'} وقارئُ `Variant` يقرأ {len(vs)} نموذجاً بعنوانٍ وحجمٍ معقولَين"
          + ("" if os.path.exists(KT) else " (‏لا شفرةَ محرّكٍ هنا — يُقرأ «لم يُفحَص»)"))
    if not os.path.exists(KT):
        ok3 = True
    good = ok and ok2 and ok3
    print("✅ الحسابُ سليمٌ على حالاته." if good else "⛔ سقط ضابطُ الحساب")
    return 0 if good else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--sha" in sys.argv:
        return sha_report()
    vs = variants(KT)
    if not vs:
        raise SystemExit("⛔ لم يُقرأ نموذجٌ واحدٌ من الشفرة — القارئُ تعطّل ولا يُقرأ الصفرُ نجاحاً")
    bad = 0
    print("| النموذج | HTTP | الحجمُ على R2 | المعلَنُ في الشفرة | الحكم |")
    print("|---|---:|---:|---:|:-:|")
    for name, url, declared in vs:
        try:
            req = urllib.request.Request(url, method="HEAD", headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                code = r.status
                actual = int(r.headers.get("Content-Length", -1))
        except Exception as e:
            print(f"| `{name}` | ⛔ {type(e).__name__} | — | {declared:,} | ⛔ |")
            bad += 1
            continue
        ok = code == 200 and actual == declared
        bad += 0 if ok else 1
        print(f"| `{name}` | {code} | {actual:,} | {declared:,} | {'✅' if ok else '⛔'} |")
    if bad:
        print(f"\n⛔ **{bad} نموذجاً لا يطابق.** والأثرُ على المستخدم: تنزيلٌ كاملٌ ثمّ رفضٌ "
              "ثمّ إعادةٌ بلا نهاية — فصحّح الحجمَ في الشفرة أو أعد رفعَ الملفّ.")
        return 1
    print(f"\n✅ {len(vs)} نماذجَ: العنوانُ يستجيب والحجمُ يطابق المعلَن بايتاً ببايت.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
