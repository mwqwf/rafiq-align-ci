"""Read-only targeted source context and unknown long-recording content diagnosis."""
import argparse
import base64
import gc
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import final_verse_free_batch as B
import independent_window_pilot as P
S=B.S
PLAN='ops/source-repair/codex-source-context-plan-20261006.json'
PLAN_SHA='7d9393ff6c059e35a18eb9f24922aa8778278b93d24e0b7ee35f1863a9bdb24a'
IDS=('saad28_context', 'saad45_tail', 'shamrani79_tail', 'tblawi_head', 'tblawi_tail', 'm_ab26_29', 'm_ab34_37', 'm_ab91_95', 'koshi20_22', 'koshi94_96', 'saad28_tail', 'saad22_41_45', 'saad22_68_71', 'saad22_tail', 'shamrani79_middle', 'shamrani79_midad_middle', 'mab_rs1_16_9', 'mab_rs1_11_22', 'mab_rs1_18_90', 'mab_rs1_23_52', 'mab_rs1_23_79', 'mab_rs1_69_47', 'mab_rs1_90_11', 'mab_rs1_90_19', 'mab_rs1_90_5', 'mab_rs1_78_33', 'mrifai84_tail', 'yousef107_tail', 'saad_reject_22_27', 'saad_reject_22_52', 'saad_reject_22_62', 'saad_reject_28_21', 'saad_reject_28_67', 'hazmi67_23_26', 'hazmi67_tail', 'hazmi77_tail', 'benkirane77_tail', 'benkirane51_middle', 'benkirane51_tail', 'rabbani_warsh_77_expanded', 'rabbani_warsh_96_expanded', 'hatem_54_expanded', 'hatem_82_expanded', 'm_abdulkareem_warsh_69_expanded', 'mab78_32_36', 'mab90_4_8', 'mab90_10_14', 'mukhtar37_19', 'mukhtar37_25', 'mukhtar37_84', 'mukhtar37_153', 'mukhtar37_163', 'mukhtar37_166', 'benkirane77_26_28', 'rabbani56_tail', 'rabbani96_5_10', 'mukhtar37_20_22', 'tblawi7_new_head', 'tblawi7_new_middle', 'tblawi7_new_tail', 'obk1_new_full', 'mab_v3_11_56', 'mab_v3_11_91', 'mab_v3_11_122', 'mab_v3_16_16', 'mab_v3_23_105', 'mab_v3_23_113_114', 'mab_v3_23_117', 'balilah69_tail_transition', 'mab_v4_11_93', 'mab_v4_23_107', 'iraoui41_free_1', 'iraoui41_free_2', 'iraoui41_free_3', 'iraoui41_free_4', 'iraoui41_free_5', 'short_final_shuba_deban_shuba_89', 'short_final_hafs_a_albadr_56', 'short_final_hafs_deban_80', 'short_final_hafs_hamza_52', 'short_final_warsh_laghdaf_shinqiti_69', 'short_final_hafs_yahya_68', 'short_final_qalun_fakhfakh_qalun_38', 'short_final_hafs_lahoni_89', 'short_final_hafs_m_qari_87', 'short_final_warsh_harraz_warsh_44', 'short_final_warsh_harraz_warsh_53', 'short_final_hafs_wdee3_89', 'short_final_douri_deban_douri_89', 'short_final_qalun_noah_qalun_93', 'short_final_hafs_alijon_89', 'short_final_hafs_muftah_sultany_77', 'short_final_hafs_sayed_53', 'short_final_hafs_m_qari_105', 'short_final_hafs_mohsin_harthi_91', 'short_final_hafs_a_alqrafi_89', 'short_final_hafs_darweez_89', 'short_final_hafs_h_abudalal_89', 'short_final_hafs_muftah_sultany_53', 'short_final_qalun_suhaim_qalun_91', 'short_final_hafs_m_alfaqih_89', 'short_final_warsh_kholti_warsh_91', 'short_final_hafs_deban_89', 'short_final_hafs_sayed_91', 'short_final_qalun_qeniwa_qalun_94', 'short_final_hafs_qurashi_89', 'short_final_hafs_nabil_91', 'short_final_badr56_79_87', 'short_final_badr56_87_96', 'short_final_deban80_33_42', 'short_final_laghdaf69_43_52', 'short_final_yahya68_45_52', 'iraoui41_new_15_16', 'iraoui41_new_44', 'iraoui41_new_47_48', 'iraoui41_new_49_50', 'iraoui41_new_51_52', 'iraoui41_new_53_54', 'iraoui41_new_50_full', 'iraoui41_new_head_1_4', 'alijon89_eof_24_30', 'harraz44_tail_40_50', 'harraz44_tail_49_57', 'harraz44_tail_52_59', 'harraz53_tail_51_62', 'sayed53_tail_51_62', 'muftah53_tail_51_62', 'alqrafi89_tail_24_30', 'darweez89_tail_24_30', 'suhaim91_final15', 'balilah69_disputed25_27', 'nabil91_final15', 'sayed53_tail_39_52', 'muftah53_tail_39_52', 'muftah53_final61_62', 'alqrafi89_boundary28')

PINNED_PARENT_IDS={'rabbani_warsh_77_expanded': 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa', 'rabbani_warsh_96_expanded': 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa', 'hatem_54_expanded': '5d7e73699ae633807bd57ecb60ea235f503318fdacf8c13bd3b81132eb10f85e', 'hatem_82_expanded': '5d7e73699ae633807bd57ecb60ea235f503318fdacf8c13bd3b81132eb10f85e', 'm_abdulkareem_warsh_69_expanded': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab78_32_36': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab90_4_8': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab90_10_14': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mukhtar37_19': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_25': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_84': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_153': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_163': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_166': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'rabbani56_tail': 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa', 'rabbani96_5_10': 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa', 'mukhtar37_20_22': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mab_v3_11_56': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_11_91': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_11_122': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_16_16': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_23_105': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_23_113_114': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_23_117': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'balilah69_tail_transition': 'f1b40abe72f4f85bd41cc87166f2cf8785960c1e267f09816b99532851812207', 'mab_v4_11_93': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v4_23_107': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'short_final_shuba_deban_shuba_89': 'b839ddd521e41de6d909f4143c807d9e596d2d2df2236a7518fad40fe39f5e5a', 'short_final_hafs_a_albadr_56': '121d167d0f2e0d8bb222fac7c5dfb5d42b2fe8cdf14c2c2fce4244c9cd7a4717', 'short_final_hafs_deban_80': 'f374f5b6b3f0ca61d29b9468dc057dac5d6276c64159d88db8f0ff190e55c3f7', 'short_final_hafs_hamza_52': 'f4493b228dd45f550b177474f68541e5d644144b43c19c57226d8ecb466c649f', 'short_final_warsh_laghdaf_shinqiti_69': '3840d4aebfa883cd246b2cb7a66d4da6b5cf50c6cca906372ee32afbfdeed218', 'short_final_hafs_yahya_68': 'aa9ad2ef19ce132980788c38da835ed56c5954553a60774806b1895c1685c1ec', 'short_final_qalun_fakhfakh_qalun_38': '5bad920fd4994019caacc00b9edd6662941abae720ba0b3a2b41281016c23eef', 'short_final_hafs_lahoni_89': '6a7bfeb439ce991a2feefd25b30e829f106199ffde39680a0d82a7181358af2e', 'short_final_hafs_m_qari_87': '2a27b0f8a6cf6560343605eb38de13d1f41ea71ee08eba59ce45fdbae9e1f8f6', 'short_final_warsh_harraz_warsh_44': 'f233a9f03cc81a3bc450e048923a81b9ddd05481d5dcb06d5e1c669f47ed13c1', 'short_final_warsh_harraz_warsh_53': 'f233a9f03cc81a3bc450e048923a81b9ddd05481d5dcb06d5e1c669f47ed13c1', 'short_final_hafs_wdee3_89': '79baebc0951b6a2f9683c0a5a2e5310133dd68b3aa1f0b96e070b890d9012f7f', 'short_final_douri_deban_douri_89': 'e622142954c6f97b0290053ebc7d1c282a436ec28fb679ae9e48a1fc1f469580', 'short_final_qalun_noah_qalun_93': '21ebad8421e4fdb407a920dd7564a73af0d1174d82012652c0e0f6bf77056c08', 'short_final_hafs_alijon_89': '5e9fd934732d6ad50325098a0cc20330ef06a13f5732e5d528eedd6ba5c3e154', 'short_final_hafs_muftah_sultany_77': 'ebc247fd427ba1f9cbb62b09602076c00ebeb01c5a6180e2d412344ca4bff11d', 'short_final_hafs_sayed_53': '79118033c593c0bf7110be8fbc48e98bc32785aa7eb39858be8f768c371a5ba0', 'short_final_hafs_m_qari_105': '2a27b0f8a6cf6560343605eb38de13d1f41ea71ee08eba59ce45fdbae9e1f8f6', 'short_final_hafs_mohsin_harthi_91': 'ac38edba785e2dbb519a9423f6153f2395cd70d381fdfbce8ef3bc26f1f3c0f5', 'short_final_hafs_a_alqrafi_89': '3e2c3d79aeeb28cf188f7a861c34cd074d6ae400df54580a13b215aea65d22cf', 'short_final_hafs_darweez_89': '47ef82a5541a9e71e6e25fd83c8608020512f5c9f8ce7583ce9801bbc234140e', 'short_final_hafs_h_abudalal_89': '13f195b2460b5333015c6ab9d54a4516ca2ef8ffc85fab4395dbea2853d51ed8', 'short_final_hafs_muftah_sultany_53': 'ebc247fd427ba1f9cbb62b09602076c00ebeb01c5a6180e2d412344ca4bff11d', 'short_final_qalun_suhaim_qalun_91': '9323930457a179624befb399b7e46a4687ce2c8bd66f51ed3f8bfff12a155234', 'short_final_hafs_m_alfaqih_89': 'a46c655a1ce4c4fb9176234b11b758ee59c455b262fa84635efa53099e186fe7', 'short_final_warsh_kholti_warsh_91': '563cfc75bbc42ebf67fc9d089d602822eb6d2b226e44d1d714c18cfb445ac7ff', 'short_final_hafs_deban_89': 'f374f5b6b3f0ca61d29b9468dc057dac5d6276c64159d88db8f0ff190e55c3f7', 'short_final_hafs_sayed_91': '79118033c593c0bf7110be8fbc48e98bc32785aa7eb39858be8f768c371a5ba0', 'short_final_qalun_qeniwa_qalun_94': 'bbd2a48275460c0966d586b083dad2dc7ea00cc6417688af8168cd87d701445c', 'short_final_hafs_qurashi_89': '6a42a675870ed312366d67b2168ae3c56e911026ce94c846805a85ed201b13de', 'short_final_hafs_nabil_91': 'eda04a24fee769a98246eccc484ba7eb7c1450fa3446753ea19a0d4da8fe8bb3', 'short_final_badr56_79_87': '121d167d0f2e0d8bb222fac7c5dfb5d42b2fe8cdf14c2c2fce4244c9cd7a4717', 'short_final_badr56_87_96': '121d167d0f2e0d8bb222fac7c5dfb5d42b2fe8cdf14c2c2fce4244c9cd7a4717', 'short_final_deban80_33_42': 'f374f5b6b3f0ca61d29b9468dc057dac5d6276c64159d88db8f0ff190e55c3f7', 'short_final_laghdaf69_43_52': '3840d4aebfa883cd246b2cb7a66d4da6b5cf50c6cca906372ee32afbfdeed218', 'short_final_yahya68_45_52': 'aa9ad2ef19ce132980788c38da835ed56c5954553a60774806b1895c1685c1ec', 'alijon89_eof_24_30': '5e9fd934732d6ad50325098a0cc20330ef06a13f5732e5d528eedd6ba5c3e154', 'harraz44_tail_40_50': 'f233a9f03cc81a3bc450e048923a81b9ddd05481d5dcb06d5e1c669f47ed13c1', 'harraz44_tail_49_57': 'f233a9f03cc81a3bc450e048923a81b9ddd05481d5dcb06d5e1c669f47ed13c1', 'harraz44_tail_52_59': 'f233a9f03cc81a3bc450e048923a81b9ddd05481d5dcb06d5e1c669f47ed13c1', 'harraz53_tail_51_62': 'f233a9f03cc81a3bc450e048923a81b9ddd05481d5dcb06d5e1c669f47ed13c1', 'sayed53_tail_51_62': '79118033c593c0bf7110be8fbc48e98bc32785aa7eb39858be8f768c371a5ba0', 'muftah53_tail_51_62': 'ebc247fd427ba1f9cbb62b09602076c00ebeb01c5a6180e2d412344ca4bff11d', 'alqrafi89_tail_24_30': '3e2c3d79aeeb28cf188f7a861c34cd074d6ae400df54580a13b215aea65d22cf', 'darweez89_tail_24_30': '47ef82a5541a9e71e6e25fd83c8608020512f5c9f8ce7583ce9801bbc234140e', 'suhaim91_final15': '9323930457a179624befb399b7e46a4687ce2c8bd66f51ed3f8bfff12a155234', 'balilah69_disputed25_27': 'f1b40abe72f4f85bd41cc87166f2cf8785960c1e267f09816b99532851812207', 'nabil91_final15': 'eda04a24fee769a98246eccc484ba7eb7c1450fa3446753ea19a0d4da8fe8bb3', 'sayed53_tail_39_52': '79118033c593c0bf7110be8fbc48e98bc32785aa7eb39858be8f768c371a5ba0', 'muftah53_tail_39_52': 'ebc247fd427ba1f9cbb62b09602076c00ebeb01c5a6180e2d412344ca4bff11d', 'muftah53_final61_62': 'ebc247fd427ba1f9cbb62b09602076c00ebeb01c5a6180e2d412344ca4bff11d', 'alqrafi89_boundary28': '3e2c3d79aeeb28cf188f7a861c34cd074d6ae400df54580a13b215aea65d22cf'}

def load_source(ident):
    B.require(ident in IDS, 'unplanned diagnostic')
    raw=(B.ROOT/PLAN).read_bytes();B.require(hashlib.sha256(raw).hexdigest()==PLAN_SHA,'plan changed')
    rows=json.loads(raw)['sources'];B.require(len(rows)==136 and {r['id'] for r in rows}==set(IDS),'population changed')
    source=next(r for r in rows if r['id']==ident)
    path=(B.ROOT/source['evidencePath']).resolve()
    B.require(path.parent==B.ROOT/'ops/out' and path.suffix=='.json','evidence path')
    b=path.read_bytes();B.require(hashlib.sha256(b).hexdigest()==source['evidenceSha256'],'evidence changed')
    evidence=json.loads(b)
    if source['evidenceKind']=='alignment':
        B.require(evidence['measurementComplete'] and not evidence['errors'],'incomplete source evidence')
        measured=evidence['source']
        B.require(all(source[k]==measured[k] for k in ('url','sha256','surah','riwaya')),'source mismatch')
        B.require(source['contextAyahs'] and all(type(a)is int and 1<=a<=len(evidence['alignment']['entries']) for a in source['contextAyahs']),'invalid context')
        B.require(source['maxSourceSeconds']==7200,'ordinary source limit changed')
    elif source['evidenceKind']=='tblawi-publisher-metadata':
        B.require(ident in ('tblawi7_new_head','tblawi7_new_middle','tblawi7_new_tail'),'unexpected new publisher diagnostic')
        measured=evidence['sources'][0]
        B.require(evidence['complete'] and measured['id']=='tblawi7_nquran' and measured['ok'] and measured['pcm']['decodedWithoutErrors'] and measured['stereo']['decodedWithoutErrors'],'unhealthy publisher source')
        B.require(source['url']==measured['file']['finalUrl'] and source['sha256']==measured['file']['sha256']=='76b0d10dbb33d90cdbb98e71786653a497dbe73f7af704bf2297848ce1fbc547' and source['surah']==measured['surah']==7 and source['riwaya']==measured['riwaya']=='hafs','publisher source mismatch')
        B.require(measured['identitySourceUrl']=='https://www.nquran.com/ar/view/10716' and source['maxSourceSeconds']==7200,'publisher identity/limit changed')
    elif source['evidenceKind']=='obk-publisher-metadata':
        B.require(ident=='obk1_new_full','unexpected Shatri diagnostic')
        measured=evidence['sources'][0]
        B.require(evidence['complete'] and measured['id']=='obk1_nquran' and measured['ok'] and measured['pcm']['decodedWithoutErrors'] and measured['stereo']['decodedWithoutErrors'],'unhealthy Shatri source')
        B.require(source['url']==measured['file']['finalUrl']=='https://www.nquran.com/audiof/quran/Sh_%20shatri/001.mp3' and source['sha256']==measured['file']['sha256']=='a9a743e67cbae4e241744847e18fbac55c77090e5cbc8a4144dba78a412a5924','Shatri source mismatch')
        B.require(source['surah']==measured['surah']==1 and source['riwaya']==measured['riwaya']=='hafs' and measured['identitySourceUrl']=='https://www.nquran.com/ar/view/3870','Shatri publisher identity mismatch')
        B.require(source['contextAyahs']==list(range(1,8)) and source['requestedWindowSeconds']==[0,63] and source['maxSourceSeconds']==7200,'Shatri complete context changed')
    elif source['evidenceKind']=='iraoui-publisher-metadata':
        windows={'iraoui41_free_1':[0,70],'iraoui41_free_2':[60,130],
                 'iraoui41_free_3':[120,190],'iraoui41_free_4':[180,250],
                 'iraoui41_free_5':[247,317]}
        measured=next(r for r in evidence['sources'] if r['id']=='iraoui_warsh-s41')
        B.require(ident in windows and source['requestedWindowSeconds']==windows[ident]
                  and not source['contextAyahs'] and source['maxSourceSeconds']==7200,'changed prefix diagnosis scope')
        B.require(measured['ok'] and measured['pcm']['decodedWithoutErrors']
                  and measured['pcm']['samples']==5069400,'publisher decoding evidence changed')
        B.require(source['sha256']==measured['file']['sha256']=='292231f872106bbf4ea3d5429be73c1ad0abf4be7c9073afe4ac662d0555393e'
                  and source['url']==measured['requestedUrl']=='https://cdns1.zekr.online/quran/6100/41/80.mp3'
                  and source['surah']==measured['surah']==41 and source['riwaya']==measured['riwaya']=='warsh','publisher source identity mismatch')
    elif source['evidenceKind']=='pinned-parent':
        B.require(ident in PINNED_PARENT_IDS,'unexpected parent diagnostic')
        expected=PINNED_PARENT_IDS[ident]
        B.require(evidence['parentSha256']==expected,'wrong diagnostic parent')
        pb=(B.ROOT/evidence['parentPath']).read_bytes()
        B.require(hashlib.sha256(pb).hexdigest()==expected,'parent bytes changed')
        parent=json.loads(gzip.decompress(pb));surah=source['surah']
        B.require(parent['riwaya']==source['riwaya']==evidence['riwaya'] and parent['reciterId']==evidence['reciterId'],'parent identity changed')
        rows=[e for e in parent['entries'] if e['ayahId'] in {f'{surah}:{a}' for a in source['contextAyahs']}]
        B.require(rows==evidence['entries'] and len(rows)==len(source['contextAyahs']),'parent context changed')
        B.require({e['fileRef'] for e in rows}=={source['url']} and parent['audioSha256'][surah-1]==source['sha256']==evidence['sourceSha256'],'parent audio mismatch')
        B.require(source['maxSourceSeconds']==7200,'source limit changed')
    elif source['evidenceKind']=='raw-heard':
        B.require(ident in ('hazmi67_23_26','hazmi67_tail','hazmi77_tail'),'unexpected raw heard source')
        B.require(evidence['engine']=='ctc-heardmap-1' and evidence['surah']==source['surah'] and evidence['riwaya']==source['riwaya']=='hafs','wrong raw alignment')
        B.require(evidence['fileRef']==source['url'] and evidence['sha256']==source['sha256'] and not evidence['issues'],'wrong or incomplete heard source')
        # Heard-only reports intentionally have no timing entries. They authorize diagnostics, never a splice.
        count={67:30,77:50}[source['surah']]
        B.require(evidence['entries']==[] and set(evidence['heardMap'])=={str(i) for i in range(1,count+1)},'incomplete heard-only map')
        B.require(all(isinstance(v,dict) and len(v.get('anchorMs',[]))==2 for v in evidence['heardMap'].values()),'invalid heard-only anchors')
        rb=(B.ROOT/'ops/out/codex-hazmi-heard-37400472678.json').read_bytes()
        B.require(hashlib.sha256(rb).hexdigest()=='4e76f3bd15e1a31954e2bb872e26ea5c08522911db4f0f97262c4ed634292b5a','rejection changed')
        rejection=json.loads(rb)
        B.require(rejection['measurementComplete'] and not rejection['measurementErrors'] and rejection['ok'] is False,'incomplete original rejection')
        B.require(source['maxSourceSeconds']==7200,'source limit changed')
    elif source['evidenceKind']=='qa-disagreement':
        B.require(evidence['sha256']=='fbf2b7997b428c6b45e858f11aecf681337dfbd5f2e69f57a65c43e275bb939c' and not evidence['fatal'],'wrong QA report')
        targets={r['aid'] for r in evidence['sample']['rows'] if r['kind']=='جسيم'}
        B.require(len(targets)==10 and source['targetId'] in targets,'not a measured severe disagreement')
        pb=(B.ROOT/source['parentPath']).read_bytes()
        B.require(hashlib.sha256(pb).hexdigest()==source['parentSha256']=='746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5','wrong parent')
        parent=json.loads(gzip.decompress(pb));byid={e['ayahId']:e for e in parent['entries']}
        B.require(parent['reciterId']=='m_abdulkareem_warsh' and parent['riwaya']==source['riwaya']=='warsh','wrong reader')
        s,a=map(int,source['targetId'].split(':'))
        B.require(source['surah']==s and source['contextAyahs']==list(range(a-1,a+2)),'wrong context')
        es=[byid[f'{s}:{n}'] for n in source['contextAyahs']]
        B.require(es==source['parentEntries'] and {e['fileRef'] for e in es}=={source['url']} and parent['audioSha256'][s-1]==source['sha256'],'wrong source or changed entries')
        B.require(source['maxSourceSeconds']==7200,'source limit changed')
    elif source['evidenceKind']=='metadata-source':
        measured=next(r for r in evidence['sources'] if r['id']=='shamrani_79_midad')
        B.require(ident=='shamrani79_midad_middle' and measured['ok'] and measured['pcm']['decodedWithoutErrors'],'unhealthy alternate source')
        B.require(source['sha256']==measured['file']['sha256'] and source['url']==measured['file']['finalUrl'] and source['surah']==measured['surah']==79 and source['riwaya']==measured['riwaya']=='hafs','alternate identity mismatch')
        B.require(source['maxSourceSeconds']==7200 and source['contextAyahs']==list(range(8,22)),'alternate scope changed')
    elif source['evidenceKind']=='heard-rejection':
        B.require(evidence['measurementComplete'] and not evidence['measurementErrors'] and evidence['ok'] is False,'rejected complete witness required')
        B.require(evidence['sha256']=='e3279a0914c45bc72ef6c24ed02ff3196ce3e3664936c352bc85ce60bcd31323' and source['surah']==21 and source['riwaya']=='warsh','wrong rejection')
        measured=evidence['maps']['21']
        B.require(source['sha256']==measured['sha256'] and source['url']==measured['fileRef'] and source['maxSourceSeconds']==7200,'rejected source mismatch')
        B.require(all(type(a)is int and 1<=a<=112 for a in source['contextAyahs']),'invalid rejected context')
    elif source['evidenceKind']=='koshi-rejection':
        B.require(evidence['measurementComplete'] and not evidence['measurementErrors'] and evidence['ok'] is False,'rejected complete witness required')
        B.require(evidence['sha256']=='db629f87eb79a0aca87c547ebc5856f08174e263be41591a4a984e4a616fa9d1' and source['surah']==11 and source['riwaya']=='warsh','wrong rejection')
        measured=evidence['maps']['11']
        B.require(source['sha256']==measured['sha256'] and source['url']==measured['fileRef'] and source['maxSourceSeconds']==7200,'rejected source mismatch')
        B.require(all(type(a)is int and 1<=a<=123 for a in source['contextAyahs']),'invalid rejected context')
    else:
        measured=evidence['sources'][0]
        B.require(ident in ('tblawi_head','tblawi_tail') and measured['ok'] and measured['pcm']['decodedWithoutErrors'],'invalid long-source exception')
        B.require(source['url']==measured['requestedUrl'] and source['sha256']==measured['file']['sha256']=='ec1ccc7f0f052e500eb173757d0ead4503071db2fbe9ce501c20fb156b0ca361','long source changed')
        B.require(source['maxSourceSeconds']==11000 and not source['contextAyahs'],'bounded free-only exception required')
    # Local read-only instance only: the measured ~3h source is explicitly pinned.
    # No strict decode checks are skipped and the shared helper file is unchanged.
    B.MAX_SOURCE_SECONDS=source['maxSourceSeconds']
    start,end=source['requestedWindowSeconds']
    B.require(type(start)is int and type(end)is int and 0<=start<end<=B.MAX_SOURCE_SECONDS and end-start<=70,'invalid window')
    S.metadata.validate_url(source['url'])
    return source,None


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--reader',choices=IDS,required=True)
    ap.add_argument('--model-policy',choices=('cache-only','quran-pinned-ephemeral'),default='cache-only');a=ap.parse_args(argv)
    rep={'schema':1,'kind':'source-context-and-content-diagnostic','reader':a.reader,'planSha256':PLAN_SHA,
      'measurementComplete':False,'qualityClaim':False,'productionChanged':False,'freeResults':[],'measurements':[],'models':[],'errors':[],
      'limits':['Context alignment may force absent text; compare free ASR and both models.','Existing candidate window may omit displaced speech.','No quality report, timing, confidence or Quran text is rewritten.'],
      'provenance':{'runId':os.environ.get('GITHUB_RUN_ID',''),'runSha':os.environ.get('GITHUB_SHA',''),'toolSha256':S.sha_file(__file__)}}
    try:
        source,idx=load_source(a.reader);rep['source']=source
        B.require(os.environ.get('CTC_INT8')=='0' and os.environ.get('CTC_THREADS')=='2','fixed CPU runtime required');rep['versions']=S.validate_versions()
        for k in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_XET'):os.environ[k]='1'
        contract=P.load_contract();common=importlib.import_module('common')
        begin,stop,_=common.surah_slice(common.load_index(),source['surah']);refs=common.load_text(source['riwaya'])[begin:stop]
        ids=[f"{source['surah']}:{n}" for n in source['contextAyahs']];canonical=[refs[int(i.split(':')[1])-1] for i in ids];rep['canonicalContext']=canonical
        assets=B.ROOT/'core/quran/src/main/assets/quran';rep['referenceSha256']={n:S.sha_file(assets/n) for n in ('index.jz',f"text_{source['riwaya']}.jz")}
        with tempfile.TemporaryDirectory(prefix='rafiq-short-defect-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
            path=Path(tmp)/'source.mp3';receipt=S.metadata.fetch(source['url'],path,limit=B.MAX_SOURCE_BYTES)
            B.require(receipt['sha256']==source['sha256'],'source changed');collector,proof=B.decode(path,source)
            rep['audio']={'download':receipt,**proof};channels=collector.channels();window=dict(source,windowSeconds=[collector.start/S.RATE,min(collector.frames,collector.end)/S.RATE])
            with S.model_snapshots(a.model_policy) as (snapshots,inventory):
                rep['modelAcquisition']=inventory
                for spec in S.MODELS:
                    backend=S.FreeCTC(snapshots[spec['name']],spec)
                    rep['models'].append({**spec,'vocabulary':backend.vocabulary,'files':S.model_files(snapshots[spec['name']],spec)})
                    for channel,raw in channels.items():
                        rep['freeResults'].append(S.measure_window(backend,raw,window,channel,spec['name'],
                            checkpoint=lambda part:S.emit(part,'SOURCE_CONTEXT_FREE_PART')))
                    del backend;gc.collect()
                import huggingface_hub as hub
                import numpy as np
                specs=P.model_specs(contract);bound={(s['id'],s['revision']):snapshots[s['name']] for s in specs}
                backend=P.Backend(importlib.import_module('ci_spoken_census'))
                with P.offline_model_loads(hub,specs,bound):
                    for name in (('generic','quran') if ids else ()):
                        model=backend.configure(name);texts=list(canonical) if name=='generic' else [backend.reference_text(t) for t in canonical]
                        for channel,raw in channels.items():
                            wav=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768.0
                            measured=P.raw_result(list(backend.segment(wav,texts)),ids,int(window['windowSeconds'][0]*1000),backend.conf)
                            row={'model':name,'channel':channel,'alignmentModel':model,'alignmentInput':texts,
                              'windowSeconds':window['windowSeconds'],'inputPcmSha256':hashlib.sha256(wav.tobytes()).hexdigest(),**measured}
                            rep['measurements'].append(row);S.emit(row,'SOURCE_CONTEXT_CONTEXT_PART')
                        backend.clear();gc.collect()
            B.require(S.sha_file(path)==source['sha256'],'source changed after inference')
            B.require(len(rep['freeResults'])==2*collector.count and len(rep['measurements'])==(2*collector.count if ids else 0),'incomplete matrix')
        load_source(a.reader);rep['measurementComplete']=True
    except Exception as exc:
        rep['errors'].append({'type':type(exc).__name__,'message':str(exc)[:240]})
    finally:S.emit(rep,'SOURCE_CONTEXT_REPORT')
    return 0 if rep['measurementComplete'] else 1

if __name__=='__main__':raise SystemExit(main())
