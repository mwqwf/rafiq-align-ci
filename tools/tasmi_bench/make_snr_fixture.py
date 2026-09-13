# -*- coding: utf-8 -*-
"""🔊 **مولّدُ حزمةِ تماثلِ نسبةِ الضجيج** — `engine/recitation/src/test/resources/snr_fixture.tsv`.

يقابلها `AudioLevelSnrParityTest` على المحرك، فيُحرَس المقياسُ الذي تقوم عليه بوّابةُ «الغرفةِ
الصاخبة» (‏D-329) وعتبتُها المشتقّةُ من منحنى الدقّة (‏D-337 ثمّ D-344).

⭐ **إشاراتٌ تحليليّةٌ لا صوتٌ مخزَّن:** كلُّ حالةٍ إطاراتٌ بسعةٍ ثابتةٍ داخل الإطار (‏`FRAME=320`)
⇒ المئينان وأدنى النوافذ معلومةٌ بالحساب، فالحزمةُ بضع مئاتٍ من البايتات لا ميغابايتات، **ولا
يُقارَن رقمٌ مجهولُ الأصل**.

صيغةُ الوصف: مقاطعُ مفصولةٌ بـ`;`
    `<عددُ الإطارات>:<السعة>`            مقطعٌ ثابت
    `alt<عددُ الإطارات>:<سعة>:<سعة>`     إطاراتٌ متعاقبةٌ بين سعتَين — **تمثيلُ الكلام المتغيّر**

⛔ **ولماذا `alt` لازمة** (‏درسٌ من D-344): الحالةُ المسطَّحة (‏90 إطاراً بسعةٍ واحدةٍ ثمّ 10 صامتة)
لا تمثّل كلاماً: الكلامُ ولو كان متّصلاً تهبط طاقتُه في إطارِ 20 م.ث عند الإغلاقات والشدّات، وعلى
ذلك يقوم `quietFloor`. فحزمةٌ مسطَّحةٌ وحدَها تُظهر المقياسَ الجديدَ **فاشلاً** وهو ناجحٌ على صوتٍ
حقيقيّ (‏`g4dense`: وسيطٌ 25.8 وأدنى 22.3).

    python tools/tasmi_bench/make_snr_fixture.py
"""
import io
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import snr_probe as SP  # noqa: E402

OUT = os.path.join(HERE, "..", "..", "engine", "recitation", "src", "test", "resources", "snr_fixture.tsv")

CASES = [
    # صمتٌ 60٪ ⇒ الأرضيةُ خفيضةٌ جدّاً ⇒ تُعفى (‏null) ولا تُتَّهم غرفةٌ هادئة
    ("floor_inaudible", "40:0.30;60:1e-05"),
    # ⭐ **كلامٌ متّصلٌ نظيفٌ متغيّرُ الطاقة** — الحالةُ التي كان المقياسُ القديمُ يحجبها ظلماً
    ("dense_modulated", "alt200:0.30:0.02"),
    # مسطَّحٌ متّصل: حالةٌ حدّيّةٌ لا تمثّل كلاماً (تُحفظ لأنّها حدُّ المقياس لا عطبُه)
    ("flat_dense_edge", "90:0.30;10:1e-05"),
    # ضجيجٌ ثابتٌ يرفع كلَّ الإطارات ⇒ مدىً ضيّق ⇒ يُحجب
    ("noisy_narrow", "alt100:0.30:0.12"),
    ("borderline", "alt100:0.30:0.055"),
    # نظيفٌ بأرضيةٍ مسموعةٍ وواسعٍ ⇒ يمرّ
    ("clean_audible", "alt100:0.50:0.010"),
]


def signal(spec):
    out = []
    for part in spec.split(";"):
        if part.startswith("alt"):
            body = part[3:]
            n, a, b = body.split(":")
            n = int(n)
            seg = np.empty(n * SP.FRAME, dtype=np.float32)
            for i in range(n):
                seg[i * SP.FRAME:(i + 1) * SP.FRAME] = float(a) if i % 2 == 0 else float(b)
            out.append(seg)
        else:
            n, a = part.split(":")
            out.append(np.full(int(n) * SP.FRAME, float(a), dtype=np.float32))
    return np.concatenate(out)


def main():
    rows = []
    print(f"| الحالة | snrDb | الأرضية dBFS | مسموعة | الحكم بعتبتَي {SP.BLOCK_DB:g}/{SP.NOISY_DB:g} |")
    print("|---|---:|---:|:-:|---|")
    for name, spec in CASES:
        s, fl, aud = SP.snr_of(signal(spec))
        verdict = "معفاة" if not aud else ("**يُحجب**" if s < SP.BLOCK_DB else ("تقريبيّ" if s < SP.NOISY_DB else "يمرّ"))
        rows.append((name, spec, round(float(s), 4), round(float(fl), 4), aud))
        print(f"| `{name}` | {s:.2f} | {fl:.2f} | {'نعم' if aud else 'لا'} | {verdict} |")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        "# حزمةُ تماثلِ نسبةِ الضجيج — تُولَّد بـtools/tasmi_bench/make_snr_fixture.py\n"
        "# إشاراتٌ تحليليّة: إطاراتٌ بسعةٍ ثابتة (FRAME=320) · alt<n>:<a>:<b> = إطاراتٌ متعاقبة\n"
        "# name\tspec\tsnrDb\tfloorDbfs\taudible\n"
        + "\n".join(f"{n}\t{sp}\t{s}\t{f}\t{str(a).lower()}" for n, sp, s, f, a in rows) + "\n")
    print(f"\n⇒ {os.path.relpath(OUT, os.path.join(HERE, '..', '..'))}")


if __name__ == "__main__":
    sys.exit(main())
