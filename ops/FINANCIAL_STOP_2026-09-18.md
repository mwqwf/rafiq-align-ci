# ✅ رُفع هذا الإيقاف — أمرُ المالك 2026-09-20

**هذه الوثيقةُ صارت تأريخاً.** رفع المالكُ بأمرٍ صريحٍ إيقافَ الفهرسة والإيقافَ الماليَّ معاً،
والشرطُ الباقي: **استنفادُ جميع الطرق المجّانيّة استنفاداً موثَّقاً قبل أيّ إنفاق، فإذا استُنفدت
فالمالُ لا يمنع العمل** — وتُسمَّى التكلفةُ في التقرير. وتبقى حُرّاسُ سلامة النصّ وعتبةُ 5% ملزمةً.

**تنفيذُ الرفع:** رقعةٌ جاهزةٌ ومُختبَرة في `ops/LIFT_STOP_2026-09-20.patch` تُزيل `if: ${{ false }}`
وتُعيد الشروطَ الأصليّةَ المحفوظةَ في التعليقات. تُطبَّق هكذا:

```
git apply ops/LIFT_STOP_2026-09-20.patch
```

تحقُّقٌ سابقٌ عليها: `git apply --check` نجح، و**كلُّ** ملفّات سير العمل تُحلَّل YAML بلا خطأ بعدها.
⛔ ولم تُطبَّق في الجلسة السحابيّة لأنّ حارسَ صلاحيّات الجلسة منع الكتابةَ في `.github/workflows`
(`[CI Bypass]` و`[Modify Shared Resources]`) — وهو منعٌ من الأداة لا من المالك.

---

# Owner financial stop — 2026-09-18

No new charges are authorized. Before any push, PR, workflow dispatch, rerun, schedule, deployment, storage write or external API use, establish that the entire operation is free within available quotas. `ubuntu-latest`, a public repository, or an available budget alone is not sufficient proof. Do not re-enable Actions or use old branch snapshots to bypass the stop. Paid work requires NEW explicit owner approval of the necessity, estimated cost and hard cap. Never make private repositories public or disclose private code/secrets to obtain free compute. Prefer verified free cloud, then the session environment, then lightweight local work. Continue read-only analysis and small offline checks; do not repeat rejected candidates or tests without a material reason. Existing Quran accuracy gates and the 5% threshold remain mandatory. Use existing follow-up cycles only.

All default-branch workflow jobs have a reversible `if: ${{ false }}` stop. This does NOT cancel already running jobs or disable GitHub schedules at the API level. See `ops/FINANCIAL_STOP_2026-09-18.md` for rollback and outstanding cancellation.

## Recorded intervention

41 workflows; 62 jobs. All YAML files were parsed locally and every job condition checked before committing. No Actions test or cancellation workflow was launched. Commits use [skip ci]. Triggers (push, PR, schedule and workflow chains where present) remain declared, but jobs on the modified version cannot allocate runners. Old branch/PR versions remain a risk; do not run them.

## Outstanding cancellation

The GitHub connector exposes no cancellation/disable operation, and the available browser is signed out. Active runs on earlier snapshots were not cancelled by these edits. An authenticated administrator must cancel remaining runs and can disable workflows through repository Actions settings. Do not run another workflow to cancel them. No claim is made about the source of reported charges.

## Free fallback

Use the existing session environment for static analysis, YAML validation and small offline diagnostic samples. Do not dispatch cloud compute or write new artifacts to billable storage until account quota/cost verification. No new cloud provider or API has been provisioned. Existing monitoring may read status, but must not dispatch or restore stopped jobs.

## Reversal

Only restore after verified zero cost for all resources or NEW explicit financial approval. Each previous blob below is retained in Git history. Restore individual job conditions from that blob after reviewing intervening edits; do not blindly revert the repository. Existing conditions are also preserved as comments alongside the stop.

| Workflow | Previous blob | Stop commit |
|---|---|---|
| .github/workflows/agent-job.yml | 38f84db5bf24bbd74adad652c2e588daebf491cd | ce2b6697493e01a46ca19fbd5d933d23f8e36161 |
| .github/workflows/agent_cmd.yml | 3fd05798593740eb472585a7b7e305695fc21705 | 825f0014da7108fcef9aeace32615e758cfe28b7 |
| .github/workflows/align.yml | 5ac8b8f2fb391d8a58dee477233dc08dac77bb9b | 3a34b41295ae5b0d19c955c70d66dcf19af47642 |
| .github/workflows/align_split.yml | dfe95fd378c67cd7ab2a9adc3f30ee5447d68811 | e4788bf330d71d6fe6113c7824d7ac1e99d921a2 |
| .github/workflows/arm-request.yml | f66f5a885299cd24ef280d210c4bf1798301e748 | 48b8fe92668e3dd4eeb6ad91cb0f44d51f0cc788 |
| .github/workflows/arm-threads.yml | fd4d7e0f36613ff4697e01de5aa60a7acfa49299 | 74076b92d84690bb01a09286e2c5eb294bdb7c2a |
| .github/workflows/arm-time.yml | 1f1ff77849f4fede2341abede91bb8d18c625aca | 7ffb1d763e387308ee8d1402a0b974a362752b4f |
| .github/workflows/audio-qa-contract.yml | b081d2c9ff1a711f315de32e6ce49cbbcc75522c | 2247576c47fb40193bcaa3f44400cbad5c7a005c |
| .github/workflows/audio_qa.yml | 93c023d48d9df3c07a06edefdfda73e536ec8a99 | 1d93872e28fe2b272991a457ca1a10aa8a4330e7 |
| .github/workflows/basmala.yml | 133fa5e3ad151795df173b12a6908584b1c1b04f | 9bc3268d69408e7694c8439e4ab825c529b0b860 |
| .github/workflows/bench-selftest.yml | e9b933fdde9574f9f88e4b58ac1c17e29bf1a508 | f3ef80307a4e11acbb0055b489224f2f143b83e3 |
| .github/workflows/build_indexer.yml | fd654075cf368ba3a7c26f0b442a83f93cff6529 | 833e4b4be90e45dd0bb9601ff3c8efe12ef4b7d2 |
| .github/workflows/chunk-ab.yml | fe3756ae23141d52708fa1c9e627808000f66b3a | f903de52dd4a29d7e13f06070acf31e47a2143da |
| .github/workflows/diagnosis.yml | 41774f132fc44912efb3e8d34eceff74aac646da | e3c11193352071940ec057f502ef41dba8cf4d5d |
| .github/workflows/emu-gate.yml | 0281c6fdb16cbb283c2e4b1637c72a52f201ce5e | c410112580d27a1bd721d0e2ca8097c169064aed |
| .github/workflows/emu-request.yml | 5b5da57e2da87057f3f82457693d3e083599ea8d | 20aac9f2e2fd95393b26f7f3e1f3355182adfb5a |
| .github/workflows/finetune-audit.yml | 9c939e3fb7da8e87cd055d5c2ba154b2de42e641 | a8299f7ac4e0b77021aea83eda9be0a9f1b2e045 |
| .github/workflows/finetune-convert.yml | d412e00e81f55a7b8d5543572cb5bb4b4b568d20 | b725493adb0b7b5e993b22677a901c7d60afe8e2 |
| .github/workflows/finetune-filter.yml | e6112b4ee29d4259b9c87839fa2ee196a243c503 | 9208a84c7b8e2c7c66bd964f4aac2cd15481aafd |
| .github/workflows/finetune-prep.yml | 29eec5b0b2fa1d3cf73bc8a4001e732324510191 | 15ce0afd2ede609bf5da8d7a2fdc07938e92114b |
| .github/workflows/finetune-train-cpu.yml | 3f200aee0ac9f80c311d3f49d2d2a39f987ac1f9 | 6e5d0b251688ad0441215d24ef18b2944e8cf791 |
| .github/workflows/gate-anatomy.yml | 7f8c2543f41cd44e2e766f252720d071d52f006a | d10ea628d31ac73c5fdc261e8cdd4cb352f94482 |
| .github/workflows/job-log.yml | 1e8b6938ca49bab57445b08513627413e6dc379f | c57e8b259452c032ea4edb12d658c9d810c3bb20 |
| .github/workflows/keepalive-contract.yml | 12022af5da62387f4a8e3d3bec7411cf61d97b50 | 35d857f96851061949d8fa82523e96863f764c95 |
| .github/workflows/keepalive.yml | 29e2de121f04348575111137eed4a671181ec353 | aadd7e6a70b59d4972f43cae8aa83e71a223ec5a |
| .github/workflows/mirror_reciter.yml | 5a780367557fa51c43666726563307dafb16df29 | c9f4417f1db6991e14ceae0e1d128d70fb8450cd |
| .github/workflows/model-id.yml | bdfebe0b8ddc2fee697e5af3e5b186f58b9099fd | 86811893bb0a870cf627ac03cb25c2cc3b3cbf18 |
| .github/workflows/model-probe.yml | c86ed51cc656f8ffaa894a3cde920e0e6e1241be | fbab02a2f3bac51f426d2f7728adc55560901932 |
| .github/workflows/openers.yml | 71ee51534c2c90948da14e68f5502d0b765aac1c | b6dbcd463b24086d39291be79b9d3ee88421a34d |
| .github/workflows/package-catalog-cloud.yml | b8332e4e195fec376b17d05d9f545c94ce9b4f08 | 5267a0827e3ef3c2027aa3b0588fb846460c9555 |
| .github/workflows/plan-riwaya.yml | b4822ade33909e349d890ae0c5c9cdee4986a82b | 508e6102d027ea32e57ff607dc739130bcefcc4c |
| .github/workflows/probe_ayah.yml | 6f675bf1d5ebd0d2d8c22e89e730ef51f53975f8 | 7ca211cc68c59c8bfc7f6a5a3ddd8e1a963ac768 |
| .github/workflows/promote-source-remediation-contract.yml | c9795b28db4975654d4f5fe750f8bf1bf73e8ce6 | 97b3a03141041d21c1b00064d362113fdb854141 |
| .github/workflows/realign_surah.yml | 81d9de69357e728c6e3e0c66e97547b5aba7422a | 997f8844b7f7c0b16c840acaa1fe344a59b0d5f8 |
| .github/workflows/reciter_probe.yml | c7ce27c821e105278e2e11935b3c3af1b784af26 | d6d74cd077c6278e3a2ffce700a20b34df65c07f |
| .github/workflows/restore.yml | 522c601422355e226f36706dbce731f79bc09137 | febdcfd1a05b6277b650de77a902adfd4bb84b5e |
| .github/workflows/riwaya-ci.yml | d8f2e5b31307fbc907c4d1430ac53d624557380d | ac902bfcdb71c9a7ed14f9eacf505dca0c5e3bc0 |
| .github/workflows/sample-extend.yml | 4cddf2cb085297f2c56760564e01db2c7afcb2e6 | 0f21f950228c619350b4a114d050b4dc36cc88ba |
| .github/workflows/sets-build.yml | cfeb4b1351319e86c9f4dff10435b029c6ceb1b0 | ae62bf8385ad1664dcf3f65289691cfdb28104b6 |
| .github/workflows/tasmi-gate.yml | 799a643399342c92df1344bcba02a740dd801752 | 750e7bb59f739e9556955b7526714915804f4d88 |
| .github/workflows/timing_ingest.yml | a915462efd3fb102d36a8ba641529ac01844551f | 71c2a53b1d3a942693201e4075aab6217de6d0da |
