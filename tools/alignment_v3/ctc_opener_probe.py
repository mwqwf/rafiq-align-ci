#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""الشاهدُ الثاني لحكم `late` في فحص المطالع — CTC على **مقطع المطلع وحده** (2026-09-30).

⭐ **سببُه مقيس:** `late` (مقطعٌ بعد 2ث من المدخل يبدأ بأوّل الآية) التقط المطالعَ المعطوبةَ
المؤكَّدة (النفيس القديم 20/22 · الحارثي س89 · موسى س4 · الرباني س55)، **لكنّه يكذب أحياناً**:
نموذجُ التفريغ مدرَّبٌ على القرآن فيُكمل الآيةَ من بعضها — «انا اعطيناك الكوثر» كاملةً من مقطعٍ
يبدأ في وسطها، والنساءُ عند النفيس وُسمت والـCTC يضع التلاوةَ **قبل** بدء الفهرس (−455م.ث).
⇒ **شاهدان مستقلّان** (‏كقاعدة D-110): `late` من Whisper **و** CTC يضع بدءَ الآية بعد بدء المدخل
بـ≥ CONFIRM_MS بثقة ≥ MIN_CONF ⇒ `lateConfirmed` (مانعٌ في `promote`). وما لم يؤكَّد يبقى تنبيهاً.

⛔ لا تفريغ هنا: نصُّ البسملة والآية الأولى **مفروضٌ** على مقطعٍ قصير [0، نهاية الآية الأولى + 1.5ث]،
فيُحسب الزمنُ في ثوانٍ لا في ساعات. ⛔ والحروفُ المقطّعة مستبعدةٌ قبل الوصول هنا (‏`late_trigger`).

    python tools/alignment_v3/ctc_opener_probe.py --witness state/x.openers.json --riwaya hafs
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
from ctc_seg import BASMALA, SR, _conf, _emissions, _segment  # noqa: E402
from common import load_index, load_text, norm, to_wav16k  # noqa: E402
from vad import read_wav  # noqa: E402

CONFIRM_MS = 1500
# ⛔ **0.3 لا 0.5 — بالمعايرة** (‏36686304114 · 8 فهارس حقيقتها معروفة): كلُّ «late» كاذبٍ جاء فرقُه
#    **سالباً** (−417…−552م.ث) أيّاً كانت ثقتُه، والصادقةُ موجبةٌ ≈2.8ث. وحدُّ 0.5 أفلت صادقاتٍ بثقة
#    0.34–0.48 (‏النفيس 99·100·105·107·108 · الحج 22 · الرباني 55). وخفضُه **يشدّ** الحارسَ لا يُرخيه:
#    يمنع أكثر، وثمنُ خطئه تأخيرُ ترقيةٍ تُفحص لا نشرُ عطب. ودون 0.3 (‏0.0–0.27) لا يُعتدّ بالقياس.
MIN_CONF = 0.3
TAIL_MS = 1500
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}


def confirm(index_start_ms, ctc_start_ms, conf):
    """أيؤكّد CTC أنّ الآيةَ تبدأ بعد بدء المدخل بما يكفي؟ — دالّةٌ صِرفةٌ مختبَرة."""
    if ctc_start_ms is None or conf is None:
        return False
    return conf >= MIN_CONF and (ctc_start_ms - index_start_ms) >= CONFIRM_MS


def probe(url, surah, end_ms, text1):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        data = r.read()
    with tempfile.TemporaryDirectory() as t:
        mp3 = os.path.join(t, "a.mp3")
        open(mp3, "wb").write(data)
        x = read_wav(to_wav16k(mp3)).astype(np.float32)
    clip = x[: int((end_ms + TAIL_MS) * SR / 1000)]
    lead = [] if surah in (1, 9) else [BASMALA]
    segs = _segment(_emissions(clip), len(clip), lead + [text1])
    st, _en, sc = segs[len(lead)]
    return int(st * 1000), _conf(sc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--witness", required=True, help="شاهدُ المطالع (json) — يُكتب فيه الحكمُ الثاني")
    ap.add_argument("--riwaya", required=True)
    a = ap.parse_args()
    doc = json.load(open(a.witness, encoding="utf-8"))
    text = load_text(a.riwaya)
    start_of = {s["n"]: s["start"] for s in load_index()["surahs"]}
    confirmed, detail = [], {}
    for row in doc.get("rows") or []:
        if row.get("verdict") != "late":
            continue
        s = int(row["surah"])
        try:
            st, cf = probe(row["url"], s, int(row["endMs"]), norm(text[start_of[s]]))
        except Exception as ex:                        # noqa: BLE001
            detail[str(s)] = {"error": str(ex)[:120]}
            print(f"  س{s}: ⚠️ تعذّر السبر — {str(ex)[:80]}")
            continue
        ok = confirm(int(row["startMs"]), st, cf)
        detail[str(s)] = {"indexStartMs": row["startMs"], "ctcStartMs": st, "conf": cf,
                          "diffMs": st - int(row["startMs"]), "confirmed": ok}
        print(f"  س{s}: الفهرس {row['startMs']} · CTC {st} (ثقة {cf}) ⇒ {'⛔ مؤكَّد' if ok else 'غير مؤكَّد'}")
        if ok:
            confirmed.append(s)
    doc["lateConfirmed"] = sorted(confirmed)
    doc["lateCtc"] = detail
    doc["lateCtcRule"] = f"CTC ≥{CONFIRM_MS}م.ث بعد بدء المدخل بثقة ≥{MIN_CONF}"
    json.dump(doc, open(a.witness, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"⇒ lateConfirmed={doc['lateConfirmed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
