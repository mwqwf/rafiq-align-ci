#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تدقيق فهارس التوقيتات **الكلمية** (`wordtimings/{riwaya}/{id}.jz`).

    python tools/index_qa/words.py qalun/husary_qalun
    python tools/index_qa/words.py qalun/husary_qalun --struct-only
    python tools/index_qa/words.py qalun/husary_qalun --ayat 20 --per-ayah 6

⛔ **ما لا تحكم عليه هذه الأداة — يُقرأ قبل نتيجتها لا بعدها:**

1. **لا تصدّق ولا تكذّب ادّعاء «وسيط خطأ البداية 180م.ث».** أداتنا لا تفصل ما
   دون ~0.3ث، وتقيس **وجود الأثر لا مقداره**. فحكم «سليم» هنا لا يشهد لدقّةٍ
   بالمللي، والادّعاء الكمّي يبقى مسنوداً بقياس صاحبه وحده.
2. **لا تحكم على النهايات إطلاقاً.** ‏`endsPolicy="contiguous"` يجعل نهاية كل
   كلمة = بداية التالية **بالسياسة لا بالقياس**، فمقابلتها بالصوت مقابلةٌ
   لسياسةٍ لا لقياس. (وهو نفس درس §هـ في QA_BOUNDARIES: نهايةٌ مشتقّة من
   الجار لا تصلح حارساً.)
3. **تحكم على صنفٍ واحد: الخطأ الجسيم في البداية** — أن يقع `startMs` لكلمةٍ
   على كلمةٍ أخرى. فمن يتتبّع الكلمة المضيئة لا يضيره 180م.ث، ويضيره أن تضيء
   الكلمة الخطأ.
4. **الكلمة المفردة (~0.3–0.7ث) يتشوّش تفريغها**، ولذلك النافذة 2.5ث والحكم
   على **مطلعها**؛ وتوقَّع «غير حاسم» أكثر مما في حدود الآي.

والقاعدة الحاكمة كما في حدود الآي: **لا بلاغ إلا بشاهدٍ نصّي، ولا شاهد إلا
بتمريرين** — أمامي يجب أن يبدأ بالكلمة، وحاسمٌ ينتهي عندها ويجب ألّا يحويها.
"""
from __future__ import annotations
import argparse, difflib, gzip, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run import (ASSETS, COUNTS, flat, s3, skel, cluster_ci, remote_run,   # noqa: E402
                 push_worker, _match_from, RASM_TOL, QA_HOST, STATE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

FWD_MS, DEC_MS = 2500, 2500

def fetch_raw(key):
    cl, b = s3()
    return cl.get_object(Bucket=b, Key=key)["Body"].read()

def presign(key, secs=3600):
    cl, b = s3()
    return cl.generate_presigned_url("get_object", Params={"Bucket": b, "Key": key}, ExpiresIn=secs)

# ───────────────────────── الفحص البنيوي ─────────────────────────
def structural(wt, txt, bounds):
    """`bounds`: مداخل الفهرس الحدّي مفهرسةً بـayahId (أو None لتخطّي فحص الحصر)."""
    fatal, warn, info = [], [], {}
    E = wt.get("entries", [])
    info["ayat"] = len(E)
    info["words"] = sum(len(e.get("words", [])) for e in E)
    info["engine"] = wt.get("engineVersion")
    info["indexing"] = wt.get("indexing")
    info["endsPolicy"] = wt.get("endsPolicy")

    if wt.get("indexing") != "RAW_TOKENS":
        warn.append(f"indexing = {wt.get('indexing')!r} — فحص عدد الكلمات مبنيٌّ على RAW_TOKENS")

    # ١) عدد الكلمات = عدد الرموز الخام في نص الرواية (ادّعاء RAW_TOKENS)
    bad_count, ex = 0, ""
    for e in E:
        s, a = map(int, e["ayahId"].split(":"))
        want = len(txt[flat(s, a)].split())
        got = len(e.get("words", []))
        if want != got:
            bad_count += 1
            ex = ex or f"{e['ayahId']}: {got} كلمة والنص {want}"
    if bad_count:
        fatal.append(f"عدد الكلمات ≠ الرموز الخام في {bad_count} آية · مثال: {ex}")

    # ٢) الرتابة، والنهايات الملصوقة كما تقتضي السياسة، وصفر مدّةٍ عدمية
    mono = zero = gap = silent = 0
    ex_m = ex_z = ""
    for e in E:
        ws = e.get("words", [])
        s, an = map(int, e["ayahId"].split(":"))
        toks = txt[flat(s, an)].split()
        for i, w in enumerate(ws):
            st, en = w.get("startMs"), w.get("endMs")
            # ⛔ الرمز الصامت («۞» علامة الربع مثلاً) **رمزٌ خام لا كلمة منطوقة**،
            # فمدّته الصفرية هي الصواب لا العطب. اكتُشف ذلك بعد أن أبلغت أداتي
            # عن «45 كلمة بمدّة صفرية» وكانت خمساً وأربعين علامةَ ربع.
            # والقاعدة عامة: رمزٌ هيكله خالٍ من الحروف = لا صوت له.
            if i < len(toks) and not skel(toks[i]):
                silent += 1
                continue
            if st is None or en is None or en < st:
                zero += 1
                ex_z = ex_z or f"{w.get('wordId')}: {st}→{en}"
                continue
            if en == st:
                zero += 1
                ex_z = ex_z or f"{w.get('wordId')}: مدّة صفرية"
            if i and st < ws[i-1]["startMs"]:
                mono += 1
                ex_m = ex_m or f"{w.get('wordId')} يبدأ قبل سابقته"
            if i and ws[i-1].get("endMs") != st:
                gap += 1
    info["silentTokens"] = silent
    if zero:
        fatal.append(f"كلمات بمدّة غير صالحة أو صفرية: {zero} · مثال: {ex_z}")
    if mono:
        fatal.append(f"خرق الرتابة داخل الآية: {mono} · مثال: {ex_m}")
    if gap:
        warn.append(f"نهاياتٌ لا تلاصق بداية التالية: {gap} — يخالف endsPolicy=contiguous المعلَن")

    # ٣) انحصار مدى كلمات الآية داخل حدّ الآية في الفهرس الحدّي
    if bounds:
        out, ex_o, missing = 0, "", 0
        for e in E:
            b = bounds.get(e["ayahId"])
            if not b:
                missing += 1
                continue
            ws = e.get("words", [])
            if not ws:
                continue
            if ws[0]["startMs"] < b["startMs"] - 50 or ws[-1]["endMs"] > b["endMs"] + 50:
                out += 1
                ex_o = ex_o or (f"{e['ayahId']}: الكلمات {ws[0]['startMs']}→{ws[-1]['endMs']} "
                                f"والآية {b['startMs']}→{b['endMs']}")
        if out:
            fatal.append(f"آيات كلماتها خارج حدّ الآية: {out} · مثال: {ex_o}")
        if missing:
            fatal.append(f"آيات لا مدخل لها في الفهرس الحدّي المرجعي: {missing}")

        # ٤) ادّعاء «لا تُكتب آية إلا HIGH»
        non_high = [e["ayahId"] for e in E
                    if bounds.get(e["ayahId"], {}).get("confBand") != "HIGH"]
        info["nonHigh"] = len(non_high)
        if non_high:
            fatal.append(f"آيات ليست HIGH في الفهرس الحدّي: {len(non_high)} · مثال: {non_high[:5]}")
    return fatal, warn, info

# ───────────────────────── العيّنة والحكم ─────────────────────────
def sample_words(wt, n_ayat, per_ayah):
    """بذرة مشتقّة من مفتاح الملف — ثابتة، وتُختار قبل أي سماع."""
    import random
    seed_hex = hashlib.sha256(f"wordtimings/{wt['riwaya']}/{wt['reciterId']}".encode()).hexdigest()
    rng = random.Random(int(seed_hex[:16], 16))
    pool = [e for e in wt["entries"] if len(e.get("words", [])) >= per_ayah]
    out = []
    for e in rng.sample(pool, min(n_ayat, len(pool))):
        for w in rng.sample(e["words"], per_ayah):
            out.append((e["ayahId"], w))
    return seed_hex, out

def judge_word(word_text, prev_text, fwd, dec):
    """الحكم على **بداية** الكلمة وحدها. جسيم = البداية على كلمةٍ أخرى."""
    wsk = skel(word_text)
    if len(wsk) < 3:
        return "غير حاسم", "غير حاسم", f"الكلمة «{word_text}» أقصر من أن يُحكم عليها بالتفريغ"
    h = skel(fwd or "")
    if not h:
        return "غير حاسم", "غير حاسم", "تفريغ التمرير الأول فارغ"

    # ⛔ العتبة تُقاس بطول **الكلمة** لا بطول التفريغ. استعمالُ عتبة الحدود هنا
    # جعل كل كلمةٍ من ثلاثة أحرف («ربك» · «كان» · «انه») **يستحيل** أن تُطابَق،
    # فطُبع «غير حاسم» على مطالع سليمةٍ بيّنة: «رَبِّكَ» سُمعت «رَبِّكَ وَاسْتَغْفِرْ».
    # والعربية القرآنية مليئةٌ بالكلمات القصار، فالعطب كان يبتلع نصف العيّنة.
    lead = h[:len(wsk) + 12]
    sm = difflib.SequenceMatcher(None, wsk, lead, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= min(3, len(wsk))]
    if blocks and sum(b.size for b in blocks) >= max(3, len(wsk) - 1) and blocks[0].b <= RASM_TOL:
        return "بريء", "بريء", f"النافذة تبدأ بالكلمة: «{(fwd or '')[:40]}»"

    # التمرير الثاني الحاسم: ظهور الكلمة **قبل** الحدّ = بدايةٌ متأخرة يقيناً
    d = skel(dec or "")
    late = bool(d and len(wsk) >= 4 and wsk in d[-(len(wsk) + 8):])
    if late:
        return "LATE_WORD", "جسيم", (f"«{word_text}» تُسمع **قبل** الحدّ (النافذة الحاسمة: "
                                     f"«{(dec or '')[-40:]}») والنافذة الأمامية تبدأ «{(fwd or '')[:35]}»")
    # هل بدأت النافذة بكلمةٍ سابقةٍ صريحة؟
    psk = skel(prev_text or "")
    if psk and len(psk) >= 4:
        pm = difflib.SequenceMatcher(None, psk, h[:len(psk) + 6], autojunk=False).find_longest_match(
            0, len(psk), 0, min(len(psk) + 6, len(h)))
        if pm.size >= max(4, len(psk) - 1) and pm.b <= RASM_TOL:
            return "EARLY_WORD", "جسيم", (f"النافذة تبدأ بالكلمة **السابقة** «{prev_text}»: "
                                          f"«{(fwd or '')[:40]}» — والمقصودة «{word_text}»")
    return "غير حاسم", "غير حاسم", f"لا يبدأ التفريغ بالكلمة ولا بسابقتها · سُمع: «{(fwd or '')[:45]}»"

# ───────────────────────── main ─────────────────────────
def main():
    ap = argparse.ArgumentParser(description="تدقيق التوقيتات الكلمية")
    ap.add_argument("key", help="qalun/husary_qalun")
    ap.add_argument("--struct-only", action="store_true")
    ap.add_argument("--ayat", type=int, default=20)
    ap.add_argument("--per-ayah", type=int, default=6)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--host", default=QA_HOST)
    a = ap.parse_args()

    wkey = f"wordtimings/{a.key}.jz"
    raw = fetch_raw(wkey)
    wt = json.loads(gzip.decompress(raw).decode("utf-8"))
    riwaya, rid = wt["riwaya"], wt["reciterId"]
    print(f"\n{'═'*78}\n■ {wkey}  ({rid} · {riwaya})")
    print(f"  sha256 = {hashlib.sha256(raw).hexdigest()}")

    txt = json.loads(gzip.decompress((ASSETS / f"text_{riwaya}.jz").read_bytes()).decode("utf-8"))

    # الفهرس الحدّي المرجعي — ويُتحقّق أن بصمته هي المذكورة في generatedAgainst
    bounds, ga = None, wt.get("generatedAgainst") or {}
    try:
        braw = fetch_raw(f"timings/{a.key}.jz")
        bsha = hashlib.sha256(braw).hexdigest()
        bidx = json.loads(gzip.decompress(braw).decode("utf-8"))
        bounds = {e["ayahId"]: e for e in bidx["entries"]}
        ok = "✅ مطابقة" if bsha == ga.get("sha256") else "🔴 **غير مطابقة**"
        print(f"  الفهرس الحدّي المرجعي: {ok} (generatedAgainst = {str(ga.get('sha256'))[:16]}…)")
        if bsha != ga.get("sha256"):
            print("     ⇒ الكلمات بُنيت على فهرسٍ غير المنشور الآن — أي حكمٍ عليها لا ينتقل إليه.")
    except Exception as ex:
        print(f"  ⚠️ تعذّر جلب الفهرس الحدّي: {ex} — فحص الحصر وHIGH متخطّى")

    fatal, warn, info = structural(wt, txt, bounds)
    print(f"  بنيوي: آيات {info['ayat']} · كلمات {info['words']} · محرك {info['engine']} · "
          f"indexing={info['indexing']} · endsPolicy={info['endsPolicy']}")
    for x in fatal:
        print(f"  🔴 خلل بنيوي: {x}")
    for x in warn:
        print(f"  ⚠️  مرشّح (لا حكم): {x}")
    if not fatal:
        print("  ✅ بنيوياً سليم")

    if a.struct_only:
        print("\n  ⇒ الحكم: بنيوي فقط — بلا عيّنة صوتية")
        return

    seed, sample = sample_words(wt, a.ayat, a.per_ayah)
    print(f"\n  عيّنة عمياء: بذرة {seed[:16]}… · {len(sample)} كلمة "
          f"({a.ayat} آية × {a.per_ayah}) · تمريران لكل كلمة")

    byid = {e["ayahId"]: e for e in wt["entries"]}
    jobs, meta = [], {}
    for aid, w in sample:
        s, an = map(int, aid.split(":"))
        toks = txt[flat(s, an)].split()
        j = w["subIndex"]
        prev = toks[j - 1] if j > 0 else ""
        url = presign(f"audio/{riwaya}/{rid}/{s:03d}.mp3")
        wid = w["wordId"]
        meta[wid] = {"aid": aid, "word": toks[j] if j < len(toks) else "?", "prev": prev}
        st = w["startMs"]
        jobs += [{"id": f"F|{wid}", "url": url, "startMs": st, "endMs": st + FWD_MS},
                 {"id": f"D|{wid}", "url": url, "startMs": max(0, st - DEC_MS), "endMs": st}]

    push_worker(a.host)
    res, errs = {}, {}
    for i in range(0, len(jobs), a.batch):
        r, er = remote_run(jobs[i:i + a.batch], a.host, a.threads)
        res.update(r)
        errs.update(er)
        print(f"    …تفريغ {min(i + a.batch, len(jobs))}/{len(jobs)} نافذة", flush=True)

    rows, by_ayah = [], {}
    for wid, mt in meta.items():
        g = lambda p: (res.get(f"{p}|{wid}") or {}).get("text", "")
        v, kind, why = judge_word(mt["word"], mt["prev"], g("F"), g("D"))
        rows.append({"wordId": wid, "kind": kind, "verdict": v, "why": why, "word": mt["word"],
                     "prev": mt["prev"], "heard": {"fwd": g("F"), "dec": g("D")}})
        by_ayah.setdefault(mt["aid"], []).append(kind)

    order = {"جسيم": 0, "غير حاسم": 1, "بريء": 2}
    for r in sorted(rows, key=lambda r: (order.get(r["kind"], 9), r["wordId"])):
        mark = {"جسيم": "🔴", "بريء": "✅"}.get(r["kind"], "⚪")
        print(f"  {mark} {r['wordId']:>12} «{r['word']:<12}» {r['verdict']:>12}  {r['why'][:80]}")

    n = sum(len(v) for v in by_ayah.values())
    hit = sum(1 for v in by_ayah.values() for k in v if k == "جسيم")
    unc = sum(1 for v in by_ayah.values() for k in v if k == "غير حاسم")
    ci = cluster_ci([sum(1 for k in v if k == "جسيم") / len(v) for v in by_ayah.values() if v])
    c = f" · مجال 95% عنقودي: {ci[1]:.1%} – {ci[2]:.1%}" if ci else ""
    print(f"\n  📐 الخطأ الجسيم في البداية: {hit}/{n} = {hit/max(n,1):.1%}{c}")
    print(f"  ⚪ غير حاسم: {unc}/{n} = {unc/max(n,1):.1%} (لا يُحتسب عطباً)")
    if errs:
        print(f"  ⚠️ نوافذ تعذّر تفريغها: {len(errs)}")
    print(f"\n  ⇒ الحكم: {'مرفوض' if (fatal or hit / max(n,1) > 0.05) else 'مقبول'}"
          f"{' (خلل بنيوي)' if fatal else ''}")
    print("⚠️ حدوده: لا تُصدّق ولا تُكذّب «180م.ث» (لا نفصل ما دون ~0.3ث)؛ ولا حكم على\n"
          "   النهايات (ملصوقة بالسياسة)؛ والحكم على صنفٍ واحد: البداية على كلمةٍ أخرى.")

    (STATE / f"words_{a.key.replace('/', '_')}.json").write_text(
        json.dumps({"key": wkey, "sha256": hashlib.sha256(raw).hexdigest(), "seed": seed,
                    "fatal": fatal, "warn": warn, "info": info, "rows": rows},
                   ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()
