# asX العسيري
- سبب ردّ plan (مُستنسخ دون اتصال على بايتات المرشح المرحَّل 3siri.3a321fbf المصدّرة): promote.index_gate ⇒ inherited_drops ⇒ «بيان سبب الغياب الموروث مفقود أو تبدل» لأن reasonCode الأصل SOURCE_CORRUPT.
- لا طريق بلا تعديل حارس: (أ) op=drop_surah:7 يصطدم بـD-186 (>20 آية) في promote؛ (ب) المرشح المدمج يردّه extra_src في stage_transform؛ (ج) metadata-only يشترط تطابق المداخل.
- التعديل المقترح: asX_inherited_corrupt.diff + _test.diff (في scratchpad)، جُرّب على نسخة؛ 8 اختبارات تمر؛ index_gate على المرشح يعطي None.
- fixX_promote: لم يُضَف شيء.
- 09-10: هوية 3siri نُشرت 3a321fbf. مرشّح س7 CTC 5738b5a3: struct سليم، لكن heard_gate ردّه (8 آيات: 1,13,41,49,50,79,120,123).
- المحاولة 1 (ctc_splice mode=heard، تشغيلة 37901159081): فشلت خطوة المحاذاة بعد نجاح plan (اسم ملف الأرشيف «007 - سورة الأعراف.mp3» لا يطابق base+{s:03d}.mp3؛ السجل محجوب).
- المحاولة 2 (pin_heard): تشغيلة ctc_heard_probe 37901532740 (سبر خريطة س7 float32) قيد التنفيذ؛ التثبيت المخطط: 1,13,41,49,50,79,120,121,122,123 على مراسيها.
- المحاولة 2: pin_heard نجح بحرّاسه ⇒ 3siri.110e7855 (op=heard_pin:7، fromKey=المرحلي 5738b5a3؛ تنبيه: promote_verified_transform يشترط fromKey=timings/hafs/3siri.jz). بوابات g8 أُطلقت 1540
- 20:00 المرشّح 110e7855 اجتاز كل البوابات (heard يمر، full_audit نظيف، غير المجمَّد لا يرد)؛ أوامر unfreeze/promote/refreeze في fixX_promote (ثلاثة ملفات 2100-2102)
