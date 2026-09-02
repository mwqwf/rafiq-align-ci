# -*- coding: utf-8 -*-
"""تنفيذ خطة التغطية بالأولوية — «حدٌّ ذو معنى للمستخدم لا حدٌّ زمني».

المبدأ (قرار المشرفة 2026-09-01): نشحن **ما يُفتح فعلاً** لا ما يملأ جدولاً.
فبدل تغطية جزئية مبعثرة عبر المصحف، نضمن تغطية **كاملة** لبنود يستعملها الناس،
بنداً بعد بند، ويُرفع المخرج بعد كل بند فينتفع المستخدم بالتدريج لا عند الكمال.

ثلاثة قيود ملزمة:
  (أ) بعد كل بند: يُكتب المخرج ويُعلن البند مكتملاً.
  (ب) ⛔ **لا تُقصّ سورة نصفين** — البند يكتمل أو يُترك. (مكفول بنيوياً: الكتابة
      بعد اكتمال السورة، فالانقطاع في وسطها يُسقط عملها ولا يُنصّفها.)
  (ج) `coverageScope` في المانيفست يذكر البنود المكتملة صراحةً — فيعرض التطبيق
      الميزة حيث تعمل ويصمت حيث لا تعمل، **بلا وعد كاذب**.

python run_plan.py --index <idx.jz> --out <wordtimings.jz>
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _V2)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import load_index, load_text, read_jz  # noqa: E402

import build_index as B  # noqa: E402


def surahs(*ns):
    return lambda sn, an: sn in set(ns)


def rng(a, b):
    return lambda sn, an: a <= sn <= b


def ayat(sn0, spans):
    def f(sn, an):
        return sn == sn0 and any(a <= an <= b for a, b in spans)
    return f


# ترتيب التنفيذ — مشتق من واقع الحفظ والتلاوة (قرار المشرفة)
PLAN = [
    ("جزء 30", rng(78, 114)),
    ("جزء 29 (تبارك)", rng(67, 77)),
    ("الفاتحة + آية الكرسي + خواتيم البقرة",
     lambda sn, an: (sn == 1) or (sn == 2 and (1 <= an <= 5 or 255 <= an <= 257
                                               or 284 <= an <= 286))),
    ("الكهف", surahs(18)),
    ("يس", surahs(36)),
    ("الرحمن", surahs(55)),
    ("الواقعة", surahs(56)),
    ("السجدة", surahs(32)),
    ("مريم", surahs(19)),
    ("الحجرات", surahs(49)),
    ("لقمان", surahs(31)),
    ("جزء 28", rng(58, 66)),
]
NOTIFY_AFTER = 4          # أبلغ المشرفة بعد كل بند من الأربعة الأولى


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--riwaya", default="qalun")
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio-dir", default=os.path.join(_HERE, "work", "audio"))
    ap.add_argument("--surahs", default=None,
                    help="حصر هذا العامل بسور بعينها، مثل 18,36,55 أو 1-20 — "
                         "⛔ التقسيم بالسورة لا بالآية (عاملان على سورة واحدة "
                         "يتنافسان على ملف صوتها)")
    ap.add_argument("--part-id", default=None,
                    help="معرّف الجزء: يكتب out/parts/<name>.part<ID>.jz بدل "
                         "الملف الموحّد — لا يلمس عاملٌ ملف غيره")
    ap.add_argument("--audio-base", dest="audio_base", default=None,
                    help="قالب رابط صوت السورة {surah:03d} (الافتراضي الحصري/قالون mp3quran)")
    ap.add_argument("--audio-mirror", dest="audio_mirror", default=None,
                    help="قالب رابط المرآة عند تعذّر المصدر")
    ap.add_argument("--full-wav", dest="full_wav", action="store_true",
                    help="حوّل السورة إلى wav 16ك مرة واحدة (خادم بقرص واسع) — قصّ فوري")
    ap.add_argument("--rest", action="store_true",
                    help="بعد البنود: أكمل بقية المصحف بالأطول أولاً")
    args = ap.parse_args()

    if args.part_id:
        d, base = os.path.split(args.out)
        stem = base[:-3] if base.endswith(".jz") else base
        args.out = os.path.join(d, "parts", "%s.part%s.jz" % (stem, args.part_id))
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        print("جزء %s ← %s" % (args.part_id, args.out), flush=True)

    ti = read_jz(args.index)
    idx = load_index()
    text = load_text(args.riwaya)
    starts = {s["n"]: s["start"] for s in idx["surahs"]}
    counts = {s["n"]: s["ayahs"] for s in idx["surahs"]}
    os.makedirs(args.audio_dir, exist_ok=True)

    only = None
    if args.surahs:
        only = set()
        for part in args.surahs.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-")
                only.update(range(int(a), int(b) + 1))
            elif part:
                only.add(int(part))
        print("هذا العامل مقصور على %d سورة" % len(only), flush=True)

    high = [e for e in ti["entries"]
            if e.get("confBand") == "HIGH" and e.get("startMs") is not None
            and (only is None or int(e["ayahId"].split(":")[0]) in only)]
    done = {}
    scope = []
    high_by_item = {}
    if os.path.exists(args.out):
        try:
            prev = read_jz(args.out)
            done = {e["ayahId"]: e for e in prev.get("entries", [])}
            scope = list(prev.get("coverageScope", []))
            print("استئناف: %d آية · بنود: %s"
                  % (len(done), [c.get("item") for c in scope] or "—"), flush=True)
        except Exception:
            pass

    out = list(done.values())
    stats = {"ayahs": 0, "withWords": 0, "words": 0, "dropped": {}}

    def save():
        B.write_doc(args, ti, out, coverage=scope)

    items = list(PLAN)
    if args.rest:
        items.append(("بقية المصحف", lambda sn, an: True))

    names_done = set(c.get("item") for c in scope)
    for name, sel in items:
        if name in names_done:
            continue
        in_item = [e for e in high
                   if sel(int(e["ayahId"].split(":")[0]),
                          int(e["ayahId"].split(":")[1]))]
        high_by_item[name] = len(in_item)

        def close_item(nm):
            ids = set(e["ayahId"] for e in high
                      if sel(int(e["ayahId"].split(":")[0]),
                             int(e["ayahId"].split(":")[1])))
            cov = sum(1 for e in out if e["ayahId"] in ids)
            scope.append({"item": nm, "covered": cov, "high": len(ids)})
            save()
            print("✅ البند «%s»: %d/%d آية (%.1f%%) · الإجمالي %d"
                  % (nm, cov, len(ids), cov / max(len(ids), 1) * 100, len(out)),
                  flush=True)
        picked = [e for e in high
                  if sel(int(e["ayahId"].split(":")[0]),
                         int(e["ayahId"].split(":")[1]))
                  and e["ayahId"] not in done]
        by = {}
        for e in picked:
            by.setdefault(int(e["ayahId"].split(":")[0]), []).append(e)
        if not by:
            close_item(name)
            continue
        print("\n=== البند: %s — %d آية في %d سورة ==="
              % (name, len(picked), len(by)), flush=True)
        order = sorted(by, key=lambda n: counts.get(n, 0))   # الأقصر أولاً داخل البند
        failed = []
        for sn in order:
            try:
                B.process_surah(sn, args, by[sn], text, starts, out, stats)
            except IOError as ex:
                print("⚠️ سورة %d تعذّرت (%s) — تُلحق آخر البند" % (sn, ex), flush=True)
                failed.append(sn)
                continue
            save()      # 💾 بعد كل سورة: لا تُقصّ سورة نصفين
        for sn in failed:
            try:
                B.process_surah(sn, args, by[sn], text, starts, out, stats)
                save()
            except IOError:
                print("⛔ سورة %d بقيت متعذّرة — البند ناقص" % sn, flush=True)
                failed = [sn]
                break
        else:
            failed = []
        if failed:
            ids = set(e["ayahId"] for e in high
                      if sel(int(e["ayahId"].split(":")[0]),
                             int(e["ayahId"].split(":")[1])))
            cov = sum(1 for e in out if e["ayahId"] in ids)
            print("⛔ البند «%s» لم يكتمل — سند: %d/%d آية · سور متعذّرة %s "
                  "⇒ لا يُضاف إلى coverageScope"
                  % (name, cov, len(ids), failed), flush=True)
            continue
        close_item(name)

    save()
    print("\nالمخرج: %d آية · %d كلمة · بنود مكتملة: %s"
          % (len(out), sum(len(e["words"]) for e in out), scope))
    print("ساقطة: %s" % stats["dropped"])


if __name__ == "__main__":
    main()
