#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يرفع **منتَجَ تحويلٍ** مصنوعاً خارج مسار الأسطول إلى الاختبار — ببرهانٍ لا بثقة.

    python tools/index_qa/stage_transform.py --file tools/tasmi_bench/work/fix_hawashi.jz \
        --parent timings/hafs/hawashi.jz --parent-sha 57958521e6f2 \
        --op "basmala_fix" --reason "..." --yes

**لماذا أداةٌ ثانية؟** لأن `stage_upload.py` يشترط شجرة بناء أسطول
(`batch_<rid>/s*.json`) و**منتَجُ تحويلٍ لا يملكها بحال** — فوقف github-8e عند
حارسه ولم يلتفّ عليه، وهو الصواب. والحلُّ مسارٌ ثانٍ **بحُرّاسٍ تخصّه**، لا
ثقبٌ في الأول.

**ما يتحقّق منه قبل الرفع (‏قرار github-f4):**

1. **الأصلُ منشورٌ فعلاً** في `timings/`، وبصمتُه هي المذكورة — فلا يُبنى
   مشتقٌّ على فهرسٍ لا نعرف عينه.
2. **عددُ المداخل مطابقٌ للأصل حرفاً** — فالتحويلُ **يزيح حدوداً ولا يحذف
   آيات**؛ واختلافُ العدد يعني أنّ شيئاً آخر جرى.
3. **‏`entriesSha256` مختلفةٌ عن الأصل** — وإلا فالملفّ **لم يتغيّر** وادّعاءُ
   الإصلاح باطل. (‏عكسُ شرط `rename_reciter` تماماً: هناك تُشترط المطابقة
   لأن التسمية لا تمسّ المحتوى، وهنا يُشترط الاختلاف لأن القصّ يمسّه.)
4. **حارسا الهويّة والبنية** (`catalog_gate` و`index_gate`) على المنتَج نفسه.

ثمّ يُكتب أثرُ التحويل في الترويسة (`transform`) بالبصمتين، وتُرفع النسخة إلى
`timings-staging/{riwaya}/{reciter}.{بصمة}.jz` بميتاداتا تقول من صنعها وعمّن.
⛔ **ولا تُرقّى بذلك**: تدخل الطابور مشتقّاً كأيّ مرشّح — فحصُ مطالعَ وعيّنةٌ
كاملة على بصمتها هي، ثمّ حكمُ البوابة.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import promote                                                       # noqa: E402
from rename_reciter import entries_sha                               # noqa: E402


AYAH_COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52,
               99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69,
               60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35,
               38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11,
               18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
               29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8,
               8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]


def ascii_meta(v: str) -> str:
    """يطوي قيمةَ ميتاداتا إلى ASCII — لأن S3 يردّ ما سواه (‏وقع 2026-09-08).

    ⛔ **للميتاداتا وحدَها**: الأصلُ العربيّ يبقى في ترويسة الفهرس (`transform`)
    فلا تُفقد النسبة. وما لا يُطوى يصير `?` ولا يُحذف الحقلُ بحال، إذ حقلٌ
    غائبٌ يُقرأ «لا صانعَ له» وهو أسوأُ من نسبةٍ مشوّهة.
    """
    s = (v or "").encode("ascii", "replace").decode("ascii")
    return s or "unknown"


def entry_change_counts(parent, candidate):
    """المقارنة بالمعرف؛ إضافة آية لا تعني أن كل ما بعدها تحرك."""
    old = {e["ayahId"]: e for e in parent}
    new = {e["ayahId"]: e for e in candidate}
    if len(old) != len(parent) or len(new) != len(candidate):
        raise ValueError("معرف آية مكرر في عداد التغيير")
    moved = sum(1 for aid in old.keys() & new.keys()
                if (old[aid].get("startMs"), old[aid].get("endMs"))
                != (new[aid].get("startMs"), new[aid].get("endMs")))
    return moved, len(new.keys() - old.keys()), len(old.keys() - new.keys())


def realigned_coverage_error(have_old, have_new, realigned, allow_inherited=False):
    """نصُّ الردّ أو None — تغطيةُ السور المُعادة.

    الأصلُ (‏بلا الخيار، كما كان حرفاً): كلُّ سورةٍ مُعادةٍ كاملةٌ بعدد الرواية.
    ⭐ ومع `allow_inherited` (‏ctc_gapsplit · 2026-09-30): قسمةُ المبتلع قد تسترجع بعضَ
    الغائب وتُبقي بعضَه، فيُقبل الناقصُ **بشرطين مجتمعين**: ① لا غائبَ جديد (‏كلُّ مدخلٍ
    في الأب حاضرٌ في المخرَج) ② زيادةٌ فعليّةٌ في مداخل السور المُعادة. فلا يُرفع ما يُنقص
    شيئاً ولا ما لا يزيد شيئاً."""
    old_in = {i for i in have_old if int(i.split(":")[0]) in realigned}
    new_in = {i for i in have_new if int(i.split(":")[0]) in realigned}
    want = sum(AYAH_COUNTS[s - 1] for s in realigned)
    if len(new_in) == want:
        return None
    if not allow_inherited:
        return (f"⛔ السورُ المُعادة {realigned}: مداخلُها {len(new_in)} "
                f"والرواية {want} — لا يُرفع ناقص")
    lost = sorted(old_in - new_in, key=lambda x: tuple(map(int, x.split(":"))))
    if lost:
        return f"⛔ غابت آياتٌ كانت في الأب: {lost[:6]} — لا يُرفع ما يُنقص"
    if len(new_in) <= len(old_in):
        return f"⛔ السورُ المُعادة {realigned} لم تزد مداخلُها ({len(old_in)} ⇐ {len(new_in)}) — لا شيءَ يُرفع"
    return None

def parse_tails(spec: str) -> dict:
    """«24:30[,s:N…]» ⇒ {24: 30} — ويُردّ ما ليس بين 1 وعدد الرواية−1."""
    out = {}
    for item in [x for x in (spec or "").replace(",", " ").split() if x]:
        try:
            s, n = (int(v) for v in item.split(":"))
        except ValueError:
            raise SystemExit(f"⛔ --owner-truncated-tail بصيغة سورة:N مثل 24:30 لا {item!r}")
        if not 1 <= s <= 114 or not 1 <= n < AYAH_COUNTS[s - 1]:
            raise SystemExit(f"⛔ --owner-truncated-tail {item}: N بين 1 و{AYAH_COUNTS[s - 1] - 1}")
        out[s] = n
    return out


def truncated_tail_error(have_old, have_new, realigned, tails):
    """نصُّ الردّ أو None — تغطيةُ السور المُعادة **مع ذيلٍ مبتورٍ مسمّى**.

    ⭐ أمرُ المالك 2026-10-02: «إن كان البترُ في أوّل السورة أو آخرها فلا بأس يُعلَن ذلك،
    لكن إن كان في الوسط تُلغى السورةُ بأكملها». فالسورةُ المسمّاةُ في `tails` تُقبل
    **فقط** إن كانت مداخلُها بادئةً متّصلةً 1..N بلا فجوة، وN هي المسمّاةُ صراحةً لا
    غيرها (أكثرُ منها نشرٌ بعد البتر، وأقلُّ منها إعلانُ غيابٍ لما له صوت)، ولم تفقد
    مدخلاً كان في الأب، وزادت عليه فعلاً. وما سواها من السور المُعادة يبقى على الحارس
    الأصل: كاملٌ بعدد الرواية. ⛔ والحارسُ الأصل (`realigned_coverage_error`) لم يُمسّ:
    هذا بابٌ ثانٍ لا يُفتح إلا بالخيار الصريح."""
    for s in sorted(tails):
        if s not in realigned:
            return f"⛔ الذيلُ المبتور يسمّي س{s} وهي ليست من السور المُعادة {realigned}"
    for s in realigned:
        new_s = sorted(int(i.split(":")[1]) for i in have_new if int(i.split(":")[0]) == s)
        old_s = sorted(int(i.split(":")[1]) for i in have_old if int(i.split(":")[0]) == s)
        if s not in tails:
            if len(new_s) != AYAH_COUNTS[s - 1]:
                return (f"⛔ السورةُ المُعادة {s}: مداخلُها {len(new_s)} والرواية "
                        f"{AYAH_COUNTS[s - 1]} — لا يُرفع ناقص")
            continue
        n = tails[s]
        if new_s != list(range(1, n + 1)):
            gaps = sorted(set(range(1, n + 1)) - set(new_s))
            beyond = [k for k in new_s if k > n]
            if gaps:
                return f"⛔ س{s}: فجوةٌ وسطيّة {gaps[:6]} — البترُ في الوسط يُلغي السورةَ كلَّها"
            if beyond:
                return f"⛔ س{s}: مداخلُ بعد N={n}: {beyond[:6]} — لا يُنشر ما بعد البتر المعلَن"
            return f"⛔ س{s}: المداخلُ {len(new_s)} والبادئةُ المسمّاة 1..{n} لا تتطابق"
        if not set(old_s) <= set(new_s):
            return f"⛔ س{s}: غابت آياتٌ كانت في الأب: {sorted(set(old_s) - set(new_s))[:6]}"
        if len(new_s) <= len(old_s):
            return f"⛔ س{s}: لم تزد مداخلُها ({len(old_s)} ⇐ {len(new_s)}) — لا شيءَ يُرفع"
    return None


def truncated_header_error(idx, tails):
    """الترويسةُ تقول ما تقوله المداخل: `transform.truncatedTail` و`missing` متّسقان."""
    tr = idx.get("transform") if isinstance(idx.get("transform"), dict) else {}
    tt = (tr or {}).get("truncatedTail") or {}
    miss = idx.get("missing") or {}
    ids = set(miss.get("ids") or [])
    excused = int((miss.get("byReason") or {}).get("source_truncated", 0))
    need = 0
    for s, n in tails.items():
        rec = tt.get(str(s))
        if not isinstance(rec, dict) or rec.get("published") != n \
                or rec.get("absentFrom") != n + 1 or rec.get("absentTo") != AYAH_COUNTS[s - 1] \
                or rec.get("reason") != "source_truncated":
            return f"⛔ س{s}: الترويسة لا تُعلن الذيلَ المبتور {n + 1}..{AYAH_COUNTS[s - 1]} بسبب source_truncated"
        tail = {f"{s}:{k}" for k in range(n + 1, AYAH_COUNTS[s - 1] + 1)}
        if not tail <= ids:
            return f"⛔ س{s}: وسمُ الاكتمال لا يعدّ الذيلَ المبتور كلَّه غائباً"
        need += len(tail)
    if excused < need:
        return f"⛔ byReason.source_truncated = {excused} والذيلُ المبتور {need}"
    return None


def apply_dispatch_policy(index, enabled, parent_key, parent_sha):
    """سياسة جدولة للتحويل الحالي فقط؛ لا تغير مدخلاً أو حارس جودة."""
    index["transform"].pop("qaDispatch", None)
    if enabled:
        sys.path.insert(0, str(HERE.parent / "ci_fleet"))
        from qa_dispatch_guard import manual_qa_policy
        index["transform"]["qaDispatch"] = manual_qa_policy(index, parent_key, parent_sha)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="ملفّ المنتَج المحلّي (.jz)")
    ap.add_argument("--parent", required=True,
                    help="مفتاحُ الأصل: منشورٌ في timings/ أو مرشَّحٌ في "
                         "timings-staging/ لقارئه نفسِه")
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--op", required=True, help="اسمُ التحويل، مثل basmala_fix")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--by", default="github-8e", help="صانعُ التحويل")
    ap.add_argument("--metadata-only", metavar="سبب",
                    help="تصحيحُ حقولِ الترويسة وحدها والمداخلُ متطابقةٌ بايتاً "
                         "— يجب أن يذكر السببُ الحقلَ والقياسَ الذي بُني عليه")
    ap.add_argument("--allow-inherited-gaps", action="store_true",
                    help="(ctc_gapsplit وحده) سورةٌ مُعادةٌ ناقصةٌ تُقبل إن كان كلُّ غائبٍ فيها غائباً في الأب "
                         "ولا غائبَ جديد، وزادت مداخلُها زيادةً فعليّة")
    # ⭐ **أمرُ المالك 2026-10-02** («إن كان البترُ في أوّل السورة أو آخرها فلا بأس يُعلَن
    #    ذلك، لكن إن كان في الوسط تُلغى السورةُ بأكملها»): بابٌ ضيّقٌ ثانٍ لسورةٍ مُعادةٍ
    #    ناقصةٍ — يُقبل **فقط** إن كانت مداخلُها بادئةً متّصلةً 1..N، وN مسمّاةٌ هنا صراحةً،
    #    والباقي مسجَّلٌ `source_truncated` في الترويسة (`transform.truncatedTail` + `missing`).
    #    والحارسُ الأصل يبقى كما هو بلا هذا الخيار.
    ap.add_argument("--owner-truncated-tail", default="",
                    help="سورةٌ مبتورةُ الذيل تُقبل بادئتُها 1..N وحدها: «24:30» — بادئةٌ "
                         "متّصلةٌ بلا فجوة، وN المسمّاةُ هي الحدّ، والذيلُ معلَنٌ source_truncated")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--manual-qa-only", action="store_true",
                    help="حصر هذا المرشح في فحوص يدوية مجانية؛ لا يعفيه من أي حارس")
    a = ap.parse_args()
    tails = parse_tails(a.owner_truncated_tail)
    if tails and a.allow_inherited_gaps:
        raise SystemExit("⛔ --owner-truncated-tail لا يجتمع مع --allow-inherited-gaps")

    cl, bucket = promote.s3()
    blob = Path(a.file).read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    idx = json.loads(gzip.decompress(blob).decode("utf-8"))

    # ⛔ **الأصلُ من الاختبار مقبولٌ لقارئه نفسِه** (‏حكم المشرف 2026-09-05،
    #    كسرُ الحلقة المغلقة): كان الأصلُ يجب أن يكون منشوراً، فانحبس ثلاثةُ
    #    فهارسَ أُعيد بناؤها (99.7–99.97%) خلف منشورٍ تغطيتُه 45–86%: تمريرةُ
    #    البسملة لا تقصّ (‏امتناعٌ صواب)، و`realign_surah` على المنشور يُخرج
    #    مختلطَ الجيل فيُردّ، والبصمةُ الجيّدة لا تُرقّى لبسملةٍ واحدة. فكلُّ
    #    بابٍ مغلقٌ بحارسٍ محقّ. ⇒ يُفتح بابٌ **بالحُرّاس نفسِها كلِّها**، لا
    #    بتجاوزٍ ولا بنشرِ عيبٍ ولو ساعات (‏الموثوقيةُ فوق العدد، أمر المالك).
    if a.parent.startswith("timings-staging/"):
        # والحارسُ هنا: الرواية والمعرّف يُستخرجان من المفتاح ويُطابَقان
        # بترويسة المنتَج — فلا يُرقّع فهرسُ قارئٍ بمخرَجِ قارئٍ آخر.
        parts = a.parent.split("/")
        if len(parts) != 3:
            raise SystemExit(f"⛔ مفتاحُ اختبارٍ غيرُ سويّ: {a.parent}")
        p_riw, p_rid = parts[1], parts[2].split(".")[0]
        if idx.get("riwaya") != p_riw or idx.get("reciterId") != p_rid:
            raise SystemExit(f"⛔ المنتَج يصف {idx.get('riwaya')}/{idx.get('reciterId')} "
                             f"والأصلُ {p_riw}/{p_rid} — لا يُرقّع قارئٌ بمخرَجِ آخر")
    elif not a.parent.startswith("timings/"):
        raise SystemExit(f"⛔ الأصلُ ليس منشوراً ولا في الاختبار: {a.parent}")
    pbody = cl.get_object(Bucket=bucket, Key=a.parent)["Body"].read()
    psha = hashlib.sha256(pbody).hexdigest()
    if not psha.startswith(a.parent_sha.rstrip(".")):
        raise SystemExit(f"⛔ الأصل بصمتُه {psha[:16]} لا {a.parent_sha}")
    pidx = json.loads(gzip.decompress(pbody).decode("utf-8"))

    n_new, n_old = len(idx.get("entries") or []), len(pidx.get("entries") or [])
    # ⛔ **استثناءُ `realign_surah` وحدَه (‏قرار المشرف github-10، 2026-09-05):**
    #    القاعدةُ «التحويلُ يزيح حدوداً ولا يحذف آيات» بُنيت لتحويلاتٍ تُعدّل
    #    الحدود (‏`basmala_fix`)، و**إعادةُ محاذاة سورةٍ تُعيد مداخلَ غائبة** —
    #    فاختلافُ العدد فيها **هو المقصود** لا علامةُ خللٍ خفيّ.
    #    ⛔ ولا يُرفع الحارسُ بل **يُشدَّد**: بدل «تساوٍ» يُشترط أن يكون الفرقُ
    #    **مطابقاً حسابياً** لعدد آي السور المسمّاة في `--op`، وألّا يمسّ
    #    التحويلُ مدخلاً خارجها. فمن أعاد سورةً وحذف أخرى صامتاً يُردّ هنا.
    #    و`source_timing_splice:<سور>` يدخل البابَ نفسَه **بالحُرّاس نفسِها
    #    كلِّها**: هو أيضاً يُعيد اشتقاقَ حدود سورةٍ بعينها فيُعيد مداخلَ غائبة
    #    (‏koshi_warsh/37: 181 ⇐ 182)، والفرقُ في **مصدر الحدود** لا في أثرها.
    #    ⛔ ولا يُسمَّى «إعادةَ محاذاة» تجوّزاً: الترويسةُ سجلُّ نسبٍ يُقرأ منه
    #    جيلُ الفهرس، فاسمٌ كاذبٌ فيها أسوأ من غيابه (‏درسُ «مجهولِ الجيل»).
    realigned = []
    # أسماء الدمج من سجل الحارس نفسه؛ لا اسم جديد في موضع يغيب عن الآخر.
    splice_names = "|".join(re.escape(n) for n in sorted(promote.SPLICE_OPS))
    _m = re.match(rf"^(?:realign_surah|source_timing_splice|{splice_names}):([\d,\s]+)$", a.op.strip())
    if _m:
        realigned = sorted({int(x) for x in re.findall(r"\d+", _m.group(1))})
    # ⛔ **دمجُ محرّكين لا يُرفع إلا معلَناً سورةً سورة** (‏إذن المالك 2026-09-24):
    #    ‏`ctc_surah_splice` يجب أن يحمل `engineBySurah` يسمّي **كلَّ** سورةٍ في
    #    التحويل بمحرّكٍ غير محرّك الفهرس، **ولا سورةً سواها** إلا ما ورثه
    #    الأصلُ نفسُه — فحارسُ الترقية يطلب إحصاءً شاملاً لما في هذا السجلّ،
    #    وسجلٌّ ناقصٌ كان يُعفي سورةً من السماع.
    #    و`whisper_surah_splice` (‏سورُ Whisper في فهرس CTC) بالحُرّاس نفسِها حرفاً،
    #    ⛔ **ويُشدَّد الاثنان**: السورةُ المسمّاةُ يجب أن تُعلَن **بمحرّك تحويلها
    #    بعينه** (‏`promote.SPLICE_OPS`) — فدمجُ Whisper معلَناً بـCTC أو العكسُ
    #    كذبٌ في سجلّ النسب يُردّ، ولا يكفي أنّه «غيرُ محرّك الفهرس».
    ebs = idx.get("engineBySurah") or {}
    sys.path.insert(0, str(HERE.parent / 'alignment_v3'))
    from quran_ctc_model import records_error
    model_error = records_error(idx)
    if model_error:
        raise SystemExit('⛔ ' + model_error)
    p_ebs = pidx.get("engineBySurah") or {}
    # ⛔ **والمصدرُ البديلُ يُعلَن سورةً سورة** (‏2026-09-28): دمجُ سورةٍ من تسجيلٍ
    #    آخر للقارئ نفسِه (‏`source_overrides.json`) في فهرسٍ بالمحرّك نفسِه لا يُكتب
    #    في `engineBySurah` — فلا يمرّ إلا مُعلَناً في `sourceBySurah` بقالبه، وكلُّ
    #    مدخلٍ في السورة يُشير إلى ذلك القالب بعينه، والصوتُ غيرُ صوت الأصل فعلاً.
    #    وهذا بابٌ **أضيق** لا أوسع: يُضاف إلى إعلان المحرّك ولا يُعفي منه، والسورةُ
    #    المعلَنةُ مصدراً تدخل الإحصاءَ الشامل (‏`promote.census_surahs`).
    sbs = idx.get("sourceBySurah") or {}
    p_sbs = pidx.get("sourceBySurah") or {}
    if not isinstance(sbs, dict) or not all(isinstance(v, str) and v for v in sbs.values()):
        raise SystemExit("⛔ `sourceBySurah` غيرُ سويّ — يجب قاموساً من سورةٍ إلى قالبِ رابط")
    _splice = promote.splice_op_name(a.op)
    if _splice:
        named = {str(s) for s in realigned}
        want_eng = promote.SPLICE_OPS[_splice]
        tagged = {k for k, v in ebs.items() if v and v != idx.get("engineVersion")}
        # ‏الإعلانُ بالمصدر لا يقوم مقامَ المحرّك إلا حين يكون محرّكُ التحويل هو
        #    محرّكَ الفهرس نفسَه (‏فلا يُكتب في `engineBySurah` أصلاً) ولم يتغيّر.
        same_eng = (idx.get("engineVersion") == want_eng
                    and pidx.get("engineVersion") == want_eng)
        by_src = (named & set(sbs)) if same_eng else set()
        if not named or not named <= (tagged | by_src):
            raise SystemExit(f"⛔ دمجُ محرّكين بلا إعلانٍ لكلّ سورة: المسمّاة "
                             f"{sorted(named, key=int)} والمعلَنة {sorted(tagged, key=int)}"
                             f" والمعلَنةُ مصدراً بديلاً {sorted(by_src, key=int)}")
        wrong = sorted((k for k in named & tagged if ebs.get(k) != want_eng), key=int)
        if wrong:
            raise SystemExit(f"⛔ {_splice} يُعلن سورَه بـ{want_eng}، والسور "
                             f"{wrong} معلَنةٌ بغيره: "
                             f"{sorted({ebs.get(k) for k in wrong})}")
        extra = tagged - named - set(p_ebs)
        if extra:
            raise SystemExit(f"⛔ سورٌ معلَنةٌ بمحرّكٍ آخر لم يمسّها التحويل ولا "
                             f"ورثها الأصل: {sorted(extra, key=int)}")
    elif set(ebs) - set(p_ebs):
        raise SystemExit("⛔ سجلُّ المحرّكات زاد سوراً في تحويلٍ لا يدمج محرّكين — يُردّ")
    named_src = {str(s) for s in realigned} if _splice else set()
    extra_src = set(sbs) - named_src - set(p_sbs)
    if extra_src:
        raise SystemExit(f"⛔ سورٌ معلَنةٌ بمصدرٍ بديلٍ لم يمسّها التحويل ولا ورثها "
                         f"الأصل: {sorted(extra_src, key=int)}")
    moved_src = sorted((k for k in set(sbs) - named_src if sbs[k] != p_sbs.get(k)), key=int)
    if moved_src:
        raise SystemExit(f"⛔ مصدرُ سورٍ لم يمسّها التحويل تبدّل في الترويسة: {moved_src}")
    # ‏ولا يُمحى إعلانٌ موروثٌ ما دامت مداخلُ سورته تُشير إلى المصدر البديل نفسِه —
    #    وإلا خرجت من الإحصاء بمحوِ سطرٍ في الترويسة.
    for k in sorted(set(p_sbs) - set(sbs), key=int):
        try:
            pref = str(p_sbs[k]).format(s=int(k))
        except Exception:                                      # noqa: BLE001
            pref = None
        if pref and any(e.get("fileRef") == pref for e in (idx.get("entries") or [])
                        if int(e["ayahId"].split(":")[0]) == int(k)):
            raise SystemExit(f"⛔ إعلانُ المصدر البديل لـس{k} مُحي ومداخلُها ما زالت "
                             f"تُشير إليه ({pref}) — يُردّ")
    for k in sorted(set(sbs) & named_src, key=int):
        try:
            ref = sbs[k].format(s=int(k))
        except Exception as e:                                 # noqa: BLE001
            raise SystemExit(f"⛔ قالبُ المصدر البديل لـس{k} لا يُنسَّق: {e}")
        refs = {e.get("fileRef") for e in (idx.get("entries") or [])
                if int(e["ayahId"].split(":")[0]) == int(k)}
        if refs != {ref}:
            raise SystemExit(f"⛔ س{k} معلَنةٌ من {ref} ومداخلُها تُشير إلى "
                             f"{sorted(map(str, refs))[:3]} — الإعلانُ يخالف الفهرس")
        old_refs = {e.get("fileRef") for e in (pidx.get("entries") or [])
                    if int(e["ayahId"].split(":")[0]) == int(k)}
        if ref in old_refs and p_sbs.get(k) != sbs[k]:
            raise SystemExit(f"⛔ س{k} معلَنةٌ مصدراً بديلاً وصوتُها هو صوتُ الأصل "
                             f"({ref}) — لا تغيّرَ يُعلَن")
    if realigned:
        have_old = {e["ayahId"] for e in (pidx.get("entries") or [])}
        have_new = {e["ayahId"] for e in (idx.get("entries") or [])}
        outside_old = {i for i in have_old if int(i.split(":")[0]) not in realigned}
        outside_new = {i for i in have_new if int(i.split(":")[0]) not in realigned}
        if outside_old != outside_new:
            raise SystemExit("⛔ التحويل مسّ مداخلَ خارج السور المسمّاة — يُردّ")
        if tails:
            if not _splice:
                raise SystemExit("⛔ --owner-truncated-tail لتحويل دمجٍ مسمّىً (promote.SPLICE_OPS) وحده")
            bad = (truncated_tail_error(have_old, have_new, realigned, tails)
                   or truncated_header_error(idx, tails))
        else:
            bad = realigned_coverage_error(have_old, have_new, realigned,
                                           allow_inherited=a.allow_inherited_gaps)
        if bad:
            raise SystemExit(bad)
        if tails:
            print("  ✔ ذيلٌ مبتورٌ معلَن (أمر المالك 2026-10-02): " + " · ".join(
                f"س{s} بادئة 1..{n} والغائب {n + 1}..{AYAH_COUNTS[s - 1]} source_truncated"
                for s, n in sorted(tails.items())))
        print(f"  ✔ إعادةُ محاذاة {realigned}: {n_old} ⇐ {n_new} مدخلاً "
              f"(‏+{n_new - n_old})، وما خارجها لم يُمسّ")
    elif tails:
        raise SystemExit("⛔ --owner-truncated-tail بلا سورٍ مُعادةٍ في --op — لا معنى له")
    elif n_new != n_old:
        raise SystemExit(f"⛔ المداخل {n_new} ≠ الأصل {n_old} — التحويل يزيح "
                         "حدوداً ولا يحذف آيات")
    e_new, e_old = entries_sha(idx.get("entries") or []), entries_sha(
        pidx.get("entries") or [])
    if e_new == e_old:
        # ⛔⛔ **بابُ التصحيح الترويسيّ — ضيّقٌ ومُسمّى** (‏فُتح 2026-09-11):
        #    فهرسُ `h_saleh` **عطبُه 0.36%** وبقي محبوساً لأنّ ترويسته تقول
        #    `ayahCounting: "hafs"` — وحفصٌ **روايةٌ لا نظامَ عدّ**. وقِيس عدُّ
        #    السور الـ114 كلِّها فطابق الكوفيَّ (6236). وإعادةُ المحاذاة لم
        #    تُصلحه بل أنتجت **5791 مدخلاً** فردّها حارسُ الرفع بحقّ.
        #    ⇒ يُفتح بابٌ للترويسة وحدَها: **المداخلُ متطابقةٌ بايتاً** (شرطُ
        #    الدخول نفسُه)، والمتغيّرُ حقولٌ وصفيّةٌ تُسمّى في السبب. وبغير
        #    هذا العَلَم يبقى الردُّ كما كان — فلا يمرّ لا-تحويلٍ صامت.
        if not getattr(a, "metadata_only", None):
            raise SystemExit("⛔ المداخل لم تتغيّر — لا إصلاح هنا "
                             "(وإن كان تصحيحاً ترويسيّاً فسمِّه بـ"
                             "`--metadata-only <السبب>`)")
        changed = sorted(k for k in set(idx) | set(pidx)
                         if k not in ("entries", "transform", "generatedAt")
                         and idx.get(k) != pidx.get(k))
        if not changed:
            raise SystemExit("⛔ لا مداخلَ تغيّرت ولا ترويسة — لا شيء هنا")
        print(f"  ✔ تصحيحٌ ترويسيّ بلا مسِّ مدخلٍ واحد: {changed}")
    for check, name in ((promote.index_gate(idx), "البنية"),
                        (promote.catalog_gate(idx, promote.catalog(cl, bucket)),
                         "الهويّة")):
        if check:
            raise SystemExit(f"⛔ حارس {name}: {check}")

    moved, added, removed = entry_change_counts(pidx["entries"], idx["entries"])
    out = dict(idx)
    # ‏**`transform` قد يصل نصّاً** (كتبه github-8e سلسلةً) — يُحفظ نصُّه في
    # `opAsGiven` ولا يُطمس، ويُبنى القاموس فوقه.
    prior = idx.get("transform")
    base = dict(prior) if isinstance(prior, dict) else (
        {"opAsGiven": prior} if prior else {})
    out["transform"] = dict(base, **{
        "op": a.op, "fromSha256": psha, "fromKey": a.parent,
        "entriesSha256": e_new, "parentEntriesSha256": e_old,
        "movedEntries": moved, "addedEntries": added, "removedEntries": removed,
        "reason": a.reason, "by": a.by,
        "at": int(time.time() * 1000),
        "note": ("‏عددُ المداخل مطابقٌ للأصل والحدودُ وحدها أُزيحت؛ ولا يُرقّى "
                 "بحكم الأصل: يدخل الطابور بفحص مطالعَ وعيّنةٍ على بصمته."),
    })
    # سياسة الجدولة تخص التحويل الحالي، ولا تورث حجزاً إلى تحويل لاحق تلقائياً.
    apply_dispatch_policy(out, a.manual_qa_only, a.parent, psha)
    packed = gzip.compress(json.dumps(out, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8"), 9)
    new = hashlib.sha256(packed).hexdigest()
    target = (f"timings-staging/{idx.get('riwaya')}/"
              f"{idx.get('reciterId')}.{new[:8]}.jz")
    print(f"الأصل {a.parent} ({psha[:12]}) · المنتَج {Path(a.file).name} "
          f"({sha[:12]})")
    print(f"المداخل {n_old} ⇒ {n_new} ✅ · بصمةُ المداخل {e_old[:10]} ⇒ "
          f"{e_new[:10]} (مختلفة ✅) · حدودٌ أُزيحت {moved}")
    print(f"إلى {target} ({len(packed)} بايت · بصمة {new[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    # ⛔ ميتاداتا S3 لا تقبل إلا ASCII (`validate_ascii_metadata` في botocore)،
    #    و`--by` يُكتب بالعربية طبعاً — فكان النداءُ **يسقط بعد كلّ الحُرّاس**
    #    وبعد بناء الحزمة، فيضيع العملُ كلُّه على حرفٍ في حقلٍ وصفيّ. وقع مقيساً
    #    2026-09-08 (`ParamValidationError` على «جندي الفهرسة»).
    #    ⇒ يُطوى للميتاداتا وحدَها، **والأصلُ يبقى كما هو في ترويسة الفهرس**
    #    (`transform.by` أعلاه) — فلا تُفقد النسبةُ ولا يسقط الرفع.
    put_meta = {"source": "transform-local", "transform": a.op,
                "parent": psha[:8], "sha256-8": new[:8],
                "by": ascii_meta(a.by), "premeta": sha[:8]}
    cl.put_object(Bucket=bucket, Key=target, Body=packed,
                  ContentType="application/gzip", Metadata=put_meta)
    head = cl.head_object(Bucket=bucket, Key=target)
    print(f"↑ رُفع · الدلو {head['ContentLength']} · المحلّي {len(packed)} → "
          f"{'✅' if head['ContentLength'] == len(packed) else '❌'}")


if __name__ == "__main__":
    main()
