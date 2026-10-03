#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""☁️📏 **طولُ نافذة «سمّع معي» السحابيّة — 3.6 مقابل 4.8 مقابل 6ث** (‏المستشار · 2026-10-03).

الدافع: في الجولة الأولى (‏`tasmi-decode` 37071769425) هلوست السحابةُ «اشتركوا في القناة» / «ترجمة نانسي قنقر»
في 15/80 نافذةً بطول 3.6ث، ونافذةُ 6ث للبند نفسِه صحيحة. فهل تُطيل النافذةُ الصوتَ بما يكفي لإخماد الهلوسة،
وبأيّ ثمنٍ في الزمن والدقّة؟

لكلّ بندٍ مدّتُه ≥ أطولِ نافذة: ثلاثُ نوافذَ **متّحدةُ المركز** (‏وسطُ البند) تُرسَل إلى `/v1/tasmi/stream` بلا رأس VAD
(‏المشحون). جهازٌ مؤقّتٌ يُسجَّل ثمّ يُمحى (‏كما `cloud_vad_ab.py` — بلا أسرار؛ العنوانُ علنيٌّ في التطبيق).
⛔ الصوتُ تلاواتُ قرّاءٍ منشورة من العيّنة، لا صوتَ مستخدم؛ ومسارُ البثّ يمرّر ولا يخزّن.

المقاييسُ في `cloud_report.py` (‏مشتركةٌ مع `cloud_vad_ab.py`): الهلوسة (‏عبارةٌ غيرُ قرآنية) · WER المحلّي
(‏محاذاةٌ شبهُ شاملةٍ على أقرب مقطعٍ من الآية) · الكلمات/المتوقَّع · الزمن · والفرقُ المزدوج [95٪].
"""
import argparse
import json
import os
import sys
import time

import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from speed_ab import SR  # noqa: E402
from cloud_vad_ab import call, wav_bytes  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", required=True, help="مجلّدُ بنود (يُكرَّر: wav · wavn)")
    ap.add_argument("--sample", default="sample.json")
    ap.add_argument("--limit", type=int, default=150, help="بنودٌ من كلّ مجلّد")
    ap.add_argument("--windows", type=float, nargs="+", default=[3.6, 4.8, 6.0])
    ap.add_argument("--sleep", type=float, default=0.8, help="فاصلٌ بين النداءات (‏الحصّة 90/دقيقة)")
    ap.add_argument("--json", required=True)
    a = ap.parse_args()
    items = {it["id"]: it for it in json.load(open(a.sample, encoding="utf-8"))["items"]}
    wmax = max(a.windows)
    s, body, _ = call("POST", "/v1/device", json.dumps({"app_version": "probe", "platform": "ci-window-ab"}).encode(),
                      {"content-type": "application/json"})
    if s != 200:
        raise SystemExit("⛔ تعذّر تسجيلُ جهاز: %s %r" % (s, body[:200]))
    tok = json.loads(body)["token"]
    auth = {"authorization": "Bearer " + tok, "content-type": "audio/wav"}
    rows, sent_ms = [], 0
    try:
        for src in a.src:
            names = sorted(f for f in os.listdir(src) if f.endswith(".wav") and f[:-4] in items)
            # 🎯 البنودُ التي تتّسع لأطول نافذة — فالنوافذُ الثلاثُ قصٌّ حقيقيٌّ لا البندُ كلُّه.
            names = [f for f in names if sf.info(os.path.join(src, f)).duration >= wmax][: a.limit]
            for k, f in enumerate(names):
                x, _ = sf.read(os.path.join(src, f), dtype="float32")
                it = items[f[:-4]]
                row = {"id": f[:-4], "set": os.path.basename(src.rstrip("/")), "ref": it["refText"],
                       "dur": len(x) / SR, "wordCount": it.get("wordCount")}
                for w in a.windows:
                    n = int(w * SR); st_ = max(0, len(x) // 2 - n // 2)
                    win = x[st_: st_ + n]
                    s, body, dt = call("POST", "/v1/tasmi/stream", wav_bytes(win), auth)
                    txt = ""
                    if s == 200:
                        try:
                            txt = json.loads(body).get("text", "") or ""
                        except Exception:
                            txt = ""
                    row["w%.1f" % w] = {"status": s, "sec": dt, "win": len(win) / SR, "text": txt,
                                        "err": "" if s == 200 else body[:120].decode("utf-8", "replace")}
                    sent_ms += int(len(win) * 1000 / SR)
                    time.sleep(a.sleep)
                rows.append(row)
                if (k + 1) % 10 == 0 or k + 1 == len(names):
                    print("%s %d/%d" % (row["set"], k + 1, len(names)), flush=True)
    finally:
        s, _, _ = call("DELETE", "/v1/device", headers={"authorization": "Bearer " + tok})
        print("DELETE /v1/device →", s)
    json.dump({"arms": ["w%.1f" % w for w in a.windows], "rows": rows, "sent_ms": sent_ms},
              open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("أُرسل %.1f دقيقة صوت · %d بنداً" % (sent_ms / 60000, len(rows)))


if __name__ == "__main__":
    main()
