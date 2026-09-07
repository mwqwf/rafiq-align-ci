#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يُدخل قارئاً جديداً في الكتالوج **بوضع السورة الكاملة** — ببرهانٍ لا بجدول.

    python tools/index_qa/add_surah_reciter.py --self-test
    python tools/index_qa/add_surah_reciter.py --id x --riwaya warsh \
        --name "فلان" --base "https://host/path/" --evidence work/x.json --yes

**متى؟** بعد إتمام فهرسة قرّاء الكتالوج الحاليين (‏أمر المالك 2026-09-06):
«بعد إكمال الحاليين ابدأ العمل عليهم مباشرة». والمصدرُ جدولُ المسح
`docs/qa/WARSH_QALUN_RECITERS_SURVEY_2026-09-05.md` — **50 مرشَّحاً** (‏ورش
وقالون، مرتَّبين: موريتانيا ← ليبيا ← الجزائر ← المغرب ← غيرها).

## ⛔ لماذا «السورة الكاملة» لا «آية-آية»

القارئُ الجديد يدخل **مسموعاً لا مفهرساً**: `mode: "surah"` و
`ayahCertified: false`. فالفهرسةُ تأتي بعدُ بمسارها، ولا يُعرض في قائمة
«آية-آية» ما لا فهرسَ له — وهي علّةُ D-220 بعينها.

## الحُرّاسُ السبعة (‏كلٌّ منها يُختبر بحالةٍ سالبة في `--self-test`)

1. **114 ملفاً بـHEAD 200** — لا 113 ولا «أكثرها موجود».
2. **رأسُ MP3 مقروء** لكل عيّنةٍ مفحوصة (‏مدّةٌ ومعدّلُ بتّ) — ملفٌّ لا يُقرأ
   رأسُه ليس صوتاً ولو رجع 200.
3. ⭐ **شاهدا الهويّة**: عيّنتان سمعيّتان (‏1 و112) تُطابقان **نصَّ الرواية
   المعلَنة**، و⛔ **يُرفض من طابق حفصاً أكثر من روايته** — وهذا كاشفُ
   «النسبةِ الخاطئة»: مصحفٌ بحفصٍ مُعلَنٌ ورشاً يمرّ كلَّ فحصٍ آخر ولا يمرّ هذا.
4. **سورةٌ ثالثة عشوائية** تُفحص **فقط لمن تعارض شاهداه** (‏توفيرُ طاقةٍ بلا
   تنازلٍ عن يقين).
5. **مدّةُ السورة ضمن نطاقٍ معقول** لعدد حروفها — يكشف ملفّاً مبتوراً أو مكرَّراً.
6. **صفُّ رخصةٍ** في `DATA_LICENSE_REGISTRY.md`: المصدرُ وما أعلنه بنصّه.
7. **الإدراجُ في ذيل قائمة روايته** بحقل ترتيب، ومعه `attributionEvidence`
   (‏الشاهدان بأرقامهما) و`sourceRead`/الرابط — فمن أدخله ومن أين مكتوبٌ فيه.

⛔ **ولا يُدخل قارئٌ بلا ملفّ برهانٍ (`--evidence`)**: الجدولُ يقول «وجدتُه»،
والبرهانُ يقول «قِستُه» — والفرقُ بينهما هو الفرقُ بين 158 و120 في D-220.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import promote  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

CATALOG_KEY = "catalog/reciters.json"
ADDER = "add_surah_reciter-1.0"
RIWAYAT = {"hafs", "warsh", "qalun", "douri", "sousi", "shuba"}


def check_evidence(ev, riwaya):
    """الحُرّاس 1–5 على ملفّ البرهان — دالّةٌ نقيّةٌ تُختبر بلا شبكة."""
    bad = []
    files = ev.get("files") or {}
    ok200 = sum(1 for v in files.values() if v.get("status") == 200)
    if ok200 != 114:
        bad.append(f"1: ملفّاتٌ بـHEAD 200: {ok200}/114")
    noheader = [s for s, v in files.items()
                if v.get("status") == 200 and not v.get("durationMs")]
    if noheader:
        bad.append(f"2: رأسُ MP3 غيرُ مقروء في {len(noheader)} ملفّاً "
                   f"(مثال س{noheader[0]})")
    wit = ev.get("witnesses") or []
    if len(wit) < 2:
        bad.append(f"3: الشهودُ {len(wit)} والمطلوب اثنان على الأقلّ")
    for w in wit:
        own = w.get("scoreDeclared")
        hafs = w.get("scoreHafs")
        if own is None or hafs is None:
            bad.append(f"3: شاهدُ س{w.get('surah')} بلا درجتين — لا يُقارن")
            continue
        if riwaya != "hafs" and hafs > own:
            # ⛔ **كاشفُ النسبة الخاطئة**: مصحفٌ بحفصٍ مُعلَنٌ ورشاً يطابق
            #    نصَّ حفصٍ أكثرَ من نصّ روايته المعلَنة — ولا يكشفه شيءٌ آخر.
            bad.append(f"3: س{w.get('surah')} تطابق حفصاً ({hafs:.0%}) أكثرَ "
                       f"من {riwaya} ({own:.0%}) — نسبةٌ خاطئة، يُرفض")
        elif own < 0.60:
            bad.append(f"3: س{w.get('surah')} مطابقتُها لنصّ الرواية {own:.0%} "
                       f"— دون الحدّ 60%")
    conflict = [w for w in wit if w.get("conflict")]
    if conflict and len(wit) < 3:
        bad.append("4: تعارضَ الشاهدان ولم تُفحص سورةٌ ثالثة")
    for s, v in files.items():
        r = v.get("durationPerLetter")
        if r is not None and not (0.25 <= r <= 4.0):
            bad.append(f"5: س{s} مدّةٌ لكل حرفٍ خارج النطاق ({r:.2f})")
            break
    if not (ev.get("license") or {}).get("declared"):
        bad.append("6: لا صفَّ رخصةٍ — المصدرُ وما أعلنه يُكتبان بنصّهما")
    return bad


def _self_test() -> None:
    def base():
        return {"files": {str(s): {"status": 200, "durationMs": 60000,
                                   "durationPerLetter": 1.0}
                          for s in range(1, 115)},
                "witnesses": [{"surah": 1, "scoreDeclared": 0.94, "scoreHafs": 0.71},
                              {"surah": 112, "scoreDeclared": 0.91, "scoreHafs": 0.68}],
                "license": {"declared": "archive.org — عرفٌ دعويّ"}}
    assert not check_evidence(base(), "warsh"), "الأساسُ يجب أن يمرّ"
    a = base(); a["files"]["7"]["status"] = 404
    assert any(x.startswith("1:") for x in check_evidence(a, "warsh")), "حارس 1"
    b = base(); b["files"]["9"].pop("durationMs")
    assert any(x.startswith("2:") for x in check_evidence(b, "warsh")), "حارس 2"
    d = base(); d["witnesses"] = d["witnesses"][:1]
    assert any(x.startswith("3:") for x in check_evidence(d, "warsh")), "حارس 3 (عدد)"
    e = base(); e["witnesses"][0].update(scoreDeclared=0.70, scoreHafs=0.93)
    msg = check_evidence(e, "warsh")
    assert any("نسبةٌ خاطئة" in x for x in msg), "⛔ كاشفُ النسبة الخاطئة"
    f = base(); f["witnesses"][0]["conflict"] = True
    assert any(x.startswith("4:") for x in check_evidence(f, "warsh")), "حارس 4"
    g = base(); g["files"]["3"]["durationPerLetter"] = 9.9
    assert any(x.startswith("5:") for x in check_evidence(g, "warsh")), "حارس 5"
    h = base(); h["license"] = {}
    assert any(x.startswith("6:") for x in check_evidence(h, "warsh")), "حارس 6"
    # وحفصٌ نفسُه لا يُرفض بمطابقته حفصاً — الشرطُ على غيره
    i = base(); i["witnesses"][0].update(scoreDeclared=0.95, scoreHafs=0.95)
    assert not any("نسبةٌ خاطئة" in x for x in check_evidence(i, "hafs")), "حفص يُستثنى"
    print("  ✅ الحُرّاس 1–6: كلٌّ يردّ حالتَه السالبة، والسليمُ يمرّ")
    print("  ✅ كاشفُ النسبة الخاطئة يعمل، ولا يسري على حفصٍ نفسِه")
    print(f"✅ --self-test أخضر · {ADDER}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--riwaya")
    ap.add_argument("--name")
    ap.add_argument("--base", help="قالبُ الصوت حتى الشرطة، بلا {s:03d}")
    ap.add_argument("--evidence", help="ملفُّ البرهان (JSON) من فاحص CI")
    ap.add_argument("--country", default="")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        _self_test()
        return
    for need in ("id", "riwaya", "name", "base", "evidence"):
        if not getattr(a, need):
            sys.exit(f"⛔ ينقص --{need}")
    if a.riwaya not in RIWAYAT:
        sys.exit(f"⛔ روايةٌ غيرُ معروفة: {a.riwaya}")

    ev = json.load(open(a.evidence, encoding="utf-8"))
    bad = check_evidence(ev, a.riwaya)
    if bad:
        print("⛔ رُدّ الإدخال:")
        for x in bad:
            print("   ·", x)
        sys.exit(2)

    cl, bucket = promote.s3()
    raw = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    cat = json.loads(raw)
    riw = next((r for r in cat["riwayat"] if r["id"] == a.riwaya), None)
    if riw is None:
        sys.exit(f"⛔ الرواية {a.riwaya} ليست في الكتالوج")
    if any(x.get("id") == a.id for x in riw.get("reciters", [])):
        sys.exit(f"⛔ {a.id} موجودٌ سلفاً — لا يُكرَّر")

    base = a.base if a.base.endswith("/") else a.base + "/"
    row = {"id": a.id, "name": a.name, "mode": "surah", "base": base,
           "ayahCoverage": 0.0, "ayahCertified": False,
           "addedBy": ADDER, "country": a.country,
           "attributionEvidence": {
               "witnesses": ev.get("witnesses"),
               "files200": sum(1 for v in (ev.get("files") or {}).values()
                               if v.get("status") == 200),
               "license": (ev.get("license") or {}).get("declared")}}
    # ⛔ **الذيلُ لا الرأس**: القرّاءُ الجدد أسفلَ القائمة الحالية بحقل ترتيب،
    #    فلا يُزاح عن موضعه من اعتمده المستخدمُ سلفاً.
    row["order"] = len(riw.get("reciters", [])) + 1
    riw.setdefault("reciters", []).append(row)

    print(f"{a.riwaya}/{a.id} — {a.name} · {base}")
    print(f"  شهودٌ: {len(ev.get('witnesses') or [])} · ملفّات 200: "
          f"{row['attributionEvidence']['files200']}/114 · الرخصة: "
          f"{row['attributionEvidence']['license']}")
    if not a.yes:
        print("عرضٌ فقط — أضف --yes للكتابة")
        return
    body = json.dumps(cat, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cl.put_object(Bucket=bucket, Key=CATALOG_KEY, Body=body,
                  ContentType="application/json")
    got = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    if hashlib.sha256(got).hexdigest() != hashlib.sha256(body).hexdigest():
        sys.exit("⛔ ما نزل يخالف ما رُفع — بلاغُ حادثة")
    print(f"↑ أُدخل في ذيل {a.riwaya} برتبة {row['order']} → ✅")


if __name__ == "__main__":
    main()
