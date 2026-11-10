# حالة hd24 (مؤقّتة — أُحدّثها حتى التسليم)

الأداة: `timing_evidence_scan.py` المودَعة تستعمل `PH.ref_words_for` بينما بوّابة `drop_surah` تعيد التحقّق بـ`HG.disputed_ref_words` ⇒ مسبارٌ يمرّ في الأداة وتردّه البوّابة
(س37 في fakhfakh: «ما سُمع عند البدء «بطمه الي يوم» ليس من نصّ 37:144»). استُعملت نسخةٌ محلّيةٌ غير مودَعة تبدّل الدالّة وحدها؛ والإصلاح يلزمه طلب دمج.

| المرشّح | المسرح | الحالة |
|---|---|---|
| fakhfakh_qalun س10,29,37 | timings-staging/qalun/fakhfakh_qalun.a90b37fc.jz | مبنيّ + بوّابات؛ س42 cluster_only (3 مثبتة/6 في موضعها) |
| lahoni س29 | timings-staging/hafs/lahoni.ade06e7e.jz | مبنيّ + بوّابات |
| mohsin_harthi س46 | timings-staging/hafs/mohsin_harthi.2c889bfa.jz | مبنيّ + بوّابات |
| s_hashemi س21,23,35 | timings-staging/hafs/s_hashemi.ccc05030.jz | مبنيّ + بوّابات |
| h_abudalal س20 | timings-staging/hafs/h_abudalal.26722680.jz | مبنيّ + بوّابات |
| kyat س21,28 | timings-staging/hafs/kyat.5e899ca6.jz | مبنيّ + بوّابات |
| harraz_warsh س24,40,45 | timings-staging/warsh/harraz_warsh.64d74402.jz | مبنيّ + بوّابات |
| a_alshahhat س20 | timings-staging/hafs/a_alshahhat.dc21b4aa.jz | مبنيّ + بوّابات أُطلقت |
| m_qari س16 | — | 0 مثبتة من 128 (insufficient، رمز 4) فلا مرشّح |
| benkirane 13:27-30 | — | drop_ayahs يردّ: الأصل يعلن إسقاط س23 كاملة (التوريث لا يكون إلا مع --already-absent) |
| a_ahmed · 3siri | — | مرقّيان حيّاً بإعلاناتهما؛ لم يُلمسا |
| habdan.8307660c | timings-staging/hafs/habdan.8307660c.jz | 3:195 وحدها؛ ملوح وإحصاء مقبولة؛ التشخيص مطابق ETag |

صفوف OWNER_DROP_APPROVALS اللازمة (للقائد): كلُّ مفتاح مسرحٍ أعلاه بسوره المحجوبة حديثاً (ولا يُعفى 2% بدونها).
