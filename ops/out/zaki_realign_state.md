# حالة إعادة محاذاة zaki (2026-11-10)
- الحيّ: timings/hafs/zaki.jz بصمة dc20b8fc (ETag b727b79c5ca8df186fb14df8b97b4894، 6236 مدخلاً).
- المحاذاة الكاملة: ctc_align.yml تشغيلة 42824472600 (parts=16, auto_chunk=1) نجحت ⇒ المرشّح timings-staging/hafs/zaki.72f45472.jz (6235 آية؛ HIGH 456، فشل سور: لا شيء).
- التالي: struct (1110_zrl_zaki_sb) ثم heard_gate/openers/أربعة ملوح/diagnosis/census، ثم التحقّق من العناقيد التسعة.
- 15:12Z: المرشّح 72f45472 (ctc_align كاملة) فشل: 80 سورة من 114 انحرف ذيلها 5ث..4786ث عن الحيّ وLOW 2571، و38:53 بلا محاذاة (ثقة 0.0)؛ سليم في 34 سورة قصيرة فقط. struct مرّ بتحذيرات. لا يُرقّى.
- التجربة: ctc_splice mode=heard على الحيّ بسور كاملة (25 · 8 · 86-90) ثم تعميم على 114 (دفعات في /tmp/claude-0/zk/batches.json: 50 دفعة).
- 15:50Z: تجربة heard نجحت: 25 ⇒ zaki.6d52cfc6 · 86-90 ⇒ zaki.13a0b551 · 8 ⇒ (تشغيلة 42842370540). أُطلقت بقيّة الدفعات (47) على الحيّ بوضع heard؛ ثمّ تُزرع بـgraft_surahs سلسلةً.
- 17:25: انتهت 50 تشغيلة heard (نجحت كلها وغطّت 114 سورة). أُطلق ctc_splice_merge لدمجها في مرشّح واحد من dc20b8fc (ops/commands/1110_zrl_zaki_merge.json؛ معرّفات التشغيلات في الأمر).
- 17:35: المرشّح المدموج: timings-staging/hafs/zaki.e6cb8131.jz (6236 مدخلاً، 114 سورة، حدود أُزيحت 5846، محرّك align-0.2/heard). أُطلقت بواباته: struct · heard_gate · openers · 4 ملوح (zrl1110A-D) · census · diagnosis (ops/commands/1110_zrl_zaki_c_*).
