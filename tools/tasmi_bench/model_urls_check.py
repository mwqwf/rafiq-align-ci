# -*- coding: utf-8 -*-
"""📦 **حارسُ عناوين النماذج وأحجامها** — يقرأ `WhisperModelStore.Variant` ويقابلها بـR2.

⛔ **لِمَ وُجد:** `WhisperModelStore.ensure` **يرفض الملفَّ إن خالف الحجمُ المعلَن** — وهو حارسٌ
صحيحٌ (‏درسُ بصمات منبر: نصفُ ملفٍّ لا يُحسب نموذجاً). لكنّ أثرَه الجانبيّ أنّ **رفعَ نموذجٍ
مُعاداً بحجمٍ يختلف بايتاً واحداً يُعطّل التنزيلَ إلى الأبد** لكلّ مستخدم: يُنزَّل كاملاً ثمّ
يُرفض ثمّ يُمحى ثمّ يُعاد… بلا رسالةٍ تقول السبب. ⇒ **عطبٌ كامل، صامت، وعلى شبكة المستخدم.**

والفحصُ رخيص: `HEAD` واحدٌ لكلّ نموذج (‏لا تنزيل) — فيُشغَّل قبل أيّ إصدار.

    python tools/tasmi_bench/model_urls_check.py

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


def main():
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
