#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يكتب في الكتالوج **تغطيةَ كل قارئ وشهادتَه** (D-220) — محسوبةً من الدلو لا بيد.

    python tools/index_qa/certify_catalog.py            # عرضٌ فقط
    python tools/index_qa/certify_catalog.py --yes      # يكتب catalog/reciters.json
    python tools/index_qa/certify_catalog.py --self-test

**لماذا** (‏أمر المشرف github-10، 2026-09-05): كشف فحصُ P1 أنّ 26 فهرساً مخدوماً
تغطيتُها 29–95% وهي معدودةٌ «داعمةً لآية-آية»، فيرى المستخدمُ قارئاً في القائمة
ثم لا يجد ثلثَ المصحف عنده. ⇒ الحقلان يجعلان **الواجهة تعرف ما تعرفه البوابة**:

- `ayahCoverage`: نسبةُ مداخل الفهرس المخدوم إلى عدّ الرواية (‏1.0 لمن صوتُه
  مقطَّعٌ آيةً آية أصلاً).
- `ayahCertified`: **صحيحٌ فقط** باجتماع شروط D-220 الثلاثة — تغطيةٌ ≥98%،
  وبلا فشلٍ بنيويّ، **وحكمُ بوابةٍ على البصمة المخدومة نفسها**.

⛔ **حارسٌ يُسقط التوليد كلَّه** (لا يُصلَح بصمت): إن خرج قارئٌ `certified=true`
وليس لبصمته المخدومة حكم، **يُوقَف الكتابة** ويُبلَّغ — لأن شهادةً بلا حكمٍ هي
بعينها العطبُ الذي وُضع الحقلُ ليمنعه.

⛔ **ولا يُغيّر هذا الملفُّ شيئاً غير الحقلين**: يُقارَن الكتالوجُ قبل وبعد،
فإن اختلف حقلٌ ثالثٌ يُوقَف.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import promote  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

CATALOG_KEY = "catalog/reciters.json"
MIN_COV = 0.98
CERTIFIER = "certify_catalog-1.1"

# ⛔ **أثرُ إسقاطٍ معلَن، لا عطبٌ**: من رُقّي بـ`--allow-truncated` يبقى فحصُه
#    الصوتيُّ يطبع هذه الثلاثة أبداً، لأن السورةَ المحذوفةَ بقرارٍ **غائبةٌ
#    حقّاً**. فهي نتيجةُ القرار لا خللٌ فيه، وعدُّها رفضاً ينزع الشهادةَ عن
#    أربعةٍ رُقّوا بحقّ (‏قِيس بالأسماء: `arkani` · `balilah` · `kurdi` · `wdod`).
DECLARED_DROP_FATALS = (
    "سور غائبة كلياً",
    "الغياب منحازٌ إلى القصار",
    "وسم الاكتمال يخالف الحساب",
)


def undeclared_fatal(fatals, transform_op):
    """هل في الفواتل ما **ليس** أثراً لإسقاطٍ معلَن؟ (‏فيكون عطباً حقيقيّاً)

    ⛔ **سببُ الدالّة مقيسٌ لا مفترَض** (2026-09-07): البصمةُ المخدومة من
    `koshi_warsh` (‏`cd973a9e`) رُدّت **3 من 3 موجات** بفواتلَ صوتيةٍ مؤكَّدة
    (بسملةٌ مبتلعةٌ في 37:1 و47:1 و108:1) و`transform` فيها **فارغ** — أي لا
    إسقاطَ معلَناً يبرّرها — **ومع ذلك شُهدت** لأن الشرط (أ) في D-220 يسأل عن
    **وجودِ** ملفِّ حكمٍ يحمل البصمة ولا يقرأ ما فيه. فوصلت المستخدمَ بوسم
    «آية-آية» وهي بعينها العطبُ الذي وُضع الحقلُ ليمنعه.
    """
    if not fatals:
        return False
    declared = str(transform_op or "").startswith("drop_surah")
    for f in fatals:
        f = str(f)
        if declared and any(f.startswith(p) for p in DECLARED_DROP_FATALS):
            continue
        return True
    return False


def certify(cat, served, verdict_shas, rejected_shas=frozenset()):
    """يُرجع (الكتالوجُ الجديد، إحصاء) — دالّةٌ نقيّةٌ تُختبر بلا شبكة."""
    stat = {"certified": 0, "total": 0, "byRiwaya": {}}
    for r in cat.get("riwayat", []):
        rid = r["id"]
        for x in r.get("reciters", []):
            stat["total"] += 1
            key = f"timings/{rid}/{x['id']}.jz"
            if x.get("mode") == "ayah":
                cov, cert = 1.0, True
            elif key in served:
                n, tot, sha, fatal = served[key]
                cov = round(n / max(1, tot), 4)
                cert = bool(cov >= MIN_COV and not fatal
                            and sha in verdict_shas and sha not in rejected_shas)
            else:
                cov, cert = 0.0, False
            x["ayahCoverage"] = cov
            x["ayahCertified"] = cert
            b = stat["byRiwaya"].setdefault(rid, [0, 0])
            b[1] += 1
            if cert:
                stat["certified"] += 1
                b[0] += 1
    cat["certifiedBy"] = CERTIFIER
    return cat, stat


def _self_test() -> None:
    cat = {"riwayat": [{"id": "hafs", "reciters": [
        {"id": "a", "mode": "ayah"},
        {"id": "b", "mode": "surah"},          # تغطيةٌ كاملةٌ وحكم ⇒ شهادة
        {"id": "c", "mode": "surah"},          # تغطيةٌ ناقصة ⇒ لا
        {"id": "d", "mode": "surah"},          # تغطيةٌ كاملةٌ بلا حكم ⇒ لا
        {"id": "e", "mode": "surah"},          # لا فهرسَ أصلاً ⇒ لا
    ]}]}
    served = {"timings/hafs/b.jz": (6236, 6236, "SHB", False),
              "timings/hafs/c.jz": (3000, 6236, "SHC", False),
              "timings/hafs/d.jz": (6236, 6236, "SHD", False)}
    out, st = certify(json.loads(json.dumps(cat)), served, {"SHB", "SHC"})
    got = {x["id"]: (x["ayahCoverage"], x["ayahCertified"])
           for x in out["riwayat"][0]["reciters"]}
    assert got["a"] == (1.0, True), "ayah أصلاً يُشهد"
    assert got["b"] == (1.0, True), "تغطيةٌ كاملةٌ وحكمٌ ⇒ شهادة"
    assert got["c"][1] is False, "التغطيةُ الناقصة تُسقط الشهادة"
    assert got["d"][1] is False, "⛔ حكمٌ غائبٌ يُسقط الشهادة ولو كانت التغطيةُ كاملة"
    assert got["e"] == (0.0, False), "بلا فهرسٍ لا شهادة"
    # الفشلُ البنيويّ يُسقط الشهادة ولو تمّت التغطيةُ ووُجد الحكم
    served2 = dict(served); served2["timings/hafs/b.jz"] = (6236, 6236, "SHB", True)
    out2, _ = certify(json.loads(json.dumps(cat)), served2, {"SHB"})
    assert out2["riwayat"][0]["reciters"][1]["ayahCertified"] is False, "الفشلُ البنيويّ يُسقط"
    print("  ✅ الشروطُ الثلاثة كلٌّ منها يُسقط الشهادةَ وحده، والمجتمِعُ يُشهد")

    # ── الشرطُ الرابع: حكمٌ **مقروء** لا حكمٌ **موجود** ────────────────────
    out3, _ = certify(json.loads(json.dumps(cat)), served, {"SHB"}, {"SHB"})
    assert out3["riwayat"][0]["reciters"][1]["ayahCertified"] is False, \
        "⛔ بصمةٌ حكمُها فاتلٌ غيرُ معلَنٍ لا تُشهد ولو وُجد ملفُّ حكمها"
    assert out3["riwayat"][0]["reciters"][0]["ayahCertified"] is True, \
        "و`mode=ayah` لا يمسّه الشرطُ الرابع"
    # وتمييزُ الإسقاط المعلَن عن العطب — وهو مربطُ الفرس:
    assert undeclared_fatal(["سور غائبة كلياً: 1 → [106]"], "drop_surah:106") is False, \
        "أثرُ إسقاطٍ معلَنٍ ليس عطباً"
    assert undeclared_fatal(["سور غائبة كلياً: 1 → [106]"], "") is True, \
        "⛔ وغيابٌ بلا إسقاطٍ معلَنٍ عطبٌ"
    assert undeclared_fatal(["بسملة مبتلعة في 37:1 — مؤكَّدة بالصوت"], "drop_surah:108") is True, \
        "⛔ والبسملةُ المبتلعة عطبٌ ولو كان في الفهرس إسقاطٌ معلَنٌ لسورةٍ أخرى"
    assert undeclared_fatal([], "") is False, "بلا فاتلٍ لا مانع"
    print("  ✅ الشرطُ الرابع يفصل **أثرَ الإسقاط المعلَن** عن **العطب المقيس**")
    print(f"✅ --self-test أخضر · {CERTIFIER}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        _self_test()
        return

    cl, bucket = promote.s3()
    pg = cl.get_paginator("list_objects_v2")
    keys, sizes = [], {}
    for p in pg.paginate(Bucket=bucket, Prefix="timings/"):
        for o in p.get("Contents", []):
            if o["Key"].endswith(".jz"):
                keys.append(o["Key"])
                sizes[o["Key"]] = o["Size"]

    def load(k, tries=4):
        # ⛔ **شبكةُ المالك ضعيفةٌ ومتقطّعة** (قاعدةٌ ثابتة): جرُّ 110 فهارسَ
        #    باثني عشر خيطاً يخنقها فتسقط الأداةُ كلُّها بـReadTimeout —
        #    فالخيوطُ أربعةٌ وللقراءة تراجعٌ أُسّي، والفشلُ بعد المحاولات
        #    يُرفع لا يُبتلع.
        for i in range(tries):
            try:
                raw = cl.get_object(Bucket=bucket, Key=k)["Body"].read()
                # ⛔ **القراءةُ المبتورةُ صامتةٌ وأخطرُ من الفشل**: جسمٌ ناقصٌ
                #    يعطي **بصمةً أخرى** فلا تُطابق حكمَه، ويعطي **عددَ مداخلَ
                #    أقلّ** فتهبط تغطيتُه. والفشلُ يُرى والنقصُ يُكتب حكماً
                #    كاذباً. ⇒ يُقارَن الطولُ بالمعلَن.
                # ⚠️ **تصحيحٌ لسببٍ كُتب هنا** (جنديّ الفهرسة 2026-09-07 05:4xZ):
                #    نُسب سقوطُ شهادة `koshi_warsh` إلى قراءةٍ مبتورة، وليس منه
                #    في شيء — **أنا نزعتُها قصداً** بالشرط الرابع أدناه، وهو
                #    **ليس مستوفياً**: بصمتُه المخدومة `cd973a9e` رُدّت **3 من 3
                #    موجات** بفواتلَ صوتيةٍ مؤكَّدة (37:1 · 47:1 · 108:1) بلا
                #    إسقاطٍ معلَنٍ يبرّرها. والحارسُ أدناه صحيحٌ في نفسه فيبقى.
                if sizes.get(k) is not None and len(raw) != sizes[k]:
                    raise IOError(f"جسمٌ مبتور: {len(raw)} من {sizes[k]}")
                break
            except Exception:                             # noqa: BLE001
                if i == tries - 1:
                    raise
                time.sleep(2 ** i)
        d = json.load(gzip.open(io.BytesIO(raw), "rt", encoding="utf-8"))
        fatal = bool((d.get("qa") or {}).get("fatal"))
        op = (d.get("transform") or {}).get("op") or ""
        return k, (len(d.get("entries") or []), d.get("ayahCount") or 6236,
                   hashlib.sha256(raw).hexdigest(), fatal), op
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(load, keys))
    served = {k: v for k, v, _ in rows}
    # بصمةٌ ⇐ `transform.op` — لتمييز الإسقاط المعلَن عن العطب في الشرط الرابع.
    op_of = {v[2]: op for _, v, op in rows}

    # ⛔ **لا تُسقَط شهادةٌ بقراءةٍ ناقصة**: قراءةٌ ناقصةٌ لقائمة الأحكام
    #    (‏شبكةٌ متقطّعة) تُظهر الحكمَ غائباً وهو حاضر. والنقصُ الصامت أخطرُ من
    #    الفشل: الفشلُ يُرى، والنقصُ يُكتب حكماً كاذباً. (⚠️ ولم يقع هذا على
    #    `koshi_warsh` كما كُتب هنا أوّلاً — انظر التصحيح في `load` أعلاه.)
    #    ⇒ يُقارَن عددُ الأحكام بالجولة السابقة، فإن هبط هبوطاً حادّاً يُوقَف.
    shas = set()
    try:
        for p in pg.paginate(Bucket=bucket, Prefix="state/"):
            for o in p.get("Contents", []):
                shas.add(o["Key"])
    except Exception as error:                            # noqa: BLE001
        sys.exit(f"⛔ تعذّرت قراءةُ قائمة الأحكام كاملةً ({type(error).__name__}) "
                 "— لا تُكتب شهادةٌ على قراءةٍ ناقصة")
    if len(shas) < 500:
        sys.exit(f"⛔ قائمةُ الأحكام {len(shas)} سطراً فقط — قراءةٌ ناقصةٌ يقيناً، "
                 "ولا تُسقَط شهادةٌ بها")
    # الحكمُ يُنسب إلى البصمة: مفتاحُ الحالة يحمل بادئتَها الثمانية.
    verdict_shas = {s for _, (_, _, s, _) in served.items()
                    if any(s[:8] in k for k in shas)}

    # ── الشرطُ الرابع: يُقرأ ما في ملفّ الحكم لا وجودُه وحدَه ──────────────
    # ⛔ **والقراءةُ للفواتل وحدَها**: أما «مرفوض (عطبٌ جسيم %)» فمقياسٌ عيّنيّ
    #    يتقلّب بالملح، وتجميعُه شأنُ D-109 في `promote.py` لا شأنُ هذا الملفّ —
    #    ومن عدّ كلَّ رافضٍ منفردٍ مانعاً نزع الشهادةَ عن ستّةٍ رُقّوا بحقّ
    #    (قِيس: `m_qari` 1/5 · `twfeeq` 1/9 · `yousef` 1/4 · `qeniwa_qalun` 1/9
    #    · `trablsi` 1/10 · `waleed_qalun` 2/8). **فالفاتلُ وحدَه هو الحاكم:
    #    موضعٌ مسمَّىً بالاسم أدانه الصوت، لا رقمٌ عامّ.**
    audio_keys = [k for k in shas if ".audio-" in k and k.endswith(".json")]
    want = {s[:8]: s for s in verdict_shas}
    mine = [k for k in audio_keys if any(p in k for p in want)]

    def verdict(k, tries=3):
        for i in range(tries):
            try:
                return k, json.loads(cl.get_object(Bucket=bucket, Key=k)["Body"]
                                     .read().decode("utf-8"))
            except Exception:                             # noqa: BLE001
                if i == tries - 1:
                    raise
                time.sleep(2 ** i)
    with ThreadPoolExecutor(4) as ex:
        docs = dict(ex.map(verdict, mine))
    rejected_shas, why = set(), {}
    for k, d in docs.items():
        sha = next((s for p, s in want.items() if p in k), None)
        if sha is None:
            continue
        fats = d.get("fatal") or []
        if undeclared_fatal(fats, op_of.get(sha, "")):
            rejected_shas.add(sha)
            why.setdefault(sha, (k, str(fats[0])[:90]))

    raw_cat = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    before = json.loads(raw_cat)
    after, stat = certify(json.loads(raw_cat), served, verdict_shas, rejected_shas)
    for r in before.get("riwayat", []):
        for x in r.get("reciters", []):
            k = f"timings/{r['id']}/{x['id']}.jz"
            s = served.get(k, (0, 0, "", 0))[2]
            if s in rejected_shas and x.get("ayahCertified"):
                print(f"⛔ تُنزع الشهادةُ عن {r['id']}/{x['id']} ({s[:8]}) — "
                      f"فاتلٌ غيرُ معلَنٍ في {why[s][0].split('.jz.')[-1]}: {why[s][1]}")

    # ⛔ الحارس: شهادةٌ بلا حكمٍ تُسقط التوليد كلَّه.
    bad = []
    for r in after.get("riwayat", []):
        for x in r.get("reciters", []):
            if x.get("ayahCertified") and x.get("mode") != "ayah":
                k = f"timings/{r['id']}/{x['id']}.jz"
                if k not in served or served[k][2] not in verdict_shas:
                    bad.append(k)
    if bad:
        sys.exit(f"⛔ شهادةٌ بلا حكمٍ على البصمة المخدومة: {bad[:5]} — يُوقَف التوليد")

    # ⛔ ولا يتغيّر إلا الحقلان.
    def strip(c):
        c = json.loads(json.dumps(c))
        c.pop("certifiedBy", None)
        for r in c.get("riwayat", []):
            for x in r.get("reciters", []):
                x.pop("ayahCoverage", None)
                x.pop("ayahCertified", None)
        return c
    if json.dumps(strip(before), sort_keys=True) != json.dumps(strip(after), sort_keys=True):
        sys.exit("⛔ تغيّر حقلٌ غيرُ الحقلين في الكتالوج — يُوقَف")

    print(f"مشهودون {stat['certified']}/{stat['total']} = "
          f"{stat['certified'] / stat['total']:.1%}")
    for k, (ok, tot) in sorted(stat["byRiwaya"].items()):
        print(f"   {k:8s} {ok:3d}/{tot:3d} = {ok / tot:.0%}")
    if not a.yes:
        print("عرضٌ فقط — أضف --yes للكتابة")
        return
    body = json.dumps(after, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cl.put_object(Bucket=bucket, Key=CATALOG_KEY, Body=body,
                  ContentType="application/json")
    got = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    if hashlib.sha256(got).hexdigest() != hashlib.sha256(body).hexdigest():
        sys.exit("⛔ ما نزل يخالف ما رُفع — بلاغُ حادثة")
    print(f"↑ كُتب {CATALOG_KEY} ({len(body)} بايت) → ✅")


if __name__ == "__main__":
    main()
