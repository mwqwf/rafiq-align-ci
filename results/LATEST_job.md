# 🦾 شغلُ الوكيل · الشوط 42211258468

- التاريخ: 2026-11-06T11:35:16Z
- المستودعُ الخاصّ: حاضر (مسارُ العدّاء لا يُطبع)/home/runner/work/_temp/QuranRafiq

## `jobs/tasmi_student_measure.sh`

```
▸ المستودعُ الخاصّ: a74ed0a (البصمةُ وحدها)
▸ ① العُدّة

[notice] A new release of pip is available: 26.2.2 -> 26.3
[notice] To update, run: pip install --upgrade pip

[notice] A new release of pip is available: 26.2.2 -> 26.3
[notice] To update, run: pip install --upgrade pip
▸ ② الوسمُ (‏D-717)
▸ ③ المعلّمُ وتهيئتُه (‏D-738)
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/site-packages/transformers/configuration_utils.py:335: UserWarning: Passing `gradient_checkpointing` to a config initialization is deprecated and will be removed in v5 Transformers. Using `model.gradient_checkpointing_enable()` instead, or if you are using the `Trainer` API, pass `gradient_checkpointing=True` in your `TrainingArguments`.
  warnings.warn(
▸ ④ البيانات (‏قرّاءُ D-714 أنفسُهم · 150 لكلّ قارئ بدل 400 — والفرقُ يُنشر)
11:41:07 ✅ ('hafs', 'a_alshahhat'): 150 clips · 0.36 h
11:41:07 ✅ ('hafs', 'a_alhazmi'): 150 clips · 0.42 h
11:41:07 DONE manifest rows = 2230 · 7.25 h · failed reciters = []
▸ المجموعة: 2230 صفّاً
▸ ⑤ معايرةُ السرعة — أربعون خطوةً تُقاس ثمّ تُحسب ميزانيّةُ الخطوات
🧍 قرّاءٌ محجوزون كلّياً ['a_alhazmi', 'm_sayed_warsh', 'tareq_qalun']: 224 آية للتقييم · 1030 للتدريب
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/site-packages/transformers/configuration_utils.py:335: UserWarning: Passing `gradient_checkpointing` to a config initialization is deprecated and will be removed in v5 Transformers. Using `model.gradient_checkpointing_enable()` instead, or if you are using the `Trainer` API, pass `gradient_checkpointing=True` in your `TrainingArguments`.
  warnings.warn(
🪶 طالبٌ ضيّق: hidden=384 · طبقات=8 · 19.8 م.معلمة · نُسخ من المعلّم 13/213 موتّراً
  · 20/40 خسارة 14.107 · 14.22ث/خطوة
  · 40/40 خسارة 3.553 · 14.40ث/خطوة
  خطوة 40: خسارة 8.564 · PER 100.0٪
✅ الخسارة 56.97 ⇐ 3.543 · PER 100.0٪
▸ ⏱️ 16.15 ث/خطوة بدفعة 16 · استُهلك 16 دقيقة ⇒ سقفُ هذا الشوط 210 خطوة
▸ ⑥ التدريبُ إلى 210 ثمّ التكميم
  · 100/210 خسارة 3.339 · 14.38ث/خطوة
  · 200/210 خسارة 3.215 · 14.55ث/خطوة
  خطوة 200: خسارة 3.188 · PER 100.0٪
  خطوة 210: خسارة 3.182 · PER 100.0٪
/home/runner/work/_temp/QuranRafiq/tools/tasmi_phoneme/ctc_train.py:323: DeprecationWarning: torch.ao.quantization is deprecated and will be removed in 2.10. 
For migrations of users: 
1. Eager mode quantization (torch.ao.quantization.quantize, torch.ao.quantization.quantize_dynamic), please migrate to use torchao eager mode quantize_ API instead 
2. FX graph mode quantization (torch.ao.quantization.quantize_fx.prepare_fx,torch.ao.quantization.quantize_fx.convert_fx, please migrate to use torchao pt2e quantization API instead (prepare_pt2e, convert_pt2e) 
3. pt2e quantization has been migrated to torchao (https://github.com/pytorch/ao/tree/main/torchao/quantization/pt2e) 
see https://github.com/pytorch/ao/issues/2259 for more details
  q = torch.ao.quantization.quantize_dynamic(copy.deepcopy(cpu), {torch.nn.Linear}, dtype=torch.qint8)
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/site-packages/torch/ao/nn/quantized/modules/utils.py:72: UserWarning: torch.quantize_per_tensor, torch.quantize_per_channel and other quantized tensor creation functions that produce tensors with dtype torch.quint8, torch.qint8, and torch.qint32 are deprecated and will be removed in a future PyTorch release. Please see https://github.com/pytorch/pytorch/issues/184982 for more information. (Triggered internally at /__w/pytorch/pytorch/aten/src/ATen/quantized/Quantizer.cpp:111.)
  qweight = torch.quantize_per_tensor(
📦 fp32 79.2 م.ب ⇐ int8 36.2 م.ب · PER على 100 آية: 100.0٪ ⇐ 100.0٪
✅ الخسارة 3.46 ⇐ 3.161 · PER 100.0٪
▸ 📄 الخلاصة:
{"items": 1254, "firstLoss": 3.4621567726135254, "finalLoss": 3.1612704396247864, "per": 1.0, "smoke": false, "heldout": 224, "holdoutReciters": "m_sayed_warsh,tareq_qalun,a_alhazmi", "sizeMbFp32": 79.248614, "sizeMbInt8": 36.167306, "perFp32Cpu": 1.0, "perInt8Cpu": 1.0, "quantN": 100}
▸ ⑦ مجموعةُ حدود الكلمة (‏العشرون سورةُ عينُها) ثمّ قياسُ الطوابع
162 آيةً · **658 حدَّ كلمةٍ** · مُسقَطاتٌ 0 · ثباتُ القصّ (وسيط) 0.0 م.ث ⇒ work/tasmi/gwF/qurancdn/manifest.json
⛔ قطعُ ناشرٍ لا وسمٌ بشريٌّ يدويّ — لا تُسمَّى باسم بوّابة M3

حدودُ كلمةٍ مقيسة: 658 في 162 آية (مُسقَط 0)
الخطأُ المطلقُ الوسيط 241 م.ث · p90 872 م.ث
الانحيازُ الوسيط -87 م.ث · التشتّتُ حولَه 215 م.ث (p90 866)
ضمن 60 م.ث مطلقاً: 14.0٪ · ومن الانحياز: 17.3٪
⛔ قطعُ ناشرٍ لا وسمٌ بشريّ — بوّابةُ M3 الأصليّةُ باقيةٌ بلا مسطرتها
▸ ⑧ ⛔ والمقارنةُ على تقاطع الآيات وحدَه (‏D-741) — لا على مادّتَين
صفوفٌ مشتركة: 649 (في 160 آيةً) · وحدَها في معلّم-D733: 0 · وحدَها في طالب-210-خطوة: 9
  معلّم-D733: انحيازٌ -98 م.ث · تشتّتٌ 62 م.ث · ضمن ±60 من الانحياز 48.4٪
  طالب-210-خطوة: انحيازٌ -88 م.ث · تشتّتٌ 216 م.ث · ضمن ±60 من الانحياز 17.7٪
⇒ الفرق: تشتّتٌ +154 م.ث · ضمن ±60 -30.7 نقطة
▸ ✅ تمّ — والرقمُ يُنشر بعددِ خطواته (210 من 3200 المخطَّطة) ولا يُسمّى «الطالبَ النهائيّ»
```

**الخروج: 0 ✅**

