# حالة المشروع — محاذاة التلاوات (rafiq-align-ci)

> 🗂️ الفهرس الآليّ (الإصدار · الوحدات · سير العمل · المهارات): [`PROJECT_INDEX.md`](PROJECT_INDEX.md).
> **كل وكيل يُنهي تغييراً يحدّث هذا الملف في الطلب نفسه.** آخر تحديث: 2026-11-24.

## الخطة
- إكمال فهرسة كل القرّاء المنشورين بتوقيت صحيح وفق مهارة `quran-audio-alignment`؛ الحالة الحيّة في الدلو و`ops/`.

## الحالة الآن
- نشط يومياً (آخر الإيداعات 2026-11-23: استيعاب توقيت mp3quran لـ`husary_douri`، زرع السور التامّة بـ`official_timing_splice`).
- مسألتان مفتوحتان و6 طلبات سحب.

## الوحدات المفتاحية
- `tools/alignment/` · `.github/workflows/` (`agent_cmd`، `align_split`، `realign_surah`…) · `ops/` الأوامر والأجوبة.

## العمل المفتوح
- طلبات مفتوحة: [#132](https://github.com/mwqwf/rafiq-align-ci/pull/132) · [#131](https://github.com/mwqwf/rafiq-align-ci/pull/131) · [#90](https://github.com/mwqwf/rafiq-align-ci/pull/90) · [#86](https://github.com/mwqwf/rafiq-align-ci/pull/86) · [#82](https://github.com/mwqwf/rafiq-align-ci/pull/82) · [#33](https://github.com/mwqwf/rafiq-align-ci/pull/33).

## السجلّ (الأحدث أولاً، سطر لكل تغيير)
- 2026-11-24 — «حارس مصحفك»: تثبيتٌ من الحيّ على مراسي heard_pub (≥0.5، بلا إرخاء) أنتج مرشّحات ابن عون 2ad3d599 (س23+36) والجناي bbaecb76 (س16) والقرشي eb8dc8c6 (س36+46) ودرويز a17d96eb (س35) والحازمي 85d3926d (س43) وبنكيران b6a993dd (س16+38+59)؛ بواباتها جارية. ترقية الجناي ⛔ بحارس «لا وراثة عن وراثة» لحجب س5 (الحيّ b70f256f عمليته heard_pin) — يلزمه قرار المالك. أدوات المحاكاة المحليّة والتفاصيل في `/workspace/mushafak-index/PROGRESS.md`.
- 2026-11-23 — إعادة استيعاب توقيت mp3quran لـ`husary_douri`.
- 2026-11-23 — إضافة الفهرس الحيّ (`PROJECT_INDEX.md` + سير `project-index`) وتوحيد `AGENTS.md` ومزامنة المهارات من [mwqwf/agent-skills](https://github.com/mwqwf/agent-skills).
