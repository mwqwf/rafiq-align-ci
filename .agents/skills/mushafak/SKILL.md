---
name: mushafak
description: "Mushafak/مصحفك app (QuranRafiq, rafiq-align-ci, mushafak-ci): features, memorization, recitation, reciter audio alignment/indexing, release. تطبيق المصحف، الحفظ، التسميع، محاذاة التلاوات"
license: Proprietary (mwqwf) — internal
metadata:
  merged: "quran-rafiq + quran-audio-alignment (2026-11-23)"
  full-text: "references/app-constitution.md (old quran-rafiq) · references/alignment.md (old quran-audio-alignment)"
---

# مصحفك | Mushafak (QuranRafiq · rafiq-align-ci · mushafak-ci)

> نبني ما نملكه وحدنا. **الاحترافية · البساطة · الخفة · الاستقلالية** معايير قبول ورفض كل قرار.

## الهوية (محسومة)
- «مصحف يعرف صاحبه»: تقرأ بروايتك، وتحفظ بخطة تشرح قراراتها، وتسمّع فيكشف أخطاءك على جهازك — بلا إنترنت. الحزمة `com.mushafak.app`.
- المستخدم الأول: طالب الحفظ العربيّ (ورش/قالون المغاربي + حفص) بهاتف اقتصاديّ وشبكة متقطّعة.
- العربية **القرآنية** جوهر (والعامة خارج النطاق نهائياً)؛ معمارية Language-Pack من اليوم الأول ولا لغة «مدعومة» قبل اكتمالها بمعيار؛ منتج واحد بتجربة تتشكّل بالهدف — لا تفريع ولا Super App.

## الدستور
1. **AI لا يولّد قرآناً أبداً** — لا نصاً ولا حركة ولا صوت تلاوة؛ يحاذي ويفهرس ويكشف التعارض، ومخرجه مسوّدة تُدقّق. لا بيانات مجهولة الأصل (مهارة `arabic-text-integrity`).
2. البساطة: المصحف يبقى مصحفاً؛ التعقيد تحت السطح. الخفة: offline-first، والأهداف الرقمية في `docs/TARGETS.md`.
3. Solo-first: لا يرتهن إصدار بشيخ/قارئ/مؤسسة/متطوّع؛ الشركاء مضاعِفات لا تبعيات؛ لا تقدير زمن لمراجعة بشرية خارجية قبل تجربتها.
4. **مرفوض نهائياً:** إعلانات · chatbot محاور · leagues/XP · عربية عامة · مجتمع مفتوح · تقييم تجويد كامل قبل نضج العلم · جدولة نشر.
5. لا بند بانتظار المالك: ما لا يملكه إلا حسابه يُدوَّن في `docs/OWNER_ONLY.md` ويُلتفّ عليه؛ لا رسالة للمالك تطلب إذناً. إذن الجلسة المشرفة = إذنه (مع تسمية كل أثر لا رجعة فيه).

## مكان الحقيقة (`mwqwf/QuranRafiq/docs/`)
`PROJECT_STATE.md` (يُقرأ أولاً) · `NEXT_ACTION.md` (الأهمّ الآن + DoD + «يحتاج المالك») · `ROADMAP.md` · `CHANGELOG.md` · `DECISIONS.md` (ADR) · `FEATURE_REGISTRY.md` · `DATA_LICENSE_REGISTRY.md` (**لا أصل في الإنتاج قبل صفّ هنا**) · `RISKS.md` · `BENCHMARKS.md` (لا قرار AI بالانطباع) · `ARCHITECTURE.md`. الأمر اليوميّ في `NEXT_ACTION.md` و`PLAN_TODAY_<التاريخ>.md`. آخر قرار موثّق يغلب أي محادثة أو ذاكرة.
- البنية والخوادم والأسرار (أسماء): اقرأ أحدث `docs/ops/OPS_*.md` قبل أي عمل بنية؛ التسليم النافذ أحدث `HANDOFF_*`؛ `SOLDIER_PROMPTS_*` عند تكليف جنديّ.
- الواجهة: `docs/design/BINDING_SUMMARY.md` ملزم قبل أي عمل واجهة (الدراسة `APP_DESIGN_VISION.md`).
- كود يُعاد استعماله: مصحف/مشغّل/محرّك حزم منبر في `mwqwf/minbar-adkshk`.

## بروتوكول الجلسة
1. LOAD: `PROJECT_STATE` ثم `NEXT_ACTION` (والمتخصّص فقط). 2. ORIENT: المرحلة والبوابة من `ROADMAP`. 3. VERIFY: لا تعارض مع `DECISIONS`/`FEATURE_REGISTRY` (إن تعارض فاعرض القرار وسببه أولاً). 4. WORK: أي بيانات جديدة تمرّ بـ`DATA_LICENSE_REGISTRY`. 5. TEST: سلامة النصّ القرآنيّ إلزامية عند مسّ بياناته. 6. DOCUMENT: `PROJECT_STATE` + `NEXT_ACTION` + `CHANGELOG` قبل نهاية الجلسة. 7. HANDOFF بلا سؤال واحد ثم commit.
- **«واصل»** = عمل بلا توقف حتى إتمام الخطة؛ لا توقف إلا بأمر صريح أو عائق مستحيل بعد استنفاد الطرق (قواعد «ليس عذراً» في `mwqwf-workflow`). التقرير ليس نقطة توقف. الهاتف: المحاكي فقط.

## قبول ميزة جديدة
«ماذا لو أضفنا X؟» ليست قراراً: الهوية؟ القيمة؟ التبعيات؟ Solo؟ التكلفة والحجم؟ أثرها على المبادئ؟ بديل أبسط؟ ⇒ **ACCEPT NOW / PREPARE ONLY / DEFER / REJECT** في `FEATURE_REGISTRY` و`DECISIONS` قبل أي كود. الحالات IDEA→…→RELEASED؛ لا «مدعوم» إلا RELEASED.

## قبل الإصدار (ثابت)
- الرجوع من كل شاشة فرعيّة إلى أمّها: `BackNavigationEmulatorTest` أخضر وكل شاشة جديدة بحالة محلية تُضاف لجدوله وتستعمل `SubScreenBack`. القائمة الكاملة `docs/STORE_GATE.md`. النشر بمهارة `google-play` (`store/release-request.json`).
- Actions: QuranRafiq خاصّ ⇒ `[self-hosted, mushafak-box]` أو ضرورة مسمّاة؛ `mushafak-ci` العامّ مقفل بحارس نطاق (لا وثائق/مهارات فيه).

## محاذاة التلاوات (`rafiq-align-ci` العامّ)
الغاية: كل آية عند كل قارئ منشور بتوقيت صحيح، بلا حاسوب المالك. التكليف الكامل `rafiq-align-ci/docs/agents/RULES.md`، والحالة `ops/out/state.json`.
- ⛔ **لا تحريف بأي وجه:** فهرس يُقرئ آية بصوت سورة أخرى لا يُنشر ولو رفع العدّ؛ النقص المعلَن خير من صوت خاطئ.
- ⛔ عتبة العطب الجسيم **5% لا تُخفَّض** ولا يُعطَّل حارس؛ الحدّيّ يُحسم بعيّنة أكبر (ملوح إضافية).
- ⛔ لا نجاح قبل قراءة الأثر من **الدلو** (`timings/`، `state/`)؛ `conclusion=failure` في Actions ليس حكماً.
- الثقيل في `rafiq-align-ci` (مجانيّ). لا تلمس `emu-gate` و`arm-time` و`chunk-ab` و`finetune-*` (جلسة التسميع).
- **الأمر عبر ملف:** JSON في `ops/commands/` يُدفع ⇒ `agent_cmd.yml` ⇒ الجواب `ops/out/<الاسم>.txt`: `{"action":"state"}` · `{"action":"dispatch","workflow":"<wf>.yml","inputs":{…,"reason":"…"}}` · `{"action":"tool","tool":"index_qa/run.py","args":[…]}`. المسموح في `tools/ci_fleet/agent_cmd.py`. التعذّر ⇒ `ops/out/BLOCKED.md`.
- الاستئناف لا يقع إلا في المشروع الذي على دلوه عمل القارئ (`/mnt/work`)، ومن أطلقه في غيره أعاده من الصفر. «غير مقروء» ليس «غير منجَز» (`f_hajry` مكتمل 114/114 حجبته الفوترة).
- الحلقة (عدّ الأسطول، البصمات، الملوح الأربعة، الترقية) والدروس الثابتة (البسملة، `ctc_splice`، المطلع المتأخّر، الترقية اليدوية): **افتح `references/alignment.md` قبل أي فهرسة أو إصلاح قارئ أو تعديل حارس/عتبة.**
- النصّ الكامل القديم للتطبيق (مراجع الجدوى والخندق): `references/app-constitution.md` — عند الحاجة فقط.
