#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ناقلُ أوامرِ الوكيل السحابيّ — يُنفَّذ داخل العدّاء بصلاحيّاته لا بصلاحيّات الوكيل.

**المشكلةُ التي يحلّها (مقيسةٌ لا مظنونة):** جلسةُ كلود السحابيّة تقرأ جيت هَب
ولا تملك `workflow_dispatch` (‏`403`)، ولا تملك اعتمادَ الدلو. فكانت عاجزةً عن
ثلاثةِ أشياءَ هي صُلبُ العمل: **إطلاقُ محاذاة · القياسُ من الدلو · الترقية**.

**الحلّ:** الوكيلُ يكتب أمراً في `ops/commands/<اسم>.json` ويدفعه، فيستيقظ
`agent_cmd.yml` وينفّذه **بصلاحيّاته هو** ثمّ يُعيد الجواب إلى `ops/out/`.
⭐ **فالصلاحيةُ تبقى حيث هي، والأمرُ يُنقل إليها** — ولا يُسلَّم الوكيلُ سرّاً.

## صيغةُ الأمر
```json
{"action": "dispatch", "workflow": "realign_surah.yml",
 "inputs": {"parent": "timings/hafs/x.jz", "surahs": "6", "skip_ms": "7840",
            "url_template": "https://…/{s:03d}.mp3", "reciter_id": "x",
            "riwaya": "hafs", "reason": "…"}}

{"action": "tool", "tool": "index_qa/run.py", "args": ["--struct-only", "timings-staging/…jz"]}
{"action": "tool", "tool": "ci_fleet/restore_loop.py", "args": ["scan", "--limit", "3"]}
{"action": "state"}                      ← جردٌ كاملٌ من الدلو إلى ops/out/state.json
```

⛔ **وقائمةُ المسموح مغلقة** (‏`ALLOWED_*`): أمرٌ خارجَها يُردّ ويُكتب سببُ ردّه.
⛔ **ولا شيءَ هنا يمسّ العتبات ولا الحُرّاس** — `promote.py` يحكم بحُرّاسه كما هو.
⛔ (صيد 2026-10-09) **ويُردّ لـ`index_qa/promote.py` الوسيطان `--override` و`--allow-shrink`**
   بكلّ صيغهما (‏`--x v` · `--x=v` · اختصار argparse)؛ ويبقى `--unfreeze` و`--allow-truncated` وغيرهما.
⛔ **والأمرُ المنفَّذُ يُنقل إلى `ops/commands/done/`** فلا يُعاد تنفيذُه عند كلّ دفعة.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
CMD_DIR = ROOT / "ops" / "commands"
OUT_DIR = ROOT / "ops" / "out"
DONE_DIR = CMD_DIR / "done"
# ⛔ حدُّ المحاولات لأمرٍ لا يكتمل — انظر `main` أدناه.
MAX_TRIES = int(os.environ.get("AGENT_CMD_MAX_TRIES", "3"))

# ⛔ سيرُ العملِ المسموحُ إطلاقُه — والثقيلُ كلُّه هنا فلا حاجةَ إلى غيره.
ALLOWED_WF = {"silence_probe.yml", "heard_anchor_provenance_probe.yml", "free-noah-source-gap-quality.yml", "short_opener_context_diagnostics.yml", "reconcile_public_catalog.yml", "balilah_pause_probe.yml", "source_context_diagnostics.yml", "whisper_recovery_diagnostic.yml", "repair_boundary_diagnostics.yml", "duration_context_followup.yml", "duration_defect_diagnostic.yml", "quran_source_recovery.yml", "tail_clipping_followup.yml", "fakhfakh69_tail_dual_witness.yml", "final_verse_free_batch.yml", "peshawa_tail_dual_probe.yml", "peshawa_tail_free_decode.yml", "saad_free_decode.yml", "free-post-stage-quality.yml", "independent_window_pilot.yml", "registered-source-quality.yml", "verified_kurdi_source.yml", "spoken_census.yml", "window_census.yml", "source_quran_probe.yml", "align.yml", "realign_surah.yml", "openers.yml", "audio_qa.yml",
              # ⭐ 2026-09-24 (‏إذن المالك بالتسريع): محاذاةُ سور النقص وحدها بـCTC
              #    ودمجُها، وإحصاؤها الصوتيُّ الشامل الذي تطلبه الترقية.
              "ctc_splice.yml", "splice_census.yml",
              # 🔀 2026-10-17: الدمجُ التلقائيُّ لطلبات claude/ (بإذن المالك) — إطلاقٌ يدويٌّ عند تأخّر الجدول.
              "automerge.yml",
              # ⭐ (fixT · 2026-10-03) الإصلاحُ الدفعيّ لكبس الذيل (‏مرشّحٌ واحدٌ لكلّ فهرس) وبوّابةُ السماع التي تطلبها الترقية.
              "heard_batch.yml", "heard_gate.yml",
              # 🔎 proofZ 2026-10-09: خرائطُ السماع للمنشور (قياسٌ فقط يكتب state-heard/ وحدَه؛ لا يرقّي ولا يمسّ timings/).
              "heard_pub.yml",
              # تقطيع التفاسير المفتوحة لمقتطفات المساعد الذكي (يكتب ai-tafsir/v1/ وحدها ولا يحذف).
              "tafsir_ai_split.yml",
              #    وعكسُه: سورُ النقص في فهرسٍ منشورٍ بـCTC تُحاذى بـWhisper وتُدمج.
              "whisper_splice.yml",
              "mirror_sha_guard.yml", "mushaf_assets.yml", "basmala.yml", "restore.yml", "keepalive.yml", "mirror_reciter.yml",
              "reciter_probe.yml", "free_candidate_probe.yml", "probe_ayah.yml", "diagnosis.yml", "timing_ingest.yml",
              # ⛔ **أُضيف 2026-09-14 (‏D-442 · مناوبةُ المحرك):** `bench-selftest.yml` يشغّل
              #    اختباراتِ عدّة القياس وحُرّاسَها (‏دقيقةٌ واحدة · بايثون وحدَه · لا محاكيَ ولا
              #    شبكةَ ثقيلة). وأُضيف لأنّ زنادَه بالدفع **توقّف عن الاشتعال** على دفعاتٍ
              #    تمسّ مساراتِه وهو `active` (‏أربعُ محاولاتٍ بأدلّتها في `ops/out/BLOCKED.md`)،
              #    و`workflow_dispatch` المباشر يردّ **403** على بيانة الوكيل ⇒ فالبابُ المفتوح
              #    هو هذا الأمرُ نفسُه. ⚖️ وهو **مسارُ قراءةٍ وفحصٍ لا يكتب شيئاً** (‏`permissions:
              #    contents: read`) فإدخالُه لا يُضعف حارساً ولا يفتح باباً للكتابة.
              "bench-selftest.yml", "package-catalog-cloud.yml",
              # ⛔ **أُضيف 2026-09-14 (مناوبةُ الفهرسة):** `align_split.yml` يقسم القارئَ
              #    الواحدَ على عدّة عدّائين ثمّ يجمع. أُدخل لأنّ العلّةَ التي يعالجها مقيسةٌ
              #    (الموجة 34813198468: أربعُ شرائحَ انتهت في ثانيتين واثنتان تجاوزتا
              #    ساعتين وأربعين) ⇒ زمنُ الموجة أطولُ شريحةٍ لا مجموعُ العمل.
              # ⚖️ **ولا يُضعف حارساً**: شوطُ الجزء لا يستدعي `stage_upload.py` بحال،
              #    والرفعُ كلُّه في العدّاء الخاتم على مسار «المصحف الكامل 1-114»
              #    بحرّاسه كاملةً (114/114 · refine_probe · حارسُ الرفع · PARTIAL_MIN).
              "align_split.yml",
              # ⛔⛔ **أُضيف 2026-09-20 بقياسٍ من سجلّ التشغيلة 35514028223**
              #    (‏`yahya` س102، والخمسُ الأخرياتُ مثلُها حرفاً):
              #      «VAD: 1 فترة صمت · مقطع 1/2 [0.0-28.0ث]: ذهاكم التكاثر …
              #       تفريغ: 2 مقطعاً، 14 كلمة · آيات بلا حدود: [3, 6, 8]»
              #    ⇒ القارئُ يقرأ التكاثرَ **في نفَسٍ واحدٍ بلا سكتات**، فلا
              #    يجد محرّكُ VAD حدوداً يقسم عليها. **وليست علّةَ تخطٍّ**:
              #    التخطّي عمل، والبسملةُ أُزيحت، والصوتُ نُزّل سليماً.
              # ⛔ وقد أُعيدت هذه السورُ الخمسُ في **ثلاث دوراتٍ متتالية**
              #    بالمُدخَل نفسِه ⇒ ثمانيَ عشرةَ تشغيلةً ضاعت. والقاعدةُ نصّاً:
              #    **لا تكرارَ اختبارٍ سقط بلا مُدخَلٍ مختلفٍ بسببٍ مقيسٍ مكتوب.**
              # ⭐ و`ctc_align` هو المُدخَلُ المختلف: محاذاةٌ قسريّةٌ لا تحتاج
              #    سكتةً لتجد حدَّ الآية، وقد كسرت من قبلُ قرّاءً ردَّهم المحرّكُ
              #    القديم. وله `probe_surahs` = **سبرٌ بلا رفع** ⇒ يُقاس أوّلاً
              #    بلا أن يمسَّ المسرحَ ولا الدلوَ ولا حارساً.
              # ⚖️ مجّانيّ: مستودعٌ عامّ وعدّاءُ `ubuntu-latest` القياسيّ.
              "ctc_align.yml",
              # 🔎 **أُضيف 2026-10-02 (‏عاصم س38):** سبرُ «أيُّ آيةٍ تُسمع أين» لملفٍّ واحدٍ
              #    بـ`ctc_heard_map.py --probe` — قارئٌ محضٌ بلا سرٍّ ولا دلو (‏`contents: read`)،
              #    يقيس الزيادةَ والتكرارَ في تسجيلٍ طويلٍ قبل أن يُبنى عليه مرشّح.
              "ctc_heard_probe.yml",
              # قارئ بيانات مصدر واحد/دفعة محدودة: بلا نموذج أو دلو أو cache أو artifacts.
              "source_metadata_probe.yml",
              # ⚖️🐦 **أُضيف 2026-10-13 (‏بند ج-1 · D-756):** شاهدُ LLR بالهدهد على مسطرة المتعلّمين —
              #    قياسٌ لا تفعيل: يقرأ من مصادرَ عامّةٍ (HF · R2 العامّ) ويودع جوابَه في `ops/out/tasmi_llr_judge/`.
              #    بلا سرٍّ ولا دلوٍ ولا artifacts ولا cache · ubuntu-latest · وظيفةٌ واحدةٌ بمهلة 75 دقيقة.
              "tasmi-llr-judge.yml"}
# ⛔ والأدواتُ المسموحةُ كلُّها **قارئةٌ أو محكومةٌ بحُرّاسها** — لا صدفةَ فيها.
# ⛔ و`certify_catalog.py` منها (‏أُضيف 2026-09-13 ‏19:0xZ بقياس): الكتالوجُ
#    `catalog/reciters.json` هو ما **يقرؤه التطبيق**، وحقلاه `ayahCoverage`
#    و`ayahCertified` لا يتحرّكان إلا به. وقِيس أنّ بصمتَه بقيت
#    `a6b98a08a789` (‏77,432 بايتاً) **خمساً وعشرين ساعة** — أي أنّ ليلةَ
#    استرجاع الـ310 آية لم تصل إلى المستخدم أصلاً، **لأنّ لا بابَ سحابيّاً
#    كان يفتحه**. وهو محكومٌ بحُرّاسه (يُسقط التوليد كلَّه إن شُهد لمن لا حكمَ
#    لبصمته، ولا يمسّ غير الحقلين)، فإدخالُه لا يُضعف حارساً.
ALLOWED_TOOLS = {"index_qa/set_reciter_files.py",  # يضع files في مدخلٍ واحدٍ من catalog/reciters.json بحُرّاس (اتّفاق الفهرس · HEAD 114 · نسخة احتياطية · لا تغيّر غير الحقل) — 2026-10-23
                 "index_qa/heard_sweep_table.py", "index_qa/source_inventory.py", "ci_fleet/promote_atomic.py",  # رفعٌ وترقيةٌ وإعادةُ تجميدٍ في عمليّةٍ واحدة (2026-10-17)
                 "index_qa/adopt_noah_source_gap.py",  # اعتماد مقيد بالبصمة بعد نجاح كامل الفحص 37405972254
                 "ci_fleet/cancel_superseded_tail_qa.py", "ci_fleet/cancel_superseded_ctc_qa.py", "ci_fleet/rerun_stale_review.py",  # retry only pinned read-only review after stale diagnosis
                 "index_qa/export_index_bytes.py",  # SHA-pinned raw read only
                 "index_qa/resync_probe.py",  # 🩺 سبرُ عطب إطارات ملفّ صوت (fixV 2026-10-05)
                 "ci_fleet/package_catalog_review.py", "ci_fleet/akri_soundcloud_native_compare.py", "ci_fleet/akri_publisher_metadata.py", "ci_fleet/publisher_link_inventory.py", "ci_fleet/akri_rss_direct_source_search.py", "ci_fleet/akri_independent_source_search.py", "ci_fleet/cancel_duplicate_kalbani_qa.py", "ci_fleet/cancel_duplicate_free_qa.py", "ci_fleet/qa_recover_stalled.py", "index_qa/repair_review.py", "ci_fleet/refreeze.py", "tasmi_bench/cloud_stream_probe.py",  # 🩺 صحّةُ التفريغ السحابيّ (2026-09-25)  # يسدّ تجميداً رُفع بلا ترقية (2026-09-23)
                 "index_qa/run.py", "index_qa/stage_transform.py", "index_qa/promote_verified_transform.py", "ci_fleet/alt_source.py", "ci_fleet/find_sources.py",  # 🔁 تسجيلٌ بديلٌ للقارئ نفسه (2026-09-25)
                 "index_qa/triage.py", "index_qa/promote.py", "index_qa/openers_coverage.py", "index_qa/gap_probe.py", "ci_fleet/web_probe.py",  # 🕋 شواهدُ المطالع على المنشور (2026-09-29)
                 "index_qa/certify_catalog.py", "index_qa/heard_gate.py", "index_qa/census_parts_diag.py",  # ⚖️ قارئٌ محض: حكمُ بوّابة السماع كما تحكم الترقية (fixT)
                 "index_qa/bucket_watch.py", "index_qa/drop_surah.py",
                 # ⚖️ أُضيف 2026-10-05 (fixV): ذيلٌ غيرُ متلوٍّ في ملفّه يُحذف ويُعلَن (‏يكتب الاختبارَ وحده، بحُرّاس declared_truncated_tail).
                 "index_qa/truncate_tail.py", "index_qa/index_header.py",
                 # ⚖️ fixV 2026-10-05: تثبيتُ بدء آياتٍ على أداءٍ مسموعٍ مقيس في تسجيلٍ مكرَّر (يكتب الاختبارَ وحده؛ يلزمه الإحصاءُ الشامل).
                 "index_qa/pin_heard.py", "index_qa/census_gate_check.py", "index_qa/graft_surah_range.py", "index_qa/graft_surahs.py",  # pT 2026-10-14: زرعُ سورٍ كاملةٍ من متبرِّعٍ مشتقٍّ إلى timings-staging/ وحده
                 "index_qa/recheck_published.py", "index_qa/recheck_pool.py",  # 🔎 pR 2026-10-09: إعادةُ فحص المنشور بالحرّاس المشدَّدة (عرضٌ فقط، قارئ محض)
                 "index_qa/low_coverage_scan.py", "index_qa/dup_sha_sweep.py",
                 "index_qa/duration_profile.py", "index_qa/reciter_evidence.py",
                 "index_qa/dump_state.py", "index_qa/show_entries.py", "index_qa/heard_pub_rows.py", "index_qa/clamp_file_end.py", "index_qa/material_probe.py",
                 # ⚖️ أُضيف 2026-09-28: مسبارُ صوتِ سورةٍ قارئٌ محض (‏مادّةٌ أم أداة؟) — لا دلوَ ولا سرّ.
                 "index_qa/surah_audio_probe.py",
                 # ⚖️ أُضيف 2026-09-28: مسبارُ عنصرٍ منفردٍ في archive.org (‏بياناتٌ ومدّةٌ ونوعُ معدّل) — قارئٌ محض.
                 "ci_fleet/ia_item_probe.py",
                 "index_qa/_debug_state_for.py", "index_qa/_debug_openers_for.py",
                 "ci_fleet/restore_loop.py", "ci_fleet/status_page.py",
                 # ⛔ **أُضيف 2026-09-20:** قراءةُ مخرَجِ تشغيلةٍ نصّاً.
                 #    سبرُ CTC بلا رفعٍ يضع حكمَه في مخرَجٍ صغير، وسجلُّ الشوط
                 #    يُقصّ من ذيله فلا تصل الأسطرُ الحاسمة ⇒ تُقرأ «نجاحاً»
                 #    بلا أثرٍ منظور. ⚖️ وهو **قارئٌ محض**: gh api قراءةً وفكُّ
                 #    ضغطٍ في الذاكرة وطباعةٌ بسقفِ بايتات — لا يمسّ الدلوَ ولا حارساً.
                 "ci_fleet/show_artifact.py",
                 # ⛔ **أُضيف 2026-09-21:** طباعةُ مصدر القارئ من الكتالوج.
                 #    خُمّن قالبُ رابطٍ مرّةً فسقطت محاذاةُ CTC بأجزائها الأربعة
                 #    (404 على كلّ سورة) — وأخطرُ من الهدر أنّ قالباً خاطئاً
                 #    قد يحاذي صوتَ قارئٍ آخر، وذاك تحريفٌ لا نقص.
                 "ci_fleet/show_source.py",
                 # ⛔ **أُضيف 2026-09-19:** اختبارُ حارسِ «بصمات الصوت n/114».
                 #    وأُدخل لأنّ قاعدةَ `CLAUDE.md` (بند 2) توجب اختبارَ أيّ
                 #    تعديلٍ على حارسٍ **نصّاً قبل استعماله** — والحارسُ يعمل على
                 #    العدّاء لا هنا، فاختبارُه حيث يعمل شرطُ صحّةٍ لا زينة.
                 # ⚖️ وهو **قارئٌ محض**: يبني فهارسَ وهميّةً في الذاكرة ويقارن
                 #    مخرَجَ `structural`، لا يمسّ الدلوَ ولا يكتب بايتاً واحداً.
                 "index_qa/test_sha_count_declared_drop.py",
                 # ⛔ **أُضيف 2026-09-19:** قياسُ البسملة من فهرس القارئ نفسِه.
                 #    والقاعدةُ في `CLAUDE.md` تأمر به منذ مدّة لكنّها كانت
                 #    **وصيّةً بلا أداة**، والسُّلَّمُ البديل (`basmala.yml`) سقفُه
                 #    3000م.ث فيكذب على مَن بسملتُه أطول (husary_douri 10160م.ث).
                 # ⚖️ وهو **قارئٌ محض**: يقرأ الفهرسَ ويطبع وسيطاً، لا يكتب شيئاً.
                 "index_qa/basmala_from_index.py",
                 # ⛔ **أُضيف 2026-09-20 (شكوى المالك):** تدقيقُ الكتالوج بعينِ
                 #    المستخدم — أسماءٌ لاتينيّةٌ تُعرض للقارئ العربيّ، وقرّاءٌ
                 #    لا يُشغَّل عندهم شيء. وحُرّاسُنا كلُّها تسأل «أصحيحٌ
                 #    التوقيت؟» ولا تسأل «أيصلح هذا للعرض والتشغيل؟».
                 # ⚖️ قارئٌ محض: يقرأ catalog/reciters.json ويعدّ العطب، لا يكتب.
                 "index_qa/catalog_audit.py",
                 # ⛔ **أُضيف 2026-09-20:** كاشفُ **المرشَّح اليتيم** — ناجٍ
                 #    بنيويّاً بلا بوّابةٍ صوتيّة. ووُلد من عطبٍ مقيس: فهرسُ
                 #    `a_binaoun.3987d0e4` نجا 09-15 وبقي خمسةَ أيّامٍ منسيّاً
                 #    بينما المنشورُ عند المستخدم 2246/6236 مدخلاً ⇒ 3924 آيةً
                 #    جاهزةً محجوبة. ولا حلقةَ كانت تسأل «أيُّ ناجٍ بلا بوّابة؟».
                 # ⚖️ قارئٌ محض: يسرد `timings-staging/` و`state/` ويطبع قائمةَ
                 #    عملٍ، لا يكتب بايتاً ولا يُطلق تشغيلةً ولا يُجيز ترقية.
                 "index_qa/orphan_candidates.py",
                 "index_qa/test_orphan_filter.py",
                 "ci_fleet/test_agent_cmd_tries.py",
                 "ci_fleet/test_state_declared_reasons.py",
                 "ci_fleet/test_agent_cmd_push.py",
                 "ci_fleet/test_source_ratio_refs.py",
                 "ci_fleet/test_needs_restore.py",
                 "index_qa/verdict_probe.py",
                 # fixW 2026-10-08: قارئٌ محضٌ لحكم التجميع (promote.pooled_samples) على أملاح مرشّح
                 "index_qa/pool_probe.py", "index_qa/pool_defects.py",
                 # 🔎 **أُضيف 2026-10-02 (أمرُ المالك: فحصٌ شاملٌ للفهرسة):** مسحٌ واحدٌ لكلّ المنشور
                 #    بالبنود الخمسة (هويّة · بنية · قاعدةُ البتر · أحكامُ الصوت على البصمة · مؤشّراتُ المدد).
                 # ⚖️ قارئٌ محض: يقرأ الدلوَ وstate/ والعنوانَ العامّ ويكتب تقريرَه في ops/out/ وحدَه؛
                 #    لا يمسّ فهرساً ولا حارساً ولا عتبة. واختبارُه بلا شبكة في test_full_audit.py.
                 "index_qa/full_audit.py",
                 "index_qa/catalog_source_audit.py",  # bounded complete source identity read only
                 "index_qa/test_full_audit.py",  # أُعيد 2026-10-08: كان قد سقط داخل التعليق أعلاه
                 # تدقيق شامل قارئ وقياس تخزين Actions؛ لا رفع ولا تشغيل صوتي ولا تعديل للحراس.
                 "index_qa/completion_audit.py", "ci_fleet/free_compute_audit.py",
                 "index_qa/test_declared_sha_fatal.py",
                 "ci_fleet/repo_parity.py",
                 # 🔎 أُضيف 2026-10-03 (تدقيقُ الجولة الثانية · أمرُ المالك): تصديرُ المنشور خاماً للتحليل المستقلّ.
                 # ⚖️ قارئٌ محض: يقرأ الدلوَ وstate/ وترويساتِ الصوت بطلبِ مدى، ويكتب في ops/out/audit-r2/ وحدَه.
                 "index_qa/audit_export.py",
                 # proofZ 2026-10-09: مسحٌ رخيص لمدّة الملفّ الصوتيّ مقابل نهاية الفهرس (قارئٌ محض: HEAD وطلب مدى 64ك.ب).
                 "index_qa/duration_sweep.py",
                 # e5 2026-10-17: مدُّ نهاية آخر آية قصّتها المحاذاةُ عند مدّة الترويسة؛ يرفع إلى staging فقط بـstage_transform وحُرّاسه.
                 "index_qa/extend_tail.py", "index_qa/header_clip.py",
                 # 🛡️ 2026-10-23: حارسُ بصمة المرآة — يحجب قصاصاتِ ملفّات المرآة المخالفة لـaudioSha256 (حجبٌ رتابيّ في المانيفست وحدَه بنسخةٍ احتياطية).
                 "index_qa/mirror_sha_guard.py"}
MAX_OUT = 200_000            # حرفاً — جوابٌ أطولُ يُقصّ ويُعلَن قصُّه

# ⛔ (تحصين 2026-10-21) العدّاءُ يحمل `secure/r2_credentials.json` وأجوبةُ ops/out تُدفع إلى مستودعٍ عامّ:
#    فلا وسيطٌ لأيّ أداةٍ يشير إلى secure أو r2_credentials أو يصعد بـ`..` أو يقصد مواضعَ حسّاسةً مطلقة،
#    ولا جوابٌ يُكتب قبل حجبِ قيم السرّ المعروفة منه. (نصوصُ الأسباب الحرّة بـ«53:39..62» سليمة: المنعُ بمكوّنِ مسارٍ كاملٍ لا بنصٍّ.)
_SENSITIVE_ABS = ("/etc", "/proc", "/sys", "/dev", "/root", "/home", "/run", "/var", "/boot", "/mnt")
SECRET_FILE = ROOT / "secure" / "r2_credentials.json"


def _forbidden_path_arg(args):
    """أوّلُ وسيطٍ يمسّ secure/r2_credentials/`..`/موضعاً مطلقاً حسّاساً أو None (لكل الأدوات)."""
    import posixpath
    for a in args:
        a = str(a)
        for v in {a, a.split("=", 1)[-1]}:
            low = v.lower().replace("\\", "/")
            parts = [x for x in low.split("/") if x]
            if "r2_credentials" in low or "secure" in parts or ".." in parts:
                return a
            if low.startswith("/"):
                n = posixpath.normpath(low)
                inside = n == str(ROOT).lower() or n.startswith(str(ROOT).lower() + "/")  # المستودعُ نفسُه تحت /home/runner
                if not inside and any(n == b or n.startswith(b + "/") for b in _SENSITIVE_ABS):
                    return a
    return None


def _secret_values():
    """قيمُ السرّ النصّيّة (≥8 حروف) من secure/r2_credentials.json، الأطولُ أوّلاً؛ فارغةٌ إن غاب الملفّ."""
    try:
        data = json.loads(SECRET_FILE.read_text(encoding="utf-8"))
    except Exception:                                             # noqa: BLE001
        return []
    out = set()

    def walk(x):
        if isinstance(x, str):
            if len(x.strip()) >= 8:
                out.add(x.strip())
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    return sorted(out, key=len, reverse=True)


def redact(text):
    """يحجب كلَّ ظهورٍ لقيمةِ سرٍّ معروفةٍ بـ*** قبل أن يُكتب الجوابُ أو يُطبع."""
    for v in _secret_values():
        text = text.replace(v, "***")
    return text


def _atomic_write(path, text):
    """كتابةٌ ذرّيّة (ملفٌّ مؤقّتٌ خارج ops/out ثمّ استبدال): الدفعُ الجماعيّ قد يُجرى
    بينما معالجٌ في خيطٍ آخر يكتب، فلا يُودَع أبداً ملفٌّ نصفُ مكتوب."""
    path = Path(path)
    tmp = ROOT / "ops" / f".tmp_{os.getpid()}_{path.name}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), **kw)
    return p.returncode, (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")


def do_dispatch(c):
    wf = c.get("workflow", "")
    if wf not in ALLOWED_WF:
        return 2, f"⛔ سيرُ عملٍ غيرُ مسموح: {wf!r}\nوالمسموح: {sorted(ALLOWED_WF)}"
    # ⛔⛔ **يُرشَّح المُدخَلُ بجواب GitHub نفسِه لا بتحليلِ ملفّ** (‏2026-09-14):
    #    العلّةُ أنّ `CLAUDE.md` يأمر بتمرير `reason` مع كلّ إطلاق و**بعضُ** سيور العمل
    #    تُعلنه وبعضُها لا ⇒ `HTTP 422: Unexpected inputs provided: ["reason"]` (وقع مرّتين).
    # ⛔ **وعلاجي الأوّلُ كان أسوأَ من العطب**: حلّلتُ الملفَّ بـPyYAML، **وهي غيرُ مثبَّتةٍ
    #    في بيئة العدّاء** ⇒ `No module named 'yaml'` فسقط كلُّ إطلاقٍ فاشلاً **مغلقاً**.
    #    ⭐ والدرس: *حارسٌ يعتمد على ما لا يضمن وجودَه يصير هو العطب* — ومَن أضاف اعتماداً
    #    جديداً في مسارٍ حرجٍ فليسأل أوّلاً: **أهو موجودٌ حيث يعمل؟**
    # ⇒ **فلا تحليلَ ولا اعتماد**: يُجرَّب الإطلاقُ، فإن ردّ 422 مسمّياً المُدخَلاتِ غيرَ
    #    المُعلَنة أُسقطت **بأسمائها من الرسالة نفسِها** وأُعيد **مرّةً واحدة**. والمصدرُ
    #    هو GitHub لا ظنُّنا، ولا يحتاج شيئاً مثبَّتاً.
    given = dict(c.get("inputs") or {})

    def _fire(inp):
        a = ["gh", "workflow", "run", wf]
        for k, v in inp.items():
            a += ["-f", f"{k}={v}"]
        # إطلاقاتٌ متوازية ⇒ قد يردّ GitHub بحدّ المعدّل الثانويّ؛ تُعاد المحاولةُ بعد انتظار (لا يُسقط أمراً).
        for _t in range(4):
            r = run(a)
            if r[0] == 0 or not re.search(r"rate limit", r[1], re.I):
                break
            import time as _tm
            _tm.sleep(20 * (_t + 1))
        return r

    rc, out = _fire(given)
    if rc != 0 and "Unexpected inputs provided" in out:
        bad = re.findall(r'"([^"]+)"', out[out.index("Unexpected inputs provided"):])
        dropped = {k: given.pop(k) for k in bad if k in given}
        if dropped:
            rc, out2 = _fire(given)
            out = ("ℹ️ مُدخَلاتٌ لا يُعلنها " + wf + " فأُسقطت وأُعيد الإطلاق:\n"
                   + "".join(f"   · {k} = {v}\n" for k, v in dropped.items()) + out2)
    return rc, out


PROMOTE_FORBIDDEN_ARGS = ("--override", "--allow-shrink")


def _forbidden_promote_args(tool, args):
    """(صيد 2026-10-09) أوّلُ وسيطٍ ممنوعٍ لأداة الترقية أو None.

    يُمسك الصيغتين `--x v` و`--x=v` وكذلك **الاختصارَ** (argparse يقبل
    `--over` و`--allow-s` بادئةً فريدة)، ويطبّع مسارَ الأداة فلا يمرّ
    `index_qa/./promote.py` ولا `./index_qa/promote.py`."""
    import posixpath
    if posixpath.normpath(tool.replace("\\", "/")).lstrip("./") != "index_qa/promote.py":
        return None
    for a in args:
        if not a.startswith("--"):
            continue
        name = a.split("=", 1)[0]
        if len(name) >= 3 and any(f.startswith(name) for f in PROMOTE_FORBIDDEN_ARGS):
            return a
    return None


def guard_tool(tool, args):
    """(rc, رسالة) إن رُدّ الأمر، وإلا None — حراسةٌ واحدةٌ مشتركةٌ بين القناة وagent_tool.yml
    (ALLOWED_TOOLS و_forbidden_promote_args بلا أي إرخاء)."""
    if tool not in ALLOWED_TOOLS:
        return 2, f"⛔ أداةٌ غيرُ مسموحة: {tool!r}\nوالمسموح: {sorted(ALLOWED_TOOLS)}"
    bp = _forbidden_path_arg(args)
    if bp:
        return 2, (f"⛔ (تحصين 2026-10-21) وسيطٌ يمسّ مجلّد secure أو r2_credentials أو `..` "
                   f"أو موضعاً مطلقاً حسّاساً: {bp!r} — مرفوضٌ لكل الأدوات.")
    bad = _forbidden_promote_args(tool, args)
    if bad:
        return 2, ("⛔ (صيد 2026-10-09) وسيطٌ ممنوعٌ عبر القناة لـ promote.py: "
                   f"{bad!r} — التجاوزُ وخفضُ المنشور قرارُ المالك المباشر لا أمرُ وكيل. "
                   "يبقى `--unfreeze` و`--allow-truncated` وغيرُهما.")
    return None


def run_tool(tool, args):
    """يشغّل أداةً مسموحةً بعد الحراسة — الدالةُ المشتركةُ للقناة وagent_tool.yml."""
    args = [x if isinstance(x, str) else str(x) for x in (args or [])]
    refused = guard_tool(tool, args)
    if refused:
        return refused
    return run([sys.executable, str(ROOT / "tools" / tool), *args])


# أمرُ tool يُفوَّض إلى agent_tool.yml (تزامنٌ لكل name) فلا يحجز قناةَ الأوامر المتسلسلة.
TOOL_WORKFLOW = "agent_tool.yml"
DEFERRED = None      # rc=None من معالجٍ ⇒ الجوابُ يكتبه agent_tool وحده، فلا يكتب main ملفاً
_NAME_RE = re.compile(r"[A-Za-z0-9_.\-]{1,120}")


def do_tool(c):
    tool = c.get("tool", "")
    args = [x if isinstance(x, str) else str(x) for x in (c.get("args") or [])]
    refused = guard_tool(tool, args)          # الرفضُ هنا يكتب جوابَه فوراً كما كان
    if refused:
        return refused
    name = c.get("_name", "")
    if not _NAME_RE.fullmatch(name or ""):
        return 3, f"⛔ اسمُ الأمر لا يصلح لملفّ جواب: {name!r}"
    import time as _t
    for _try in range(4):        # خطأ 5xx عابر من GitHub (وقع 2026-10-20: HTTP 500) لا يُسقط أمراً
        rc, out = run(["gh", "workflow", "run", TOOL_WORKFLOW, "-f", f"name={name}",
                       "-f", f"tool={tool}", "-f", "args=" + json.dumps(args, ensure_ascii=False)])
        if rc == 0 or not re.search(r"HTTP 5\d\d|rate limit", out, re.I):   # 5xx أو حدُّ المعدّل الثانويّ (التوازي)
            break
        _t.sleep(15 * (_try + 1))
    if rc != 0:
        return rc, "⛔ تعذّر إطلاق agent_tool.yml:\n" + out
    print(f"↪ فُوّض {name} إلى {TOOL_WORKFLOW} (يكتب ops/out/{name}.txt بنفسه)")
    return DEFERRED, out


def tool_main():
    """نقطةُ دخول agent_tool.yml: NAME وTOOL وARGS(JSON) من البيئة؛ يكتب الجوابَ بالصيغة نفسها ويدفعه."""
    name, tool = os.environ.get("NAME", ""), os.environ.get("TOOL", "")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not _NAME_RE.fullmatch(name):
        print(f"⛔ اسمٌ غيرُ صالح: {name!r}"); sys.exit(1)
    try:
        args = json.loads(os.environ.get("ARGS") or "[]")
        if not isinstance(args, list):
            raise ValueError("args ليست قائمة")
        rc, out = run_tool(tool, args)
    except Exception:                                             # noqa: BLE001
        rc, out = 3, "⛔ تعذّر تنفيذُ الأمر:\n" + traceback.format_exc()
    out = redact(out)
    if len(out) > MAX_OUT:
        out = out[:MAX_OUT] + f"\n… [قُصّ الجواب عند {MAX_OUT} حرفاً]"
    print(out[:4000])
    (OUT_DIR / f"{name}.txt").write_text(f"# rc={rc}\n{out}", encoding="utf-8")
    _push_answer(name, api_paths=[f"ops/out/{name}.txt"])


def _gap_surahs(entries):
    """{سورة: عددُ آياتها الغائبة} للسور الحاضرة الناقصة والغائبة معاً — قراءةٌ محضة."""
    import gzip as _gz
    idx = json.loads(_gz.decompress((ROOT / "core" / "quran" / "src" / "main" / "assets"
                                     / "quran" / "index.jz").read_bytes()).decode("utf-8"))
    want = {s["n"]: s["ayahs"] for s in idx["surahs"]}
    have = {}
    for e in entries:
        s = int(e["ayahId"].split(":")[0])
        have[s] = have.get(s, 0) + 1
    return {str(s): want[s] - have.get(s, 0) for s in sorted(want) if have.get(s, 0) < want[s]}


def do_state(c):
    """جردٌ كاملٌ من الدلو — به يرى الوكيلُ ما لا يصله اعتمادُه."""
    sys.path.insert(0, str(ROOT / "tools" / "index_qa"))
    from run import s3, fetch_index                                   # noqa: E402
    cl, b = s3()
    pub, per = {}, {}
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if k.endswith(".jz") and k.count("/") == 2:
                riw = k.split("/")[1]
                pub[(riw, k.split("/")[2][:-3])] = o["Size"]
                per[riw] = per.get(riw, 0) + 1
    cat = json.loads(cl.get_object(Bucket=b, Key="catalog/reciters.json")["Body"].read())
    # ⭐ الهدفُ يعدّ قرّاءَ الفهرس وحدَهم: قارئُ «الآية» صوتُه ملفٌّ لكلّ آيةٍ فلا فهرسَ له
    #    ولا يدخل في 162/180 — وكان غيابُ هذا التفصيل يُوهم أنّ قرّاءً سقطوا (سؤالُ المالك 05:40Z).
    catalog_total = sum(len(r.get("reciters", [])) for r in cat["riwayat"])
    ayah_mode = [f'{r.get("id") or r.get("riwaya")}/{rc.get("id")}'
                 for r in cat["riwayat"] for rc in r.get("reciters", [])
                 if rc.get("mode") == "ayah"]
    total = catalog_total - len(ayah_mode)
    gaps, read_errors = {}, {}
    fetched_count = 0
    for (riw, rid) in sorted(pub):
        key = f"timings/{riw}/{rid}.jz"
        try:
            idx, _ = fetch_index(key)
        except Exception as ex:                                      # noqa: BLE001
            # ⛔ وجود الملف لا يثبت قراءة محتواه؛ لا يُخفى تعذّر القراءة من الجرد.
            read_errors[key] = f"{type(ex).__name__}: {ex}"
            continue
        fetched_count += 1
        srs = {int(e["ayahId"].split(":")[0]) for e in idx["entries"]}
        miss = [s for s in range(1, 115) if s not in srs]
        if miss or len(idx["entries"]) < 6236:
            tr = idx.get("transform") or {}
            # ⛔⛔ **عطبُ تضليلٍ مقيسٌ 2026-09-20:** كان `reasonCode` يُقرأ من
            #    ترويسة `transform` **وحدَها** — وهي لا تُكتب إلا حين يُنتَج
            #    الفهرسُ بـ`drop_surah.py`. أمّا الفهرسُ الذي يُعلن نقصَه داخل
            #    `missing.byReason` (‏وهو ما يقرؤه `run.py` ويطبعه «بعذرٍ
            #    معلَن») فكان يُقرأ هنا **«بلا سببٍ مُعلَن»** وهو مُعلِنٌ فعلاً.
            # 🔥 والثمنُ دُفع اليومَ: عرضتُ على المالك «قراراً» مبنيّاً على أنّ
            #    `nufais` يُغيّب 46 و47 **صامتاً**، والحقُّ أنّ منشورَه يُعلن
            #    **73 من 81** غياباً بعذرِ البتر المصدريّ — فالسؤالُ كان على
            #    باطل. ⭐ **وجردٌ يقول «لا سبب» وهو لم يبحث عنه في موضعه
            #    يصنع قراراتٍ كاذبةً واثقة.**
            # ⚖️ ولا يُخفى شيء: يُطبع مصدرُ العذر وتفصيلُه، ويبقى `reasonCode`
            #    على معناه الأوّل (ترويسةُ التحويل) فلا يُخلط البابان.
            mh = idx.get("missing") or {}
            by_reason = mh.get("byReason") if isinstance(
                mh.get("byReason"), dict) else {}
            excused = sum(int(v or 0) for v in by_reason.values())
            # ⛔ **وبقيّةُ العطب نفسِه:** فهرسٌ أُنتج بـ`drop_surah` قد يحمل
            #    `transform.op = "drop_surah:24,107"` **بلا** `reasonCode` —
            #    فيبقى الحقلُ `None` ويُقرأ «بلا سببٍ مُعلَن» وهو مُعلِنٌ
            #    بترويسته. الشاهد: `qalun/akri_qalun` المنشور.
            #    ⇒ يُشتقّ من `op` عند غيابه، ويُطبع `transformOp` صريحاً.
            rcode = tr.get("reasonCode")
            if not rcode and str(tr.get("op") or "").startswith("drop_surah"):
                rcode = "DECLARED_BY_TRANSFORM"
            gaps[f"{riw}/{rid}"] = {"entries": len(idx["entries"]),
                                    "missingSurahs": miss,
                                    "reasonCode": rcode,
                                    "transformOp": tr.get("op"),
                                    "declaredReasons": by_reason or None,
                                    "declaredCount": excused,
                                    "undeclaredCount": max(
                                        0, 6236 - len(idx["entries"]) - excused),
                                    # ⭐ (‏2026-09-24، مناوبةُ الفهرسة): محرّكُ المنشور وسورُ النقص.
                                    #    CTC حتميٌّ على الصوت نفسِه، فإعادتُه على فهرسٍ **منشورٍ
                                    #    بـCTC** تُعيد النقصَ نفسَه وتحرق أربعَ وظائفَ ساعةً ونصفاً
                                    #    بلا مدخلٍ واحد. فالمحرّكُ يُقرأ هنا لتُختار الأهدافُ به.
                                    "engine": idx.get("engineVersion"),
                                    "gapSurahs": _gap_surahs(idx["entries"])}
    # ⭐⭐ **الباقي يُسمَّى بالاسم لا يُعَدّ فحسب** (‏2026-09-14): «المنشور 162/180» رقمٌ
    #    لا يقول **مَن** الثمانيةَ عشر، فظُنَّ مراراً أنّ موجةَ `reciters_gen1_fix10.tsv`
    #    ترفعه — وهي **استبدالُ جيلٍ لقرّاءَ منشورين سلفاً** (‏`aamer` و`hafz` وغيرُهما في
    #    `timings/` أصلاً) فلا ترفع العدَّ بحقّ. ⇒ فالقائمةُ تُشتقّ **بالطرح من الدلو**
    #    كما يأمر `CLAUDE.md`، وتُكتب هنا حتى لا تُخمَّن مرّةً أخرى.
    missing = sorted(
        f'{r.get("id") or r.get("riwaya")}/{rc.get("id")}'
        for r in cat["riwayat"] for rc in r.get("reciters", [])
        if rc.get("mode") != "ayah"
        and ((r.get("id") or r.get("riwaya")), rc.get("id")) not in pub
    )
    read_complete = not read_errors and fetched_count == len(pub)
    st = {"generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
          "readErrors": read_errors, "fetchedCount": fetched_count,
          "readComplete": read_complete,
          "published": len(pub), "target": total,
          "missingCount": len(missing), "missingIds": missing,
          "catalogTotal": catalog_total,
          "ayahModeExcluded": len(ayah_mode), "ayahModeIds": ayah_mode,
          "byRiwaya": per, "indexesWithGaps": gaps}
    _atomic_write(OUT_DIR / "state.json",
                  redact(json.dumps(st, ensure_ascii=False, indent=1)))
    _miss = ("\n⛔ **الباقي بالاسم** (" + str(len(missing)) + "): "
             + ("، ".join(missing) if missing else "لا شيء — ملفات القرّاء موجودة"))
    _reads = (f"قُرئ {fetched_count}/{len(pub)} فهرساً · أخطاء القراءة: {len(read_errors)}"
              + ("" if read_complete else " — ⛔ الجرد غير مكتمل؛ راجع readErrors"))
    return (0 if read_complete else 1), (f"المنشور {len(pub)}/{total}{_miss}\n"
               f"(الكتالوج {catalog_total} قارئاً · "
               f"منهم {len(ayah_mode)} بوضع الآية لا فهرسَ لهم) · {per}\n"
               f"{_reads}\n"
               f"فهارسُ فيها نقص ضمن المقروء: {len(gaps)} — التفصيلُ في ops/out/state.json\n"
               "هذا الجرد لا يشهد بصحة التوقيت أو جودة الفهرسة.")


HANDLERS = {"dispatch": do_dispatch, "tool": do_tool, "state": do_state}


# (تسريع 2026-10-22) المعالجاتُ كلُّها خفيفة (إطلاقُ gh أو تفويضٌ أو جردٌ للقراءة)،
# فتُنفَّذ كلُّ دفعةٍ من الأوامر معاً بدل التسلسل، والدفعُ جماعيٌّ:
# دفعةُ سجلّ المحاولات واحدة، ثمّ دفعةٌ لكلّ ما اكتمل معاً.
# ⛔ الحارسان باقيان بحالهما: المحاولاتُ تُسجَّل **وتُدفع قبل** التنفيذ لكل دفعة،
#    وكلُّ جوابٍ يُكتب في ملفّه ويُودَع بعد اكتماله لا في آخر الشوط.
# ⛔ كلُّ عملياتِ git ونقلِ الملفّات في الخيط الرئيسيّ وحدَه؛ الخيوطُ تحسب (rc, out) فقط.
POOL = max(1, int(os.environ.get("AGENT_CMD_POOL", "4")))


def _execute(f, name):
    """ينفّذ أمراً واحداً ويُرجع (rc, out) مُحجوبَ الأسرار ومقصوصاً — بلا لمس git ولا الملفّات."""
    try:
        c = json.loads(f.read_text(encoding="utf-8"))
        c["_name"] = name
        h = HANDLERS.get(c.get("action"))
        if not h:
            rc, out = 2, (f"⛔ فعلٌ غيرُ معروف: {c.get('action')!r} — "
                          f"والمعروف: {sorted(HANDLERS)}")
        else:
            rc, out = h(c)
    except Exception:                                             # noqa: BLE001
        rc, out = 3, "⛔ تعذّر تنفيذُ الأمر:\n" + traceback.format_exc()
    out = redact(out)
    if len(out) > MAX_OUT:
        out = out[:MAX_OUT] + f"\n… [قُصّ الجواب عند {MAX_OUT} حرفاً]"
    return rc, out


def main():
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    cmds = sorted(p for p in CMD_DIR.glob("*.json"))
    if not cmds:
        print("لا أمرَ جديد."); return
    for k in range(0, len(cmds), POOL):
        wave = []                                  # (ملفّ، اسم، رقمُ المحاولة)
        retired = []
        for f in cmds[k:k + POOL]:
            name = f.stem
            # ⛔ **عطبٌ مقيسٌ 2026-09-25**: دمجُ `origin/main` داخل `_push_answer` يجلب ما نقله
            #    شوطٌ سابقٌ إلى `done/`، فيختفي الأمرُ من تحت القائمة المحسوبة ⇒ أمرٌ غاب
            #    ملفُّه نفّذه غيرُنا، فيُتخطّى ولا يُعاد.
            if not f.exists():
                print(f"⏭ {name}: نُفّذ في شوطٍ آخر (نُقل ملفُّه) — يُتخطّى")
                continue
            # ⛔⛔ **حارسُ المحاولات — عطبٌ مقيسٌ 2026-09-20:** أمرٌ أبطأُ من `timeout-minutes`
            #    لا يكتمل أبداً فيحجز الطابورَ أبداً. تُسجَّل المحاولةُ **قبل** التنفيذ
            #    وتُدفع، فإن مات الشوطُ بقي السجلُّ شاهداً، وبعد `MAX_TRIES` يُنحّى الأمرُ
            #    بجوابٍ يقول سببَه ولا يُحذف صامتاً. والأمرُ الناجحُ يمحو عدّادَه.
            tries_p = OUT_DIR / f"{name}.attempts"
            tries = 0
            try:
                tries = int(tries_p.read_text(encoding="utf-8").strip() or 0)
            except Exception:                                     # noqa: BLE001
                tries = 0
            if tries >= MAX_TRIES:
                msg = (f"⛔ نُحّي بعد {tries} محاولةٍ لم تكتمل — الأمرُ أبطأُ من سقف "
                       f"الوظيفة (`timeout-minutes`) فكان يحجز الطابورَ أبداً.\n"
                       f"⚖️ ولم يُحذف: جوابُه هذا، وملفُّه في `ops/commands/done/`، "
                       f"ويُعاد بأداةٍ أسرعَ أو بسقفٍ أعلى بقرارٍ مكتوب.")
                print(msg)
                _atomic_write(OUT_DIR / f"{name}.txt", f"# rc=98\n{msg}")
                tries_p.unlink(missing_ok=True)
                f.replace(DONE_DIR / f.name)
                retired.append(name)
                continue
            tries_p.write_text(str(tries + 1), encoding="utf-8")
            wave.append((f, name, tries + 1))
        if retired:
            _push_answer("+".join(retired))
        if not wave:
            continue
        _push_answer("+".join(n for _, n, _ in wave) + ".محاولة")     # سجلُّ المحاولات: دفعةً واحدة
        # ⛔ ودفعُ المحاولة يدمج `origin/main` فقد يجلب نقلَ الأمر إلى `done/` من شوطٍ نفّذه
        #    قبلنا (مقيسٌ 2026-09-25) ⇒ يُعاد الفحصُ، ولا يُكتب جوابٌ ولا يُترك عدّاد.
        live = []
        for f, name, n in wave:
            if not f.exists():
                (OUT_DIR / f"{name}.attempts").unlink(missing_ok=True)
                print(f"⏭ {name}: نُفّذ في شوطٍ آخر (نُقل ملفُّه أثناء الدفع) — يُتخطّى")
            else:
                live.append((f, name, n))
        if not live:
            continue
        with ThreadPoolExecutor(max_workers=len(live)) as ex:
            futs = {}
            for f, name, n in live:
                print(f"\n══ أمر: {name}  (المحاولةُ {n}/{MAX_TRIES})")
                futs[ex.submit(_execute, f, name)] = (f, name)
            pending = set(futs)
            while pending:
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                # نجمع كلَّ ما انتهى الآن ثمّ ندفع مرّةً واحدة.
                names = []
                for fut in sorted(finished, key=lambda x: futs[x][1]):
                    f, name = futs[fut]
                    rc, out = fut.result()
                    print(f"\n── جواب {name}:")
                    print(out[:4000])
                    if rc is not DEFERRED:   # tool المفوَّض: يكتب agent_tool جوابَه وحدَه
                        _atomic_write(OUT_DIR / f"{name}.txt", f"# rc={rc}\n{out}")
                    (OUT_DIR / f"{name}.attempts").unlink(missing_ok=True)   # تمّ ⇒ يُمحى عدّادُه
                    if f.exists():                                           # فلا يُعاد تنفيذُه
                        f.replace(DONE_DIR / f.name)
                    names.append(name)
                # ⛔⛔ يُدفع الجوابُ الآن لا في آخر الشوط (عطبٌ مقيسٌ 2026-09-20): الشوطُ الذي
                #    يبلغ `timeout-minutes` كان يمحو أجوبةَ ما نُفِّذ فعلاً.
                _push_answer("+".join(names))
    print("\n⇒ تمّت الأوامر.")


def _api_put_files(paths, repo=None, branch="main", tries=6, sleep=None) -> bool:
    """يرفع كلَّ ملفٍّ في `paths` إلى `branch` بواجهة المحتويات (PUT /contents) — إيداعٌ ذرّيٌّ في الخادم بلا دمجٍ ولا جلب.

    ⛔⛔ **عطبٌ مقيسٌ 2026-10-23:** `main` يُدفع إليها كلَّ ثوانٍ، وجلبُ المستودعِ السطحيّ ودمجُه في العدّاء يستغرق 6–7 دقائق
       (‏13:39→13:46 · 13:55→14:01 · 15:43→15:50)، فيخسر الدفعُ الثاني السباقَ دائماً و`_push_answer` يكتفي بمحاولةٍ واحدة؛
       ثمّ لا يرى `ادفع الجواب` في آخر الشوط فرقاً مرحلاً (‏الإيداعُ محلّيٌّ أصلاً) فيقول «لا جوابَ يُدفع» والشوطُ ✅.
       ⇒ **ضاع جوابُ 20 أمراً من 488 في يوم** (‏وكلُّها أوامرُ tool): ترقيةُ نورين (15:43) تمّت ولا أثرَ لجوابها، وجوابُ زرع القرشي
       ضاع فانتظرته سلسلتُه ستَّ ساعات. والترقيةُ نفسُها سليمةٌ (‏المانيفست تغيّر) — الضائعُ الجوابُ وحدَه.
    يعيد True إن وصل كلُّ ملف، وFalse إن تعذّر شيءٌ (فيعود المنادي إلى الجلب والدمج). لا يرمي.
    """
    import base64
    import time
    repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
    if not repo or not paths:
        return False
    nap = sleep if sleep is not None else time.sleep
    for rel in paths:
        f = ROOT / rel
        try:
            body = base64.b64encode(f.read_bytes()).decode("ascii")
        except OSError as ex:
            print(f"⚠️ تعذّرت قراءة {rel}: {ex}")
            return False
        done = False
        for k in range(tries):
            try:
                rc, cur = run(["gh", "api", f"repos/{repo}/contents/{rel}?ref={branch}", "--jq", ".sha"])
                sha = cur.split("[stderr]")[0].strip() if rc == 0 else ""
                payload = {"message": f"ops: جوابُ الأمر {f.stem}", "content": body, "branch": branch}
                if sha:
                    payload["sha"] = sha
                rc, res = run(["gh", "api", "-X", "PUT", f"repos/{repo}/contents/{rel}", "--input", "-"],
                              input=json.dumps(payload, ensure_ascii=False))
            except Exception as ex:                                  # noqa: BLE001
                rc, res = 1, str(ex)
            if rc == 0:
                done = True
                break
            print(f"⚠️ محاولة {k + 1}/{tries} لرفع {rel} بالواجهة فشلت: {res.strip()[:200]}")
            nap(min(2 * (k + 1), 10))
        if not done:
            return False
        print(f"✅ رُفع {rel} إلى {branch} بالواجهة")
    return True


def _push_answer(name: str, api_paths=None) -> None:
    """يُودع جوابَ أمرٍ واحدٍ ويدفعه فوراً — بمسارٍ صريحٍ ولا `-A`.

    `api_paths`: ملفّات جوابٍ تُرفع بالواجهة (‏`_api_put_files`) إن خسر الدفعُ السباقَ، قبل الجلب والدمج البطيئين.
    وإن تعذّرت الواجهةُ فالجلب والدمج بحلقةٍ (حتى 3) لا بمحاولةٍ واحدة.
    """
    import subprocess
    paths = ["ops/out", "ops/commands"]
    try:
        subprocess.run(["git", "config", "user.name", "rafiq-agent-cmd"],
                       cwd=ROOT, check=False)
        subprocess.run(["git", "config", "user.email", "actions@github.com"],
                       cwd=ROOT, check=False)
        # ⛔ **عطبٌ التقطه الاختبار:** `git add a b` يسقط كلُّه إن غاب أحدُ
        #    المسارَين (`pathspec … did not match`) **فلا يُدفع شيء**. والمسارُ
        #    `ops/commands` قد يخلو فعلاً بعد نقل آخر أمرٍ إلى `done/`.
        #    ⇒ كلُّ مسارٍ على حدةٍ، وغيابُ أحدِها لا يُبطل الآخر.
        live = [p for p in paths if (ROOT / p).exists()]
        for p in live:
            subprocess.run(["git", "add", "--", p], cwd=ROOT, check=False)
        if not live or subprocess.run(["git", "diff", "--cached", "--quiet"],
                                      cwd=ROOT).returncode == 0:
            return                                     # لا جديدَ يُدفع
        # ⛔ وبالمسارات **الحاضرةِ** وحدَها هنا أيضاً: `commit -- a b` يسقط
        #    كسقوط `add` سواءً بسواء، وهو موضعُ العطب الذي أخفاه الأوّل.
        subprocess.run(["git", "commit", "-m", f"ops: جوابُ الأمر {name}",
                        "--", *live], cwd=ROOT, check=False)
        if subprocess.run(["git", "push", "origin", "HEAD:main"],
                          cwd=ROOT).returncode == 0:
            return
        # خسر السباق: الواجهةُ أوّلاً (ثوانٍ) — الجلبُ والدمجُ في عدّاءٍ سطحيٍّ يستغرقان دقائق فيخسران ثانيةً.
        if api_paths and _api_put_files(api_paths):
            return
        for _try in range(3):
            subprocess.run(["git", "fetch", "origin", "main", "--quiet"],
                           cwd=ROOT, check=False)
            # ⛔ لا `rebase` على هذه الشجرة المشتركة — `CLAUDE.md` نصّاً.
            merged = subprocess.run(["git", "merge", "-X", "ours", "--no-edit",
                                     "origin/main"], cwd=ROOT, check=False)
            # ⛔ **عطبٌ مقيسٌ 2026-09-25** (‏الشوط 36163812825): تعارضٌ لا يحلّه
            #    `-X ours` (‏حذفٌ/تعديل) يترك الدمجَ معلّقاً، فيسقط كلُّ إيداعٍ بعده
            #    بـ«cannot do a partial commit during a merge» ويضيع الجوابُ. ⇒ يُلغى
            #    الدمجُ المعلّق فيبقى الإيداعُ محلّياً، ويُعاد دفعُه بعد الأمر التالي.
            if merged.returncode != 0:
                subprocess.run(["git", "merge", "--abort"], cwd=ROOT, check=False)
                return
            if subprocess.run(["git", "push", "origin", "HEAD:main"],
                              cwd=ROOT).returncode == 0:
                return
    except Exception as ex:                                       # noqa: BLE001
        # ⛔ لا يوقف فشلُ الدفع بقيّةَ الأوامر: الخطوةُ الأخيرة شبكةُ أمان.
        print(f"⚠️ تعذّر دفعُ جواب {name} الآن (يبقى للخطوة الأخيرة): {ex}")


if __name__ == "__main__":
    if "--tool-run" in sys.argv[1:]:
        tool_main()
    else:
        main()
