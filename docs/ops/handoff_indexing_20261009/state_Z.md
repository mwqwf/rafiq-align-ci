# حالة proofZ (تُستأنف منها)
- القراءة: completion_audit يحتاج (أ) خرائط سماع state-heard (version=heard-gate-1) لكل (قارئ،سورة) = بدء مقيس؛ (ب) شاهد نهاية independentWindowCtc من تقارير splice-census لنفس البصمة (يُنتج فقط للصفوف «غير حاسم»)؛ (ج) تقرير مطالع exact-sha بلا unknown/tail/suspect.
- حالة aud3: خرائط موجودة 4402/20520؛ ناقصة 16110 سورة-قارئ (846,942 بدء)؛ حيث وُجدت الخريطة يُقاس 96.5٪.
- heard_gate.yml لا يغطي المنشور (يُلزم مرشحاً staging + معدّل∪عيّنة 4) ⇒ سيُضاف سير heard_pub.yml (قياس فقط، يكتب state-heard/ بنفس مخطط heard-gate-1).
- الخطوات: [ ] كتابة heard_pub.yml  [ ] ALLOWED_WF إيداع مستقل  [ ] تجربة على mhsny  [ ] دفعات بترتيب الانحراف  [ ] إعادة completion_audit بعد كل دفعة
- 0018Z: heard_pub.yml مدفوع ومسموح؛ تجربة mhsny: run 37864172053 قيد التشغيل
- 0035Z: سائق الحملة proofZ/driver.py يعمل (driver.log, driver_state.json) ويُستأنف بتشغيله ثانيةً؛ pilot mhsny نجح 35 خريطة
- 0042Z: السائق يستعمل نسخةً خاصة proofZ/clone للدفع (الشجرة المشتركة مزدحمة). fixY يستعمل heard_pub أيضاً
- 0230Z: أُرسل للمدير عائق شاهد النهاية (حارس report_error + tool_sha)؛ أنتظر قراره؛ الحملة مستمرة بالسائق؛ المدير: أبقِ نصف الطابور لغيري (MAX_OTHERS يُراعى)
## قرار المدير (0236Z)
لا مسار شاهد جديد للنهايات ولا مسّ بالمعيار. ready=true غير بالغٍ بالمعيار الحالي بسبب النهايات.
الدليل: completion-audit-aud3-summary.json يعطي verifiedEndEvidence=0 من 1,121,595؛ و window_census_witness.report_error يشترط في كل صف يحمل independentWindowCtc أن يكون kind='بريء' وoriginalTinyRow.kind='غير حاسم' وprovenance.tool=ci_window_census.py وtool_sha بصمة ملفه الحاليّ؛ فالمنتَج محصور بالصفوف غير الحاسمة (8332 صفاً عالقاً في aud3)، وتعديل المنتِج يُبطل بصمة كل الشواهد القائمة.
المطلوب: إكمال حملة البدء (heard_pub) وتسجيل الانحرافات المثبتة في proofZ_defects.md وإرسال القائمة دورياً.
- 0310Z: maroush_qalun اكتمل (86 خريطة). السائق مُعدَّل (others=queued+pending≤12). defects.py يولّد proofZ_defects.md. أُرسلت القائمة 1. التالي: مراقبة السائق، تدقيق completion_audit بعد ~10 فهارس
- 0425Z: السائق MAX_MINE=3 SHARDS=3 (9 وظائف ≤ نصف السعة)
- 0735Z: تدقيق 1: unmeasured 849034→814933، deviations 7575→12562، ready=false. 7 فهارس مقاسة
- 0800Z: تحقق المدير: heard_pub يأخذ الرابط من fileRef مداخل الفهرس نفسه (لا قالب كتالوج) والتدقيق يقبل الخريطة فقط إن طابقت بصمتها audioSha256 (asim 114/114 مطابقة). مسبار الصوت: asim س2 الملف 6528ث والفهرس ينتهي 3391ث؛ kurdi س42 الملف 1267ث والفهرس ينتهي 890ث ⇒ كبس حقيقي. أُضيف لسجل heard_pub الرابط والبصمة (f1fa8f8d8).
- 1115Z: تدقيق 2 (11 فهرساً): unmeasured 788,071؛ deviations 15,195؛ 19 فهرساً منحرفاً في proofZ_defects.md. الوتيرة ~0.7 فهرس/ساعة؛ السائق يعمل (استئناف: cd proofZ && MAX_MINE=3 SHARDS=3 MAX_OTHERS=12 nohup python3 driver.py &)
- 1245Z: MAX_MINE=6 وإطلاق فقط إذا إجمالي in_progress+queued+pending<15 (أمر المدير)؛ مسح duration_sweep قيد الأمر ds1
- 1320Z: duration_sweep أُنجز (62 فهرساً مرشحاً) ورُتّب الطابور به؛ sweep_rank.json؛ قسم المسح في proofZ_defects.md. السائق MAX_MINE=6

# ===== حالة التسليم (أمر المالك: الانتقال لخيط جديد) =====
أُوقف السائق ولم تُطلق دفعات جديدة. الحالة كما يلي:
## ما بُني
- `.github/workflows/heard_pub.yml` (مسموح في ALLOWED_WF): يقيس خرائط السماع لفهرس منشور ويكتب `state-heard/timings_<رواية>_<قارئ>.jz.json` (صيغة heard-gate-1) ويسجّل لكل سورة الرابط والبصمة المقيسة/المعلنة ولا يكتب خريطة غير مطابقة؛ السجل في `ops/out/heard-pub/<run>.txt`. مدخلاته: key=timings/<رواية>/<قارئ>.jz · shards · surahs · force.
- `tools/index_qa/duration_sweep.py` (مسموحة): مسح مدة الملف مقابل نهاية الفهرس (HEAD + مدى 64ك.ب).
## ما قِيس
- خرائط سماع كاملة (فهرس كامل): mhsny · maroush_qalun · khan · asim · mukhtar_haj · kurdi · sayed · a_abdl · kherkhashi_qalun · a_alqrafi · rabbani_warsh · jelmam_qalun · trablsi · alijon (وفهارس fixY: zahrani habdan abkar a_ahmed a_turki jamal jaman noah qazabri wahrani_warsh). 
- تدقيق الاكتمال: قبل 849,034 بدء غير مقيس/7,575 انحراف → بعد 11 فهرساً 788,071/15,195 (ops/out/completion-proofZ-2.json)؛ ready=false.
- مسح المدد لكل الـ180: 62 فهرساً مرشّحاً للكبس (ops/out/duration-sweep-1.json و-2.json؛ ترتيب في proofZ/sweep_rank.json).
## الجاري عند التسليم (6 تشغيلات heard_pub تنتهي وحدها وتكتب state-heard)
balilah (37934166908) · koshi_warsh (37934156559) · derini_warsh (37934146038) · a_alhazmi (37934135942) · s_sadeiq (37924943675) · harraz_warsh (37924801828). لا تُعاد قبل اكتمالها (concurrency وplan يتخطى المغطّى).
## الباقي وترتيبه
`proofZ/driver_state.json` حقل queue (160 فهرساً): أولاً مرشّحو الكبس بمسح المدد بترتيب الفرق الأكبر (a_klb · darweez · laghdaf_shinqiti · h_dukhain · s_hashemi · afs · m_harfoush · arkani · a_albadr · nourin_douri · a_binaoun · deban ...) ثم الباقي بترتيب الانحراف.
## السائق وإعادة تشغيله
`proofZ/driver.py` (يدفع أوامر الإطلاق من نسخة خاصة `proofZ/clone` لا من الشجرة المشتركة؛ يطلق فقط إذا حصتي أقل من MAX_MINE وإجمالي in_progress+queued+pending < 15). التشغيل: `cd .../scratchpad/proofZ && (MAX_MINE=6 SHARDS=3 nohup python3 driver.py >> driver.log 2>&1 &)`. ⛔ لا تقتله بـpkill -f؛ استعمل `kill $(pgrep -f "^python3 driver.py")`. تنبيه: قائمة done في الحالة تُعلَّم بعد 10 دقائق من اختفاء التشغيلة من العنوان فقد تتأخر؛ التحقق الحقيقي بملف ops/out/heard-pub. `proofZ/tick.sh` للمراقبة، `proofZ/defects.py` يعيد توليد proofZ_defects.md من سجلات heard-pub + قسم المسح.
## الوتيرة
نحو 0.7 فهرس/ساعة بثلاث تشغيلات، الزمن هو CTC لا الطابور. المتبقي مع فهارس الكبس الكبيرة أياماً.
## النهايات
ready=true غير بالغ بالمعيار الحالي (verifiedEndEvidence=0 من 1,121,595؛ شاهد independentWindowCtc محصور بالصفوف غير الحاسمة وبمنتِج بصمته معتمدة في window_census_witness.report_error). قرار المدير: لا مسّ بالمعيار.
## ملاحظات معيارية
- مطالع: completion_audit يعدّ حقل unknown (فواتح مقطّعة تعجز عنها ASR) غير محسوم وpromote.py لا يمنع به؛ fakhfakh_qalun وحده ready بالمطالع.
- التحقق من الصوت: الخريطة تُقبل فقط إن طابقت بصمتها audioSha256؛ asim س2 ملف 6528ث والفهرس ينتهي 3391ث (مسبار).
