# -*- coding: utf-8 -*-
"""يوزّع القراء على الشرائح **بموازنة الأوزان** لا بالقسمة الدورية.

⛔ سببه قياس (2026-09-02): حجم سورة البقرة يتراوح بين **28م.ب و373م.ب** بين
القرّاء — فرقُ **13×**. و`i % SHARDS` توزيعٌ أعمى قد يجمع الثقال في شريحةٍ
واحدة، **وأبطأ شريحةٍ هي زمن الموجة كله**. والوزن هنا حجمُ البقرة: بديلٌ
معلَن عن مدة التلاوة ⇒ عن زمن التنزيل وفكّ الترميز، وهو ما رجّحنا أنه يحكم
زمن الشريحة لا الحساب.

⛔ وقاعدة github-b9 («الترتيب هو القسمة، لا يُعاد ترتيبه») تبقى نافذةً على
شرائح الأسطول؛ وهذه جبهة CI وقد أذن المشرف بتغييرها فيها وحدها. **والحتمية
محفوظة:** كل شريحةٍ تحسب التوزيع نفسه من الملف نفسه بلا تنسيق بينها — فلا
يفهرس عاملان قارئاً ولا يُترك قارئٌ بلا أحد.

    python assign_shard.py <ملف> <SHARD> <SHARDS>   ⇒ أسطر قرّاء هذه الشريحة
"""
import statistics
import sys


def main():
    path, shard, shards = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.rstrip("\n\r")
            if not s or s.startswith("#"):
                continue
            c = s.split("\t")
            if len(c) >= 4:
                rows.append(c)
    if not rows:
        return
    ws = [int(c[4]) if len(c) >= 5 and c[4].isdigit() else 0 for c in rows]
    known = [w for w in ws if w > 0]
    if not known:                      # ⛔ بلا أوزان ⇒ القسمة الدورية كما كانت
        for i, c in enumerate(rows):
            if i % shards == shard:
                print("\t".join(c[:4]))
        return
    # المجهول يأخذ الوسيط لا صفراً: الصفر يجعل المجاهيل تتكدّس في شريحةٍ واحدة
    med = int(statistics.median(known))
    items = [(w or med, c) for w, c in zip(ws, rows)]
    items.sort(key=lambda x: -x[0])    # الأثقل أولاً
    load = [0] * shards
    mine = []
    for w, c in items:
        k = load.index(min(load))      # إلى أخفّ شريحة
        if k == shard:
            mine.append(c)
        load[k] += w
    for c in mine:
        print("\t".join(c[:4]))


if __name__ == "__main__":
    main()
