# -*- coding: utf-8 -*-
"""المستوى الكلمي §4.4 (دقة عرضية ±150–250م.ث): توزيع مدى الآية على كلماتها.

التوزيع بوزن الحروف مع علاوة مدّ لنهايات الكلمات الممدودة — «تقسيم مقطعي داخل
الآية». كافٍ للتظليل و«المس كلمة تسمعها»؛ الدقة الفونيمية مؤجلة بلا كلفة (§4.4).

python word_split.py --index work/timings_qalun_husary_qalun.jz --riwaya qalun
يضيف words[] لكل عنصر HIGH/MED ويكتب الفهرس محدثاً.
"""
import argparse
import re

from common import load_index, load_text, norm, read_jz, write_jz

# حروف تثقل وزن الكلمة زمنياً: المدود وأحرف العلة الطويلة والشدّات
_LONG = re.compile("[اويآٱ]")
_SHADDA = "ّ"


def word_weight(w_raw):
    """وزن زمني تقريبي: حرف=1 + مد/علة=0.7 + شدة=0.5 (معايرة أولية §4.4)."""
    bare = norm(w_raw).replace(" ", "")
    base = len(bare)
    longs = len(_LONG.findall(bare))
    shaddas = w_raw.count(_SHADDA)
    return max(base + 0.7 * longs + 0.5 * shaddas, 1.0)


def split_ayah(start_ms, end_ms, words_raw):
    """يعيد [{wordId(subIndex ترتيبي), startMs, endMs}] بتوزيع الأوزان."""
    weights = [word_weight(w) for w in words_raw]
    total = sum(weights)
    span = end_ms - start_ms
    out, t = [], float(start_ms)
    for i, w in enumerate(weights):
        dur = span * w / total
        out.append({"subIndex": i, "startMs": int(t), "endMs": int(t + dur)})
        t += dur
    if out:
        out[-1]["endMs"] = end_ms
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--riwaya", required=True, choices=["hafs", "warsh", "qalun"])
    args = ap.parse_args()
    ti = read_jz(args.index)
    idx = load_index()
    text = load_text(args.riwaya)
    starts = {s["n"]: s["start"] for s in idx["surahs"]}
    added = 0
    for e in ti["entries"]:
        if e["confBand"] == "LOW":
            continue
        sn, an = map(int, e["ayahId"].split(":"))
        raw = text[starts[sn] + an - 1]
        words_raw = raw.split()
        e["words"] = [
            {"wordId": f"{e['ayahId']}:{w['subIndex']+1}", **w,
             "conf": round(e["conf"] * 0.8, 3)}  # ثقة كلمية أدنى من ثقة الآية دوماً
            for w in split_ayah(e["startMs"], e["endMs"], words_raw)
        ]
        added += 1
    write_jz(args.index, ti)
    print(f"أُضيفت توقيتات كلمية لـ{added} آية ← {args.index}")


if __name__ == "__main__":
    main()


# اختبارات ذاتية سريعة: python -c "import word_split as W; W.self_test()"
def self_test():
    ws = split_ayah(0, 1000, ["بِسْمِ", "اللَّهِ"])
    assert ws[0]["startMs"] == 0 and ws[-1]["endMs"] == 1000
    assert ws[0]["endMs"] == ws[1]["startMs"]
    long_first = split_ayah(0, 1000, ["الضَّالِّينَ", "بِه"])
    assert (long_first[0]["endMs"] - long_first[0]["startMs"]) > \
           (long_first[1]["endMs"] - long_first[1]["startMs"])
    print("word_split ✅")
