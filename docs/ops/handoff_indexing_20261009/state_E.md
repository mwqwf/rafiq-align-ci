# حالة fixE (مستأنف)
- شجرة العمل النظيفة: scratchpad/wtE (git worktree من origin/main)؛ الخطة e_plan.json (readers من المسح عدا maroush_qalun/asim/kurdi/mukhtar_haj).
- 14:00 أُرسل أمر fixE_src_all (show_source لكل القرّاء) لجلب قوالب المصدر.
- 13:15Z أُطلقت heard_batch: darweez, laghdaf_shinqiti, alijon, sayed + سبر a_klb(3,76,77). القوالب من ops/out/20261009_1400_fixE_src_all.txt. مولّد الأوامر: scratchpad/e_gen.py
- الترتيب التالي: h_dukhain, s_hashemi, afs, a_alqrafi, m_harfoush, arkani, ... (e_plan.json)
- 13:30Z a_klb مدحوض: ملفاته .ogg (Vorbis) والمسح قدّرها كـmp3 بمعدّل وهمي؛ المدد الحقيقية s3 3488.6 مقابل نهاية الفهرس 3486.8، s76 358.4/357.4، s77 223.8/222.7 ⇒ لا كبس (ops/out/20261009_1415_fixE_probe_aklb.txt). تنبيه: أي قارئ ملفاته غير mp3 تُقدَّر مدته خطأً.
- أُطلقت h_dukhain.

## تسليم (الأمر: انتقال لخيطٍ جديد) — لقطة نهائية
- المستودع العامّ؛ شجرة نظيفة: scratchpad/wtE (worktree من origin/main)؛ الدفع بـ git push origin HEAD:main. الخطة: e_plan.json (57 فهرساً من المسح عدا maroush_qalun وasim وkurdi وmukhtar_haj)، المولّد e_gen.py (hb(rid) يكتب أمر heard_batch بقالب المصدر من ops/out/20261009_1400_fixE_src_all.txt)، e_wait.sh.
- a_klb: مدحوض بالقياس (سبر 20261009_1415_fixE_probe_aklb.txt): ملفاته .ogg، والمسح قدّرها كـmp3 بمعدّل وهمي؛ المدد الفعلية تطابق الفهرس (s3 3488.6 مقابل 3486.8؛ s76 358.4/357.4؛ s77 223.8/222.7). لا كبس ولا عمل. تحذير: أي قارئ مصدره غير mp3 (ogg/archive.org) قد يكون مرشّحه كاذباً؛ تحقق من الامتداد قبل البناء.
- تشغيلات heard_batch جارية (أصلها المنشور timings/<riw>/<id>.jz؛ كلّها لم تكتمل ولا نتيجة بعد): alijon 37935442603 · darweez 37935453281 · laghdaf_shinqiti 37935464748 · sayed 37935475396 · h_dukhain 37936010790. القرار: الدفعة تقيس كلّ سورة وتأخذ فقط ما انحرف >1.5ث وطابقه المبنيّ؛ تُنتج مرشّحاً timings-staging/<riw>/<id>.<sha8>.jz وتقريرها في ops/out/heard-batch/<id>_<run>.txt (يُقرأ بعد الاكتمال).
- لا مرشّحات ولا بوّابات ولا ترقيات بعد؛ fixE_promote وfixE_held فارغان/غير موجودين. لم يُسقَط شيء.
- المتبقي بالترتيب بعد h_dukhain: s_hashemi, afs, a_alqrafi(له خريطة heard-pub), m_harfoush, arkani, a_albadr, nourin_douri, ... (e_plan.json). لكلّ مرشّح: struct → openers → 4 ملوح → splice_census/heard_gate/diagnosis/full_audit، ثم رباعية P1-P4 للمدير.
