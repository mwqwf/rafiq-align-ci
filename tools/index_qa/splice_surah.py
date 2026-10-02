#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يستبدل مداخلَ سورةٍ (أو سور) في فهرسٍ قائم بمخرَجِ إعادةِ محاذاةٍ لها وحدها.

    python tools/index_qa/splice_surah.py --index in.jz --surah 22 \
        --aligned work/s022.json --url "https://host/{s:03d}.mp3" --out new.jz

**لماذا يوجد؟** لأن إعادةَ محاذاةِ قارئٍ كاملٍ لأجل سورةٍ واحدةٍ إنفاقُ ساعةٍ
على منجَز — والعلّةُ في `deban/22` و`lhdan/103` وأخواتِهما **سورةٌ واحدةٌ مزاحة**
لا فهرسٌ فاسد. (‏قرار المشرف github-10، 2026-09-05: الحجُّ أوّلُ ما يُعاد.)

## الحُرّاس — وكلٌّ منها من واقعة

1. **الفهرسُ لا يُمسّ إلا في السورة المطلوبة** — تُقارَن المداخلُ خارجها
   حرفاً قبل الكتابة وبعدها، فإن تغيّر مدخلٌ واحدٌ خارجها **يُوقَف كلُّ شيء**.
   (‏لا يُصلَح انحرافٌ بصمت: الإصلاحُ يمحو الدليل.)
2. **لا يُكتب مخرَجٌ ناقص:** إن رجعت المحاذاةُ بآيةٍ بلا حدود (`startMs is None`)
   فالسورةُ **لم تُحَلّ**، ويُردّ العملُ كلُّه بدل أن يُنتج فهرساً أسوأ من الأصل
   في موضعٍ ويُظنّ أحسن.
3. **عددُ الآيات يُطابَق بعدّ الرواية** لا بعدد ما رجع — فمخرَجٌ فيه آيتان
   لسورةٍ من ثلاثٍ يُردّ.
4. **الحدودُ تُفحص صعوداً** (‏`start < end` و`start[i] >= end[i-1]`)، فمخرَجٌ
   متداخلُ الحدود يُظهر للحافظ آيةً على صوت أختها.
5. ⛔ **ولا يُرفع من هنا:** المخرَجُ ملفٌّ محلّيّ، ورفعُه بـ`stage_transform.py`
   بحُرّاسه هو — كاتبٌ واحدٌ إلى الدلو لا كاتبان.
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

# عدُّ آي حفص — يُستعمل للتحقّق من اكتمال السورة المُعادة وحدها.
COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99,
          128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60,
          34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38,
          29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18,
          12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29,
          19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8,
          11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]


def load(p: Path) -> dict:
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def dump(d: dict, p: Path) -> str:
    raw = json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # ⛔ `mtime` معاملُ `GzipFile` لا `gzip.open` — و`gzip.open` يرفعه TypeError.
    #    وتثبيتُه صفراً مقصود: بصمةُ الملفّ يجب أن تتبع المحتوى وحده، فترويسةٌ
    #    فيها زمنُ البناء تُغيّر sha256 لمخرَجٍ لم يتغيّر.
    with open(p, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=9, mtime=0) as f:
            f.write(raw)
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parent_refs(entries, surahs) -> dict:
    """رابطُ ملفّ كلّ سورةٍ من مدخلاتها في الفهرس الأب نفسِه (‏مضيفُ المجلَّد).

    ⭐ (2026-09-28) مضيفٌ لا يرقّم أسماءه (‏`ar_036_Mustapha_Gharbi_Warsh.mp3`)
    لا يجمعه قالبُ `{s:03d}`؛ لكنّ السورةَ الناقصةَ حاضرةٌ جزئيّاً في الأب،
    فرابطُها معلومٌ وهو الذي يسمعه التطبيق. فيُؤخذ منه حرفاً ولا يُخمَّن.
    ⛔ سورةٌ بلا مدخلٍ في الأب، أو مدخلاتُها بأكثرَ من رابط، أو رابطٌ فارغ
    ⇒ **ردٌّ صريح** — لا رابطَ يُصطنع ولا يُرجَّح بين رابطين.
    """
    refs = {}
    for s in surahs:
        got = {e.get("fileRef") for e in entries
               if int(e["ayahId"].split(":")[0]) == s}
        if not got:
            sys.exit(f"⛔ س{s}: لا مدخلَ لها في الأب — رابطُ ملفّها مجهولٌ فلا يُخمَّن")
        if len(got) != 1:
            sys.exit(f"⛔ س{s}: مدخلاتُها في الأب بروابطَ مختلفة {sorted(map(str, got))} — لا يُرجَّح")
        ref = next(iter(got))
        if not isinstance(ref, str) or not ref.startswith(("https://", "http://")):
            sys.exit(f"⛔ س{s}: رابطُها في الأب غيرُ صالح ({ref!r})")
        refs[s] = ref
    return refs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--surah", required=True, help="سورةٌ أو أكثر بفواصل")
    ap.add_argument("--aligned", required=True, nargs="+",
                    help="مخرَجُ pipeline.py لكل سورة، بترتيب --surah")
    ap.add_argument("--url", required=True, help="قالبُ الصوت، مثل https://h/{s:03d}.mp3")
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-unresolved", action="store_true",
                    help="سورةٌ لم تُحلّ كلُّ آياتها تُترك كما هي في الأصل "
                         "وتُسمّى في المخرَج، بدل ردّ الدفعة كلِّها")
    ap.add_argument("--engine-tag", default="",
                    help="محرّكُ المحاذاة المدموجة إن خالف محرّكَ الفهرس (‏مثل "
                         "ctc-seg-1) — يُكتب في `engineBySurah` لكلّ سورةٍ أُخذت، "
                         "فيطلب حارسُ الترقية إحصاءً صوتيّاً شاملاً لها")
    ap.add_argument("--keep-parent-gaps", action="store_true",
                    help="آيةٌ بلا حدودٍ تُقبل **إن كانت غائبةً في الأب أصلاً** فتبقى غائبة (ctc_gapsplit)")
    ap.add_argument("--preserve-inherited-entries", action="store_true",
                    help="يحفظ المدخل الموروث ووسوم تقريب حدوده حرفياً؛ لا يقبل علامة inherited إذا اختلف الزمن أو الثقة أو المصدر")
    ap.add_argument("--alt-source", action="store_true",
                    help="صوتُ السور المأخوذة من مصدرٍ بديلٍ مسجَّل (‏غيرِ ملفّ الكتالوج) — "
                         "يُكتب قالبُ `--url` في `sourceBySurah` لكلّ سورةٍ أُخذت، "
                         "فيطلب حارسُ الترقية إحصاءً صوتيّاً شاملاً لها")
    ap.add_argument("--refs-from-parent", action="store_true",
                    help="مضيفُ مجلَّدٍ بلا {s:03d}: `fileRef` كلِّ سورةٍ يُؤخذ حرفاً من "
                         "مدخلاتها في الفهرس الأب، و`--url` هو المجلَّد الذي يجب أن "
                         "يبدأ به كلُّ رابط")
    ap.add_argument("--registered-sources", action="store_true",
                    help="روابط صريحة وبصمات مقيسة من سجل المصادر لهذا القارئ والرواية")
    # ⭐ **ذيلٌ مبتورٌ بأمر المالك 2026-10-02** («إن كان البترُ في أوّل السورة أو آخرها
    #    فلا بأس يُعلَن ذلك، لكن إن كان في الوسط تُلغى السورةُ بأكملها»): سورةٌ مصدرُها
    #    الوحيدُ ينقطع عند آية (النورُ عند العكري قالون) تُدمج **بادئتُها المتّصلة 1..N
    #    فقط**، وN يسمّيها المُطلِق صراحةً ويجب أن يطابقها إعلانُ المحاذي نفسِه
    #    (`truncatedTail.keep` في مخرَج `ctc_prefix_align.py`). والذيلُ N+1..آخرها يبقى
    #    غائباً ويُسجَّل `source_truncated` في الترويسة. ⛔ صفٌّ بعد N له حدود يُردّ
    #    (فلا يُنشر ما بعد البتر خلسةً)، وصفٌّ قبل N بلا حدود يُردّ (فلا فجوةَ وسطيّة).
    ap.add_argument("--truncated-tail", default="",
                    help="سورةٌ مبتورةُ الذيل تُدمج بادئتُها 1..N وحدها: «24:30» (وتجوز عدّة "
                         "بفواصل) — يلزمها --engine-tag، ولا تجتمع مع --keep-parent-gaps")
    args = ap.parse_args()
    trunc = {}
    for spec in [x for x in args.truncated_tail.replace(",", " ").split() if x]:
        try:
            s_, k_ = (int(v) for v in spec.split(":"))
        except ValueError:
            sys.exit(f"⛔ --truncated-tail بصيغة سورة:N مثل 24:30 لا {spec!r}")
        if not 1 <= s_ <= 114 or not 1 <= k_ < COUNTS[s_ - 1]:
            sys.exit(f"⛔ --truncated-tail {spec}: N يجب أن يكون بين 1 و{COUNTS[s_ - 1] - 1}")
        trunc[s_] = k_
    if trunc and (not args.engine_tag or args.keep_parent_gaps):
        sys.exit("⛔ --truncated-tail يلزمه --engine-tag ولا يجتمع مع --keep-parent-gaps")

    surahs = [int(x) for x in args.surah.replace(",", " ").split()]
    if len(surahs) != len(args.aligned):
        sys.exit("⛔ عددُ السور لا يطابق عددَ ملفّات المحاذاة")
    if not set(trunc) <= set(surahs):
        sys.exit(f"⛔ --truncated-tail يسمّي سوراً ليست في --surah: {sorted(set(trunc) - set(surahs))}")

    idx = load(Path(args.index))
    entries = idx.get("entries") or []
    # ⛔ قالبٌ بلا `{s:03d}` كان يكتب المجلَّدَ نفسَه `fileRef` لكلّ آية بصمت
    #    (‏`str.format` بلا حقلٍ يرجع النصَّ كما هو) — فيُردّ ما لم يُطلب
    #    الأخذُ من الأب صراحةً، ولا يجتمع الأخذُ من الأب مع مصدرٍ بديل.
    refs = None
    if args.registered_sources:
        if args.refs_from_parent or not args.alt_source:
            sys.exit("⛔ المصدر المسجّل يحتاج --alt-source ولا يجتمع مع --refs-from-parent")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ci_fleet"))
        from source_registry import registered_source
        refs = {}
        registered = {}
        for s in surahs:
            try:
                registered[s] = registered_source(idx["riwaya"], idx["reciterId"], s)
            except (ValueError, KeyError) as ex:
                sys.exit(f"⛔ س{s}: {ex}")
            refs[s] = registered[s]["url"]
    elif args.refs_from_parent:
        if "{s" in args.url:
            sys.exit("⛔ --refs-from-parent لمضيف المجلَّد وحده — والقالبُ هنا مرقَّم")
        if args.alt_source:
            sys.exit("⛔ لا يجتمع --refs-from-parent و--alt-source: الأبُ يصف مصدرَ الكتالوج")
        refs = parent_refs(entries, surahs)
        for s, r in refs.items():
            if not r.startswith(args.url):
                sys.exit(f"⛔ س{s}: رابطُها في الأب {r} خارجَ المجلَّد {args.url}")
    elif "{s:03d}" not in args.url:
        sys.exit("⛔ القالبُ بلا {s:03d} — استعمل --refs-from-parent لمضيف المجلَّد، ولا يُخمَّن")
    before_out = [e for e in entries if int(e["ayahId"].split(":")[0]) not in surahs]
    aligned_of = dict(zip(surahs, args.aligned))        # قبل أن تُستبدل القائمةُ بالمأخوذ

    new_rows, skipped, taken = [], [], []
    model_records = {}
    for s, af in zip(surahs, args.aligned):
        res = json.load(open(af, encoding="utf-8"))
        if args.engine_tag == 'ctc-dual-window-1':
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'alignment_v3'))
            from dual_ctc_model import evidence_error
            if res.get('engine') != args.engine_tag:
                sys.exit(f'⛔ س{s}: complementary model engine is not declared')
            error = evidence_error(res.get('dualAlignmentEvidence') or {},
                                   res.get('sha256'), res.get('entries') or [])
            if error:
                sys.exit(f'⛔ س{s}: {error}')
        if args.engine_tag in ('ctc-quran-window-1', 'ctc-quran-surah-1'):
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'alignment_v3'))
            from quran_ctc_model import MODEL_ID, REVISION, WEIGHTS_SHA256
            ev = res.get('alignmentModel') or {}
            if (res.get('engine') != args.engine_tag or ev.get('id') != MODEL_ID
                    or ev.get('revision') != REVISION or ev.get('weightsSha256') != WEIGHTS_SHA256
                    or ev.get('license') != 'Apache-2.0' or ev.get('canonicalTextChanged') is not False):
                sys.exit(f'⛔ س{s}: محرك التلاوة بلا نسب نموذج ثابت صحيح')
            model_records[str(s)] = ev
        if args.registered_sources:
            if (res.get("sourceUrl") != refs[s]
                    or not registered[s].get("audio_sha256")
                    or res.get("audioSha256") != registered[s]["audio_sha256"]):
                sys.exit(f"⛔ س{s}: رابط أو بصمة المحاذاة لا يطابقان المصدر المسجّل")
        rows = res.get("entries") or []
        want = COUNTS[s - 1]
        # ⛔ **الردُّ بالسورة لا بالدفعة** (‏تصحيحُ 2026-09-05): كان خللٌ في
        #    آيةٍ واحدةٍ يردّ اثنتي عشرةَ سورةً سليمةً معها — عقوبةٌ على
        #    التجميع لا على العطب. فالسورةُ التي لم تُحَلّ **تُترك كما هي في
        #    الأصل وتُسمَّى**، والباقياتُ تمضي. والمبدأ محفوظ: لا يُكتب ناقصٌ
        #    في موضعٍ ولا يُمسّ ما لم يُحَلّ.
        bad = None
        # ⛔ **الغيابُ الموروث لا يُعدّ حلّاً ولا نقضاً** (‏ctc_gapsplit · 2026-09-29):
        #    مع `--keep-parent-gaps` تُقبل الآيةُ بلا حدودٍ **إن كانت غائبةً في الأب**
        #    فتبقى غائبةً كما كانت؛ وما كان حاضراً في الأب ثم غاب يُردّ كما قبل.
        parent_has = {int(e["ayahId"].split(":")[1]) for e in entries
                      if int(e["ayahId"].split(":")[0]) == s
                      and e.get("startMs") is not None and e.get("endMs") is not None}
        keep_gap = set()
        if args.keep_parent_gaps:
            keep_gap = {i + 1 for i, r in enumerate(rows)
                        if (r.get("startMs") is None or r.get("endMs") is None)
                        and (i + 1) not in parent_has}
        # ⭐ الذيلُ المبتور (أمر المالك 2026-10-02): يُقبل من الصفوف 1..N فقط، وN المسمّاةُ
        #    من المُطلِق يجب أن تساوي ما أعلنه المحاذي في مخرَجه — فلا تتفرّق N بين يدين.
        #    وما قبل N بلا حدودٍ ردٌّ (فجوةٌ وسطيّة)، وما بعد N بحدودٍ ردٌّ (نشرٌ بعد البتر).
        tail_keep = trunc.get(s)
        if tail_keep is not None:
            declared = (res.get("truncatedTail") or {}).get("keep")
            if declared != tail_keep:
                sys.exit(f"⛔ س{s}: المحاذي يُعلن بادئةً حتى {declared!r} والمُطلِق يسمّي "
                         f"{tail_keep} — لا يُدمج ما لم تتّفق اليدان")
            if not parent_has <= set(range(1, tail_keep + 1)):
                sys.exit(f"⛔ س{s}: الأبُ فيه مداخلُ بعد {tail_keep} "
                         f"({sorted(parent_has - set(range(1, tail_keep + 1)))[:5]}) — "
                         f"بادئةٌ مبتورةٌ لا تُنقص ما كان منشوراً")
        if len(rows) != want:
            bad = f"رجعت {len(rows)} آية والرواية {want}"
        else:
            prev = -1
            for i, r in enumerate(rows):
                st, en = r.get("startMs"), r.get("endMs")
                if (i + 1) in keep_gap:
                    continue
                if tail_keep is not None and i >= tail_keep:
                    if st is not None or en is not None:
                        bad = f"{i + 1} لها حدودٌ بعد البتر المعلَن عند {tail_keep}"; break
                    continue
                if st is None or en is None:
                    bad = f"{i + 1} بلا حدود"; break
                if not (0 <= st < en) or st < prev:
                    bad = f"{i + 1} حدودٌ غيرُ صاعدة ({st}→{en})"; break
                prev = en
        if bad:
            if not args.skip_unresolved:
                sys.exit(f"⛔ س{s}:{bad} — السورةُ لم تُحَلّ، ولا يُكتب ناقص")
            skipped.append(f"س{s}: {bad}")
            continue
        taken.append(s)
        prev_end = -1
        for i, r in enumerate(rows):
            if (i + 1) in keep_gap:
                continue
            if tail_keep is not None and i >= tail_keep:
                continue                               # الذيلُ المبتور يبقى غائباً معلَناً
            st, en = r.get("startMs"), r.get("endMs")
            prev_end = en
            conf = float(r.get("conf") or 0.0)
            if args.preserve_inherited_entries and r.get("inherited"):
                old = next((e for e in entries if e["ayahId"] == f"{s}:{i + 1}"), None)
                source_ref = refs[s] if refs else args.url.format(s=s)
                if (not old or old["fileRef"] != source_ref
                        or old["startMs"] != st or old["endMs"] != en
                        or abs(float(old.get("conf") or 0) - conf) > .000001
                        or bool(r.get("snapped")) == bool(old.get("startApprox", False))):
                    sys.exit(f"⛔ مدخل {s}:{i + 1} معلن موروثاً وقياسه تغيّر — لا يُنسخ")
                new_rows.append(dict(old))
                continue
            band = "HIGH" if conf >= 0.8 else ("MED" if conf >= 0.5 else "LOW")
            row = {"ayahId": f"{s}:{i + 1}", "fileRef": refs[s] if refs else args.url.format(s=s),
                   "startMs": int(st), "endMs": int(en),
                   "conf": round(conf, 3), "confBand": band}
            if r.get("snapped") is False:
                row["startApprox"] = True
            new_rows.append(row)

    if args.skip_unresolved:
        surahs = taken
        before_out = [e for e in entries
                      if int(e["ayahId"].split(":")[0]) not in surahs]
        if not surahs:
            why = " · ".join(skipped) if skipped else "لا سببَ مسجَّل"
            sys.exit(f"⛔ لم تُحلّ سورةٌ واحدة — لا شيءَ يُستبدل ({why})")
    merged = before_out + new_rows
    merged.sort(key=lambda e: (int(e["ayahId"].split(":")[0]),
                               int(e["ayahId"].split(":")[1])))

    # ⛔ الحارس 1: ما خارج السور المطلوبة لم يُمسّ — يُقارَن حرفاً.
    after_out = [e for e in merged if int(e["ayahId"].split(":")[0]) not in surahs]
    if json.dumps(before_out, sort_keys=True) != json.dumps(after_out, sort_keys=True):
        sys.exit("⛔ تغيّر مدخلٌ خارج السور المطلوبة — يُوقَف ولا يُصلَح بصمت")

    out = dict(idx, entries=merged)
    # ⛔ **الخلطُ يُعلَن في الترويسة ولا يُخفى** (‏2026-09-24): سورةٌ أُخذت من
    #    محرّكٍ غيرِ محرّك الفهرس تُسجَّل باسمه، وما أُعيد بمحرّك الفهرس نفسِه
    #    يُمحى من السجلّ — فيبقى `engineBySurah` وصفاً صادقاً لكلّ سورة.
    ebs = {k: v for k, v in dict(idx.get("engineBySurah") or {}).items()
           if int(k) not in surahs}
    if args.engine_tag and args.engine_tag != idx.get("engineVersion"):
        for s in surahs:
            ebs[str(s)] = args.engine_tag
    if ebs:
        out["engineBySurah"] = dict(sorted(ebs.items(), key=lambda kv: int(kv[0])))
    else:
        out.pop("engineBySurah", None)
    models = {k:v for k,v in (idx.get('alignmentModelBySurah') or {}).items()
              if int(k) not in surahs}
    models.update({str(s):model_records[str(s)] for s in surahs if str(s) in model_records})
    if models:
        out['alignmentModelBySurah'] = models
    else:
        out.pop('alignmentModelBySurah', None)
    dual = {k: v for k, v in (idx.get('dualAlignmentEvidenceBySurah') or {}).items()
            if int(k) not in surahs}
    if args.engine_tag == 'ctc-dual-window-1':
        for s, af in zip(surahs, args.aligned):
            dual[str(s)] = json.load(open(af, encoding='utf-8'))['dualAlignmentEvidence']
    if dual:
        out['dualAlignmentEvidenceBySurah'] = dual
    else:
        out.pop('dualAlignmentEvidenceBySurah', None)
    # ⛔ **والمصدرُ البديلُ يُعلَن كذلك** (‏2026-09-28): سورةٌ جاء صوتُها من
    #    تسجيلٍ غيرِ ملفّ الكتالوج تُسجَّل بقالبها في `sourceBySurah` ولو كان
    #    المحرّكُ محرّكَ الفهرس نفسَه — فقد تغيّر الصوتُ لا المحرّك. وما أُعيد
    #    من مصدر الكتالوج يُمحى منه، فيبقى السجلُّ وصفاً صادقاً لكلّ سورة.
    sbs = {k: v for k, v in dict(idx.get("sourceBySurah") or {}).items()
           if int(k) not in surahs}
    if args.alt_source:
        for s in surahs:
            sbs[str(s)] = refs[s] if args.registered_sources else args.url
    if sbs:
        out["sourceBySurah"] = dict(sorted(sbs.items(), key=lambda kv: int(kv[0])))
    else:
        out.pop("sourceBySurah", None)
    miss = dict(out.get("missing") or {})
    ids = [e["ayahId"] for e in merged]
    have = set(ids)
    all_ids = [f"{s}:{a}" for s in range(1, 115) for a in range(1, COUNTS[s - 1] + 1)]
    gone = [i for i in all_ids if i not in have]
    miss["count"] = len(gone)
    miss["ids"] = gone[:400]
    # السورُ المُعادةُ تخرج من عذر البتر: عادت مداخلُها فلا غيابَ يُعتذر عنه.
    by = dict(miss.get("byReason") or {})
    if by.get("source_truncated"):
        back = sum(COUNTS[s - 1] for s in surahs)
        by["source_truncated"] = max(0, int(by["source_truncated"]) - back)
        if not by["source_truncated"]:
            by.pop("source_truncated")
    # ⭐ الذيلُ المبتور يُسجَّل بسببه (أمر المالك 2026-10-02): آياتُ N+1..آخرها تُعدّ
    #    `source_truncated`، ولا تُترك الدلاءُ العامّةُ (unknown/no-align) تدّعي أكثرَ ممّا
    #    بقي غائباً خارج السورة المبتورة — فتُستنزف إلى ما يصفه الغيابُ فعلاً.
    trunc_taken = {s: k for s, k in trunc.items() if s in surahs}
    if trunc_taken:
        other = [i for i in gone if int(i.split(":")[0]) not in trunc_taken]
        tail_total = sum(COUNTS[s - 1] - k for s, k in trunc_taken.items())
        generic = {k: int(v) for k, v in by.items() if k != "source_truncated"}
        excess = sum(generic.values()) - len(other)
        for g in ("unknown", "no-align", "no_align", "unaligned"):
            if excess <= 0:
                break
            take = min(excess, generic.get(g, 0))
            if take:
                generic[g] -= take
                excess -= take
                if not generic[g]:
                    generic.pop(g)
        by = dict(generic, source_truncated=int(by.get("source_truncated", 0)) + tail_total)
    miss["byReason"] = by
    out["missing"] = miss
    if trunc_taken:
        prior = dict(out.get("transform") or {}) if isinstance(out.get("transform"), dict) else {}
        tt = dict(prior.get("truncatedTail") or {})
        for s, k in trunc_taken.items():
            res = json.load(open(aligned_of[s], encoding="utf-8"))
            tt[str(s)] = {"published": k, "absentFrom": k + 1, "absentTo": COUNTS[s - 1],
                          "reason": "source_truncated", "sourceSha256": res.get("sha256"),
                          "totalMs": res.get("totalMs")}
        prior["truncatedTail"] = tt
        # السورةُ صارت حاضرةً (بادئةً) فلا تبقى في إعلان الغياب الكلّيّ الموروث.
        ds = [x for x in (prior.get("dropSurah") or []) if int(x) not in trunc_taken]
        if ds:
            prior["dropSurah"] = ds
        else:
            prior.pop("dropSurah", None)
        out["transform"] = prior

    if args.registered_sources:
        # stage_transform يغيّر op؛ يبقى إعلان الغياب الموروث للسور التي
        # ما زالت غائبة، ويُزال عن السور المسترجعة فعلاً.
        prior = dict(out.get("transform") or {})
        import re
        declared = set(prior.get("dropSurah") or [])
        for group in re.findall(r"drop_surah:([\d,\s]+)", str(prior.get("op") or "")):
            declared.update(int(s) for s in re.findall(r"\d+", group))
        present = {int(e["ayahId"].split(":")[0]) for e in merged}
        prior["dropSurah"] = sorted(declared - present)
        out["transform"] = prior

    # ⛔ **التحويلُ يُسمّي ما استُبدل فعلاً لا ما طُلب** (‏2026-09-07): مع
    #    `--skip-unresolved` قد تُترك سورةٌ كما هي، ثم يُسمّيها `--op` فيطالب
    #    حارسُ `stage_transform` بعدّها كاملاً فيسقط الإصلاحُ كلُّه. فتُكتب
    #    القائمةُ المأخوذةُ بجانب المخرَج ليقرأها المُطلِق.
    # ⛔ **بصمةُ التنزيل للسورة التي لم تكن موجودةً أصلاً** (2026-09-08):
    #    `audioSha256` قائمةٌ **موضعيّة** على السورِ التي نزل صوتُها وقتَ البناء،
    #    لا على 1..114. فإذا سقط تنزيلُ سورةٍ في المحاذاة الأولى نقصت القائمةُ
    #    واحداً **وانزاح كلُّ ما بعدها**؛ ثم تأتي `realign_surah` فتردّ مداخلَ
    #    السورة **ولا تردّ بصمتَها**، فيبقى الفهرس مردوداً بـ«بصمات الصوت
    #    113/114 — سورٌ بلا برهان تنزيل» وإن كانت مداخلُه تامّة.
    #    وقِيس على `laghdaf_shinqiti` (‏آخرُ قرّاء ورش): البصمةُ الأولى للسورة 1
    #    عند الموضع 0، وسورةُ 72 عند **70 لا 71** — أي الانزياحُ مؤكَّدٌ قياساً.
    # ⇒ فتُحسب البصمةُ من الملفّ نفسِه وتُدرَج **في موضعها من الترتيب**.
    # ⛔ ولا يعمل هذا إلا للسورة التي **لم يكن لها مدخلٌ واحد** في الأصل، ولا
    #    يمسّ قائمةً تامّةً (114) ولا قائمةً لا يوافق طولُها سورَ الأصل — فما
    #    عدا هذه الحالة يخرج المخرَجُ **مطابقاً لما كان حرفاً**.
    shas = list(out.get("audioSha256") or [])
    orig_surahs = sorted({int(e["ayahId"].split(":")[0]) for e in entries})
    added = [s for s in surahs if s not in orig_surahs]
    if args.registered_sources:
        if len(shas) != 114:
            sys.exit("⛔ المصدر المسجّل يتطلب قائمة بصمات أصلية من 114 سورة")
        for s in surahs:
            shas[s - 1] = registered[s]["audio_sha256"]
        out["audioSha256"] = shas
    if added and refs is not None and not args.registered_sources:
        sys.exit(f"⛔ سورٌ بلا مدخلٍ في الأب مع --refs-from-parent: {added}")
    if added and len(shas) == len(orig_surahs) and len(shas) < 114:
        import urllib.request as _u
        for s in sorted(added):
            url = args.url.format(s=s)
            blob, last = None, None
            for attempt in range(5):                       # شبكةٌ ضعيفةٌ متقطّعة
                try:
                    req = _u.Request(url, headers={          # r2.dev يردّ 403 على الوكيل الافتراضي
                        "User-Agent": "Mozilla/5.0 (QuranRafiq tools)"})
                    with _u.urlopen(req, timeout=120) as r:
                        want = int(r.headers.get("Content-Length") or 0)
                        blob = r.read()
                    if want and len(blob) != want:          # تنزيلٌ مبتورٌ بصمتٍ لا يُقبل
                        blob, last = None, f"نزل {len(blob)} من {want}"
                        continue
                    break
                except Exception as e:                      # noqa: BLE001
                    last, blob = str(e)[:90], None
                    time.sleep(2 ** attempt)
            if blob is None:
                sys.exit(f"⛔ تعذّر جلبُ صوت س{s} لحساب بصمته: {last}")
            pos = bisect.bisect_left(orig_surahs, s)
            shas.insert(pos, hashlib.sha256(blob).hexdigest())
            orig_surahs.insert(pos, s)
            print(f"  🔑 بصمةُ س{s} أُدرجت في الموضع {pos} · البصمات {len(shas)}/114")
        out["audioSha256"] = shas

    Path(str(args.out) + ".taken").write_text(
        ",".join(str(s) for s in surahs), encoding="utf-8")
    sha = dump(out, Path(args.out))
    for w in skipped:
        print("  ⚠️ تُركت كما هي:", w)
    print(f"المداخل {len(entries)} ⇐ {len(merged)} · الغياب {(idx.get('missing') or {}).get('count')}"
          f" ⇐ {miss['count']} · سور {surahs}")
    print(f"✅ {args.out} · sha256 {sha[:16]}…")


if __name__ == "__main__":
    main()
