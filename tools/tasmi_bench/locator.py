# -*- coding: utf-8 -*-
"""مرآة `engine/recitation/.../QuranLocator.kt` بالبايثون — نسخة القياس (2026-09-06).

⚠️ كالحاكم: هذا الملف صورةُ المحدّد لا تقريبٌ له. كل تغييرٍ في الكوتلن يُعكس هنا
وإلا فالرقم عن شيءٍ آخر. `LEGACY` = المشحون قبل 2026-09-06، `CURRENT` = بعده.
"""
import re
from collections import defaultdict

import scorer

_WS = re.compile(r"\s+")


def grams(words, cfg, n=3):
    ws = [w for w in (scorer.norm(x, cfg) for x in words) if w]
    return [" ".join(ws[i:i + n]) for i in range(len(ws) - n + 1)]


class Locator:
    def __init__(self, ayah_words, cfg, mode="current"):
        self.ayah_words = ayah_words
        self.cfg = cfg
        self.mode = mode
        self.index3 = defaultdict(list)
        self.index2 = defaultdict(list)
        self.index1 = defaultdict(list)
        def add(ix, g, flat):
            lst = ix[g]
            if not lst or lst[-1] != flat:
                lst.append(flat)
        for flat, ws in enumerate(ayah_words):
            for g in grams(ws, cfg, 3):
                add(self.index3, g, flat)
            if mode != "legacy":
                for g in grams(ws, cfg, 2):
                    add(self.index2, g, flat)
                for g in grams(ws, cfg, 1):
                    add(self.index1, g, flat)
        self.total_words = sum(len(w) for w in ayah_words)

    # ----- المشحون سابقاً (legacy) -----
    def best_start_legacy(self, hyp):
        head = hyp[:12]
        votes = defaultdict(float)
        for i in range(len(head) - 2):
            g = " ".join(head[i:i + 3])
            flats = self.index3.get(g)
            if not flats:
                continue
            w = (1.0 / len(flats)) * (3.0 if i == 0 else 2.0 if i < 3 else 1.0)
            for f in flats:
                votes[f] += w
        if not votes:
            return None
        best = max(votes.items(), key=lambda kv: kv[1] + votes.get(kv[0] + 1, 0.0) * 0.5)
        return best[0] if best[1] >= 0.05 else None

    # ----- الجديد (current) -----
    RARE_BIGRAM = 12   # ثنائيّة تشهد إن وردت في ≤12 آية
    RARE_WORD = 4      # كلمةٌ وحدها تشهد إن وردت في ≤4 آيات (نادرة فعلاً)

    def candidates(self, hyp, top=8):
        """ترشيحٌ بالتصويت على **كل** التفريغ لا أوّله: ثلاثيّات (idf لوغاريتمي)، وثنائيّات نادرة،
        وكلماتٌ مفردة نادرة جدّاً — فالنادر يشهد أقوى (أمر المالك: «حتى لو لم أذكر إلا كلمات نادرة»)."""
        import math
        votes = defaultdict(float)
        first = {}
        n3 = max(1, len(self.index3))
        for i in range(len(hyp) - 2):
            flats = self.index3.get(" ".join(hyp[i:i + 3]))
            if not flats:
                continue
            w = math.log(1 + n3 / len(flats))
            for f in flats:
                votes[f] += w
                first.setdefault(f, i)
        n2 = max(1, len(self.index2))
        for i in range(len(hyp) - 1):
            flats = self.index2.get(" ".join(hyp[i:i + 2]))
            if not flats or len(flats) > self.RARE_BIGRAM:
                continue
            w = 0.6 * math.log(1 + n2 / len(flats))
            for f in flats:
                votes[f] += w
                first.setdefault(f, i)
        n1 = max(1, len(self.index1))
        for i, wd in enumerate(hyp):
            flats = self.index1.get(wd)
            if not flats or len(flats) > self.RARE_WORD or len(wd) < 4:
                continue
            w = 0.4 * math.log(1 + n1 / len(flats))
            for f in flats:
                votes[f] += w
                first.setdefault(f, i)
        if not votes:
            return []
        scored = [(f, v + votes.get(f + 1, 0.0) * 0.5, first[f]) for f, v in votes.items()]
        # ⚖️ **كسرُ التعادل صريحٌ: الأصغرُ فهرساً أوّلاً** (‏D-300 · مرآةُ `QuranLocator.kt`).
        # هذا الترتيبُ يقرّر أمرين لا واحداً: مَن يدخل في `top` حين يقع القطعُ داخلَ تساوٍ في
        # الصوت، ومَن **يفوز** في `locate` حين تتساوى الجودةُ (‏أوّلُ الداخلين يكسب: `q > best`).
        # وكان يقرّرهما ترتيبُ المرور على `dict` هنا وعلى `HashMap` هناك — فرقُ تنفيذٍ يخرج
        # للمستخدم **جواباً مختلفاً** (‏D-299: المرآة 792 والمحرك 3750 للنصّ نفسِه).
        scored.sort(key=lambda t: (-t[1], t[0]))
        return scored[:top]

    PREAMBLES = (["اعوذ", "بالله", "من", "الشيطان", "الرجيم"], ["بسم", "الله", "الرحمن", "الرحيم"])

    def strip_preamble(self, hyp):
        """يُسقط الاستعاذة والبسملة من أول التفريغ (لا من المصحف) — يقرأ بهما كثيرون قبل أي موضع،
        والبسملة آيةٌ نادرة بالفهرس (1:1 و27:30) فتخطف التصويت زوراً. تبقى في النص الخام
        للمحاذاة، فامتدادُ الوراء يلتقط 1:1 حين تكون الفاتحة هي المقروءة."""
        cut = 0
        changed = True
        while changed:
            changed = False
            for pre in self.PREAMBLES:
                k = len(pre)
                seg = hyp[cut:cut + k]
                if len(seg) == k and sum(1 for a, b in zip(pre, seg) if scorer._matches((a,), b, self.cfg)) >= k - 1:
                    cut += k
                    changed = True
        return cut

    def anchored(self, ref_list, hyp_text, min_acc=0.5, slack=3):
        return anchored_per_ayah(ref_list, hyp_text, self.cfg, min_acc, slack)

    def locate(self, hyp_text, max_ayahs=300, stop_after=2):
        hyp = [w for w in (scorer.norm(x, self.cfg) for x in _WS.split(hyp_text)) if w]
        if self.mode == "legacy":
            if len(hyp) < 3:
                return None
            start = self.best_start_legacy(hyp)
            if start is None:
                return None
            return self._extend(start, hyp_text, max_ayahs, stop_after)
        cut = self.strip_preamble(hyp)
        core = hyp[cut:]
        if len(core) < 2:
            return None
        cands = self.candidates(core)
        best = None
        for f, v, _ in cands:
            r = self._extend(f, hyp_text, max_ayahs, stop_after)
            if r is None:
                continue
            heard = [a for a in r["anchored"] if a["window"] is not None]
            correct = sum(a["correct"] for a in heard)
            ref_n = sum(a["n"] for a in heard)
            cover = correct / max(1, len(core))   # كم من التفريغ فُسِّر
            prec = correct / max(1, ref_n)         # كم من الآيات المدّعاة سُمع فعلاً
            q = min(cover, 1.0) * (0.5 + 0.5 * prec) + v * 1e-3
            if best is None or q > best[0]:
                # ⛔ حكمٌ محافظ: نصفُ التفريغ على الأقل مفسَّرٌ، وثلاثُ كلماتٍ صحيحةٍ على الأقل (أو كلمتان
                # حين يكون التفريغ كلمتين) — وإلا فكلامٌ غير قرآني أو تفريغٌ متلف.
                if cover < 0.5 or correct < min(3, len(core)):
                    continue
                best = (q, r, cover, prec, correct)
        if best is None:
            return None
        q, r, cover, prec, correct = best
        r["quality"] = q
        # 🔁 آياتٌ متطابقة النص (متشابهات تامّة): تُذكر البدائل ليُخبر المستخدم لا ليُخمَّن.
        got = " ".join(" ".join(scorer.norm(w, self.cfg) for w in self.ayah_words[i]) for i in range(r["start"], r["end"] + 1))
        # من فهرس النصّ المتطابق (كل المواضع) لا المرشحين وحدهم — كالكوتلن
        first_norm = " ".join(scorer.norm(w, self.cfg) for w in self.ayah_words[r["start"]])
        if not hasattr(self, "_identical"):
            ident = {}
            for i, ws in enumerate(self.ayah_words):
                ident.setdefault(" ".join(scorer.norm(w, self.cfg) for w in ws), []).append(i)
            self._identical = {k: v for k, v in ident.items() if len(v) > 1}
        pool = list(dict.fromkeys(self._identical.get(first_norm, []) + [f for f, _, _ in cands]))
        alts = []
        for f in pool:
            if f == r["start"]:
                continue
            span = " ".join(" ".join(scorer.norm(w, self.cfg) for w in self.ayah_words[i])
                            for i in range(f, min(len(self.ayah_words), f + r["end"] - r["start"] + 1)))
            if span == got:
                alts.append(f)
        r["alternatives"] = sorted(alts)
        return r

    def _extend(self, start, hyp_text, max_ayahs, stop_after):
        # ⏩ تدريجي: آيةً آية مع التوقف بعد [stop_after] غير مسموعة أو نفاد التفريغ — لا 300 آية دفعةً.
        raw = [w for w in _WS.split(hyp_text) if w]
        anchored, cursor, miss, last_heard = [], 0, 0, -1
        f = start
        while f < len(self.ayah_words) and f < start + max_ayahs:
            a, cursor = anchor_one(self.ayah_words[f], raw, cursor, self.cfg)
            a["i"] = f - start
            anchored.append(a)
            if a["window"] is not None:
                last_heard, miss = len(anchored) - 1, 0
            else:
                miss += 1
                if miss >= stop_after:
                    break
            if cursor >= len(raw):
                break
            f += 1
        if last_heard < 0:
            return None
        first_win = next((a["window"][0] for a in anchored if a["window"] is not None), 0)
        back = []
        if first_win > 0 and start > 0:
            limit, miss, f = first_win, 0, start - 1
            lo = max(0, start - max_ayahs)
            while f >= lo and miss < stop_after and limit > 0:
                a, _ = anchor_one(self.ayah_words[f], raw[:limit], 0, self.cfg)
                back.insert(0, a)
                if a["window"] is not None:
                    miss, limit = 0, a["window"][0]
                else:
                    miss += 1
                f -= 1
            while back and back[0]["window"] is None:
                back.pop(0)
        allx = back + anchored[:last_heard + 1]
        # ✂️ لا يبدأ المدى بآيةٍ لم تُسمع
        lead = 0
        while lead < len(allx) and allx[lead]["window"] is None:
            lead += 1
        allx = allx[lead:]
        new_start = start - len(back) + lead
        for k, a in enumerate(allx):
            a["i"] = k
        return {"start": new_start, "end": start + last_heard, "anchored": allx}


def anchor_one(ref, hyp, cursor, cfg, min_acc=0.5, slack=3, allow_partial=True):
    """محاذاة آيةٍ واحدة على التفريغ من [cursor] — مرآة حلقة `anchoredPerAyah` لآيةٍ واحدة."""
    n = len(ref)
    if n == 0 or cursor >= len(hyp):
        return {"n": n, "correct": 0, "window": None}, cursor
    best = None
    max_start = min(len(hyp) - 1, cursor + n + slack * 2)
    for start in range(cursor, max_start + 1):
        lo = max(1, min(n - slack, len(hyp) - start))
        for ln in range(lo, min(len(hyp) - start, n + slack) + 1):
            end = start + ln
            sc = scorer.score(ref, " ".join(hyp[start:end]), cfg)
            acc = sc["correct"] / n
            adds = len(sc["additions"])
            better = (best is None or acc > best[0] or
                      (acc == best[0] and (adds < best[3] or (adds == best[3] and start < best[1][0]))))
            if better:
                best = (acc, (start, end - 1), sc, adds)
    if best is None:
        return {"n": n, "correct": 0, "window": None}, cursor
    acc, win, sc, adds = best
    # ✂️ ذيلٌ جزئي: المستخدم توقّف في وسط الآية — نافذةٌ تبلغ آخر التفريغ، كلُّ ما فيها صحيحٌ بلا
    # زوائد، وثلاثُ كلماتٍ فأكثر ⇒ مسموعةٌ (جزئياً) لا «لم تُسمع».
    # وشرطُها أن تكون **صدرَ الآية** (بدأها ولم يُتمّها) لا كلماتٍ متفرّقةً منها.
    prefix_ok = all(w[1] == "CORRECT" for w in sc["words"][:sc["correct"]])
    partial_tail = (allow_partial and win[1] == len(hyp) - 1 and adds == 0 and prefix_ok
                    and sc["correct"] >= 3 and sc["correct"] == win[1] - win[0] + 1)
    if acc < min_acc and not partial_tail:
        return {"n": n, "correct": 0, "window": None}, cursor
    # ⚖️ **المصيبُ هنا = ما لم يُتَّهم** لا «الصحيحُ» وحدَه (‏قِيس 2026-09-12 · D-299): المحركُ يبني
    # `AyahVerdict(index, n, missed.size, uncertain.size)` فأخطاؤه `MISSED`+`SUBSTITUTED` وحدَها،
    # و`QuranLocator.locate` يحسب `words - errors` ⇒ **غيرُ المتبيَّن يُعَدُّ مصيباً في ترجيح
    # المرشّحين**. وكانت المرآةُ تردّ `CORRECT` وحدَه فتبخس كلَّ مرشّحٍ فيه `UNCERTAIN` — وهو
    # بابٌ واسع (‏D-271: نطاقُ الشكِّ أوسعُ في ورشٍ وقالون). ⚠️ ولا يُمَسّ `sc["correct"]` في شرط
    # الذيل الجزئيّ أعلاه: المحركُ يستعمل `correctCount` هناك بعينِه (`LongTasmiAnchor.kt:99-102`).
    kept = n - sum(1 for w in sc["words"] if w[1] in (scorer.MISSED, scorer.SUBSTITUTED))
    return {"n": n, "correct": kept, "window": win}, win[1] + 1


def anchored_per_ayah(ref_list, hyp_text, cfg, min_acc=0.5, slack=3):
    hyp = [w for w in _WS.split(hyp_text) if w]
    cursor, out = 0, []
    for i, ref in enumerate(ref_list):
        a, cursor = anchor_one(ref, hyp, cursor, cfg, min_acc, slack)
        a["i"] = i
        out.append(a)
    return out
