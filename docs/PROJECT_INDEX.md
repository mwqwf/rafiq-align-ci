# فهرس المشروع الآليّ — `rafiq-align-ci`

> ⛔ مولَّد آلياً بـ`tools/agents/gen_project_index.py` (سير عمل `project-index` عند الدفع إلى الفرع الرئيسيّ). لا تعدّله يدوياً.
> الحالة والخطة والعمل المفتوح في `docs/PROJECT_STATE.md` (يحدّثها الوكلاء في كل تغيير).

## البنية (عدد الملفات المتتبَّعة)
| المجلد | الملفات |
|---|---|
| `"ops/` | 2 |
| `.agents/` | 17 |
| `.github/` | 106 |
| `core/` | 17 |
| `docs/` | 209 |
| `jobs/` | 7 |
| `ops/` | 89508 |
| `results/` | 146 |
| `tools/` | 5442 |

## سير العمل (103)
| الملف | الاسم | المحفّزات | الجدول (cron UTC) | المشغّل |
|---|---|---|---|---|
| `agent-job.yml` | agent-job | push, workflow_dispatch, issues | — | ubuntu |
| `agent_cmd.yml` | rafiq-agent-cmd | push, workflow_dispatch | — | ubuntu |
| `agent_tool.yml` | rafiq-agent-tool | workflow_dispatch | — | ubuntu |
| `align.yml` | rafiq-align | workflow_dispatch | — | ubuntu |
| `align_split.yml` | rafiq-align-split | workflow_dispatch | — | ubuntu |
| `app-e2e.yml` | app-e2e | push | — | ubuntu |
| `arm-request.yml` | arm-request | push | — | ubuntu |
| `arm-threads.yml` | arm-threads | push, workflow_dispatch | — | ubuntu |
| `arm-time.yml` | arm-time | workflow_dispatch | — | ubuntu |
| `audio-qa-contract.yml` | audio-qa-contract | push, workflow_dispatch | — | ubuntu |
| `audio_qa.yml` | rafiq-audio-qa | workflow_dispatch | — | ubuntu |
| `automerge.yml` | automerge | schedule, workflow_dispatch | 3-59/10 * * * * | ubuntu |
| `balilah_pause_probe.yml` | rafiq-balilah-native-pause | workflow_dispatch | — | ubuntu |
| `basmala.yml` | rafiq-basmala | workflow_dispatch | — | ubuntu |
| `bench-selftest.yml` | bench-selftest | push, schedule, workflow_dispatch | 43 * * * * | ubuntu |
| `build_indexer.yml` | build-indexer | workflow_dispatch | — | ubuntu |
| `chunk-ab.yml` | chunk-ab | workflow_dispatch | — | ubuntu |
| `cloud-probe.yml` | cloud-probe | push | — | ubuntu |
| `ctc_align.yml` | rafiq-ctc-align | workflow_dispatch | — | ubuntu |
| `ctc_driver.yml` | rafiq-ctc-driver | schedule, workflow_dispatch | */20 * * * * | ubuntu |
| `ctc_heard_probe.yml` | rafiq-ctc-heard-probe | workflow_dispatch | — | ubuntu |
| `ctc_splice.yml` | rafiq-ctc-splice | workflow_dispatch | — | ubuntu |
| `ctc_splice_merge.yml` | rafiq-ctc-splice-merge | workflow_dispatch | — | ubuntu |
| `diagnosis.yml` | rafiq-diagnosis | push, pull_request, workflow_dispatch | — | ubuntu |
| `duration_context_followup.yml` | rafiq-duration-context-followup | workflow_dispatch | — | ubuntu |
| `duration_defect_diagnostic.yml` | rafiq-duration-defect-diagnostic | workflow_dispatch | — | ubuntu |
| `emu-gate.yml` | emu-gate | workflow_dispatch, issues | — | ubuntu |
| `emu-request.yml` | emu-request | push, issues | — | ubuntu |
| `entry_window_census.yml` | rafiq-entry-window-census | workflow_dispatch | — | ubuntu |
| `entry_witness_probe.yml` | rafiq-entry-witness-probe | workflow_dispatch | — | ubuntu |
| `fakhfakh69_tail_dual_witness.yml` | rafiq-fakhfakh69-tail-dual-witness | workflow_dispatch | — | ubuntu |
| `final_verse_free_batch.yml` | rafiq-final-verse-free-batch | workflow_dispatch | — | ubuntu |
| `finetune-audit.yml` | finetune-audit | workflow_dispatch | — | ubuntu |
| `finetune-convert.yml` | finetune-convert | workflow_dispatch | — | ubuntu |
| `finetune-filter.yml` | finetune-filter | workflow_dispatch | — | ubuntu |
| `finetune-prep.yml` | finetune-prep | workflow_dispatch | — | ubuntu |
| `finetune-train-cpu.yml` | finetune-train-cpu | workflow_dispatch | — | ubuntu |
| `free-noah-source-gap-quality.yml` | فحص مجاني لحذف القمر كاملًا بسبب نقص المصدر | workflow_dispatch | — | ubuntu |
| `free-post-stage-quality.yml` | فحص مجاني بعد رفع المرشح دون ترقية | workflow_dispatch | — | ubuntu |
| `free_candidate_probe.yml` | rafiq-free-candidate-probe | workflow_dispatch | — | ubuntu |
| `gate-anatomy.yml` | gate-anatomy | push, workflow_dispatch | — | ubuntu |
| `gcp_train.yml` | gcp-train | schedule, workflow_dispatch | */30 * * * * | ubuntu |
| `heard_anchor_provenance_probe.yml` | rafiq-heard-anchor-provenance-probe | workflow_dispatch | — | ubuntu |
| `heard_batch.yml` | rafiq-heard-batch | workflow_dispatch | — | ubuntu |
| `heard_dual_shadow.yml` | rafiq-heard-dual-shadow | push, workflow_dispatch | — | ubuntu |
| `heard_gate.yml` | rafiq-heard-gate | workflow_dispatch | — | ubuntu |
| `heard_pub.yml` | rafiq-heard-pub | workflow_dispatch | — | ubuntu |
| `independent_window_pilot.yml` | rafiq-independent-window-pilot | workflow_dispatch | — | ubuntu |
| `job-log.yml` | job-log | push, workflow_dispatch | — | ubuntu |
| `keepalive-contract.yml` | keepalive-contract | push, workflow_dispatch | — | ubuntu |
| `keepalive.yml` | rafiq-keepalive | schedule, workflow_dispatch | 17 * * * * | ubuntu |
| `legacy-key-guard.yml` | legacy-key-guard | push, pull_request, workflow_dispatch | — | ubuntu |
| `mirror_reciter.yml` | rafiq-mirror-reciter | workflow_dispatch | — | ubuntu |
| `mirror_sha_guard.yml` | rafiq-mirror-sha-guard | push, schedule, workflow_dispatch | 53 */3 * * * | ubuntu |
| `model-id.yml` | model-id | push, workflow_dispatch | — | ubuntu |
| `model-probe.yml` | model-probe | workflow_dispatch | — | ubuntu |
| `mushaf_assets.yml` | mushaf_assets | workflow_dispatch | — | ubuntu |
| `openers.yml` | rafiq-openers | workflow_dispatch | — | ubuntu |
| `package-catalog-cloud.yml` | package-catalog-cloud | push, workflow_dispatch | — | ubuntu |
| `peshawa_tail_dual_probe.yml` | rafiq-peshawa-tail-dual-probe | workflow_dispatch | — | ubuntu |
| `peshawa_tail_free_decode.yml` | rafiq-peshawa-tail-free-decode | workflow_dispatch | — | ubuntu |
| `plan-riwaya.yml` | plan-riwaya | push, workflow_dispatch | — | ubuntu |
| `probe_ayah.yml` | rafiq-probe-ayah | workflow_dispatch | — | ubuntu |
| `project-index.yml` | project-index | push, workflow_dispatch | — | ubuntu |
| `promote-source-remediation-contract.yml` | promote-source-remediation-contract | push, pull_request, workflow_dispatch | — | ubuntu |
| `quran_source_recovery.yml` | rafiq-known-source-quran-recovery-probe | workflow_dispatch | — | ubuntu |
| `realign_surah.yml` | rafiq-realign-surah | workflow_dispatch | — | ubuntu |
| `reciter_probe.yml` | rafiq-reciter-probe | workflow_dispatch | — | ubuntu |
| `reconcile_public_catalog.yml` | rafiq-public-catalog-reconciliation | workflow_dispatch | — | ubuntu |
| `registered-source-quality.yml` | فحص تصحيح المصادر المسجلة بلا كتابة إلى الدلو | push, workflow_dispatch | — | ubuntu |
| `registered_splice.yml` | rafiq-registered-splice | workflow_dispatch | — | ubuntu |
| `repair_boundary_diagnostics.yml` | rafiq-repair-boundary-diagnostics | workflow_dispatch | — | ubuntu |
| `restore.yml` | rafiq-restore | push, schedule, workflow_dispatch | 41 * * * * | ubuntu |
| `riwaya-ci.yml` | riwaya-ci | push, workflow_dispatch | — | ubuntu |
| `saad_free_decode.yml` | rafiq-saad-free-decode | workflow_dispatch | — | ubuntu |
| `sample-extend.yml` | sample-extend | push, workflow_dispatch | — | ubuntu |
| `sets-build.yml` | sets-build | push, workflow_dispatch | — | ubuntu |
| `short_opener_context_diagnostics.yml` | rafiq-short-opener-contexts | workflow_dispatch | — | ubuntu |
| `silence_probe.yml` | rafiq-silence-probe | workflow_dispatch | — | ubuntu |
| `source_context_diagnostics.yml` | rafiq-source-context-diagnostics | workflow_dispatch | — | ubuntu |
| `source_drift_sweep.yml` | rafiq-source-drift-sweep | schedule, workflow_dispatch | 17 5 * * 1 | ubuntu |
| `source_metadata_probe.yml` | قياس بيانات المصدر الصوتي | workflow_dispatch | — | ubuntu |
| `source_quran_probe.yml` | rafiq-source-quran-probe | workflow_dispatch | — | ubuntu |
| `splice_census.yml` | rafiq-splice-census | workflow_dispatch | — | ubuntu |
| `spoken_census.yml` | rafiq-independent-spoken-census | workflow_dispatch | — | ubuntu |
| `tafsir_ai_split.yml` | tafsir_ai_split | push, workflow_dispatch | — | ubuntu |
| `tail_clipping_followup.yml` | rafiq-tail-clipping-followup | workflow_dispatch | — | ubuntu |
| `tasmi-conf.yml` | tasmi-conf | push, workflow_dispatch | — | ubuntu |
| `tasmi-gate.yml` | tasmi-gate | workflow_dispatch | — | ubuntu |
| `tasmi-lexbias.yml` | tasmi-lexbias | push, workflow_dispatch | — | ubuntu |
| `tasmi-llr-judge.yml` | tasmi-llr-judge | workflow_dispatch | — | ubuntu |
| `tasmi-shrink-anatomy.yml` | tasmi-shrink-anatomy | push, workflow_dispatch | — | ubuntu |
| `tasmi-shrink-publish.yml` | tasmi-shrink-publish | push, workflow_dispatch | — | ubuntu |
| `tasmi-shrink.yml` | tasmi-shrink | push, workflow_dispatch | — | ubuntu |
| `tasmi-student-armtime.yml` | tasmi-student-armtime | workflow_dispatch | — | ubuntu |
| `tasmi-student-train.yml` | tasmi-student-train | workflow_dispatch | — | ubuntu |
| `timing_ingest.yml` | rafiq-timing-ingest | workflow_dispatch | — | ubuntu |
| `timing_witness.yml` | rafiq-timing-witness | workflow_dispatch | — | ubuntu |
| `verified_kurdi_source.yml` | verified-original-kurdi-source | workflow_dispatch | — | ubuntu |
| `whisper_recovery_diagnostic.yml` | rafiq-whisper-recovery-diagnostic | workflow_dispatch | — | ubuntu |
| `whisper_splice.yml` | rafiq-whisper-splice | workflow_dispatch | — | ubuntu |
| `whisper_witness.yml` | rafiq-whisper-witness | workflow_dispatch | — | ubuntu |
| `window_census.yml` | rafiq-independent-window-census | workflow_dispatch | — | ubuntu |

## المهارات (4) — `.agents/skills/` (و`.claude/skills/` روابط لها)
`arabic-text-integrity` (مركزية) · `engineering-discipline` (مركزية) · `mushafak` (مركزية) · `mwqwf-workflow` (مركزية)

## وثائق `docs/`
[`DATA_LICENSE_REGISTRY.md`](DATA_LICENSE_REGISTRY.md) · [`PROJECT_STATE.md`](PROJECT_STATE.md)
